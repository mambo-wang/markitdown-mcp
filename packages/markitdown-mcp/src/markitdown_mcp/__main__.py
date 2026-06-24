import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from markitdown import MarkItDown
import uvicorn


# ---------------------------------------------------------------------------
# Temporary directory management (module-level)
# ---------------------------------------------------------------------------

_temp_root: str = tempfile.mkdtemp(prefix="markitdown_mcp_")

# Image file extensions we recognise when scanning output directories
_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".ico"}
)


def _cleanup_old_dirs(root: str, max_age_seconds: int = 86400) -> None:
    """Remove sub-directories under *root* that are older than *max_age_seconds*."""
    now = time.time()
    try:
        for entry in os.scandir(root):
            if entry.is_dir():
                try:
                    if now - entry.stat().st_mtime > max_age_seconds:
                        shutil.rmtree(entry.path, ignore_errors=True)
                except OSError:
                    pass
    except FileNotFoundError:
        pass


def _cleanup_all(root: str) -> None:
    """Remove the entire *root* directory tree."""
    shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

# Initialize FastMCP server for MarkItDown (SSE)
mcp = FastMCP("markitdown")


@mcp.tool()
async def convert_to_markdown(uri: str) -> str:
    """Convert a resource described by an http:, https:, file: or data: URI to markdown"""
    return MarkItDown(enable_plugins=check_plugins_enabled()).convert_uri(uri).markdown


@mcp.tool()
async def analyze_document(path: str) -> str:
    """Analyze a document and extract its text skeleton together with embedded images.

    Accepts a local file path or a URI (http:, https:, file:, data:).
    Returns a JSON string containing:
      - text_skeleton: the markdown text with image placeholder references
      - images: a list of extracted images with path, position, size and dimensions
      - metadata: source path and image count
    """
    # ---- validate input ------------------------------------------------
    is_uri = re.match(r"^(https?|file|data):", path) is not None
    if not is_uri and not os.path.exists(path):
        return json.dumps({"error": f"File not found: {path}"})

    # ---- prepare per-document temp directory ----------------------------
    doc_hash = hashlib.sha256(path.encode("utf-8", errors="replace")).hexdigest()[:16]
    doc_dir = os.path.join(_temp_root, doc_hash)
    image_dir = os.path.join(doc_dir, "images")
    os.makedirs(image_dir, exist_ok=True)

    # ---- run conversion -------------------------------------------------
    try:
        md_instance = MarkItDown(
            enable_plugins=check_plugins_enabled(),
            extract_only=True,
            image_output_dir=image_dir,
        )
        result = md_instance.convert(path)
        text_skeleton: str = result.markdown or ""
    except Exception as exc:
        return json.dumps({"error": f"Conversion failed: {exc}"})

    # ---- collect image files on disk ------------------------------------
    image_files: list[str] = []
    for fname in sorted(os.listdir(image_dir)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in _IMAGE_EXTENSIONS:
            image_files.append(os.path.join(image_dir, fname))

    # ---- parse image references from text skeleton ----------------------
    # Pattern matches an optional HTML comment with image metadata, followed
    # by the standard markdown image reference  ![alt](path)
    img_ref_pattern = re.compile(
        r"(?:<!--\s*image:\s*(?P<meta>[^>]*?)\s*-->\s*\n?)?"
        r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)"
    )

    images_out: list[dict] = []
    for match in img_ref_pattern.finditer(text_skeleton):
        src = match.group("src")
        meta_str = match.group("meta") or ""

        # Resolve to absolute path on disk
        if os.path.isabs(src):
            img_path = src
        else:
            # Relative paths are resolved against the document's directory
            base_dir = os.path.dirname(path) if not is_uri else ""
            img_path = os.path.normpath(os.path.join(base_dir, src))

        # File size
        size_bytes: int | None = None
        try:
            size_bytes = os.path.getsize(img_path)
        except OSError:
            pass

        # Dimensions -- try the metadata comment first (e.g. "1920x1080, 239KB"),
        # then fall back to PIL.
        width: int | None = None
        height: int | None = None

        dim_match = re.search(r"(\d+)\s*x\s*(\d+)", meta_str)
        if dim_match:
            width, height = int(dim_match.group(1)), int(dim_match.group(2))
        else:
            try:
                from PIL import Image as PILImage

                with PILImage.open(img_path) as img:
                    width, height = img.size
            except Exception:
                pass

        # Position: a short context snippet around the image reference
        start = max(0, match.start() - 60)
        end = min(len(text_skeleton), match.end() + 60)
        context_before = text_skeleton[start : match.start()].strip().split("\n")[-1]
        context_after = text_skeleton[match.end() : end].strip().split("\n")[0]
        position_parts: list[str] = []
        if context_before:
            position_parts.append(f"...{context_before}")
        position_parts.append("[image]")
        if context_after:
            position_parts.append(f"{context_after}...")
        position = " ".join(position_parts)

        images_out.append(
            {
                "path": img_path,
                "position": position,
                "size_bytes": size_bytes,
                "width": width,
                "height": height,
            }
        )

    # Also account for image files that were extracted but not referenced in
    # the text skeleton (e.g. embedded attachments).
    referenced_paths = {img["path"] for img in images_out}
    for fpath in image_files:
        if fpath not in referenced_paths:
            size_bytes = None
            try:
                size_bytes = os.path.getsize(fpath)
            except OSError:
                pass
            width, height = None, None
            try:
                from PIL import Image as PILImage

                with PILImage.open(fpath) as img:
                    width, height = img.size
            except Exception:
                pass
            images_out.append(
                {
                    "path": fpath,
                    "position": "[unreferenced image]",
                    "size_bytes": size_bytes,
                    "width": width,
                    "height": height,
                }
            )

    # ---- build response -------------------------------------------------
    response = {
        "text_skeleton": text_skeleton,
        "images": images_out,
        "metadata": {
            "source": path,
            "image_count": len(images_out),
        },
    }
    return json.dumps(response, ensure_ascii=False)


def check_plugins_enabled() -> bool:
    return os.getenv("MARKITDOWN_ENABLE_PLUGINS", "false").strip().lower() in (
        "true",
        "1",
        "yes",
    )


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    sse = SseServerTransport("/messages/")
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=True,
        stateless=True,
    )

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    async def handle_streamable_http(
        scope: Scope, receive: Receive, send: Send
    ) -> None:
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Context manager for session manager with temp-dir lifecycle."""
        # Startup: purge stale temp directories older than 24 h
        _cleanup_old_dirs(_temp_root, max_age_seconds=86400)
        async with session_manager.run():
            print("Application started with StreamableHTTP session manager!")
            try:
                yield
            finally:
                print("Application shutting down...")
                _cleanup_all(_temp_root)

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/mcp", app=handle_streamable_http),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        lifespan=lifespan,
    )


# Main entry point
def main():
    import argparse

    mcp_server = mcp._mcp_server

    parser = argparse.ArgumentParser(description="Run a MarkItDown MCP server")

    parser.add_argument(
        "--http",
        action="store_true",
        help="Run the server with Streamable HTTP and SSE transport rather than STDIO (default: False)",
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="(Deprecated) An alias for --http (default: False)",
    )
    parser.add_argument(
        "--host", default=None, help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Port to listen on (default: 3001)"
    )
    args = parser.parse_args()

    use_http = args.http or args.sse

    if not use_http and (args.host or args.port):
        parser.error(
            "Host and port arguments are only valid when using streamable HTTP or SSE transport (see: --http)."
        )
        sys.exit(1)

    if use_http:
        host = args.host if args.host else "127.0.0.1"
        if args.host and args.host not in ("127.0.0.1", "localhost"):
            print(
                "\n"
                "WARNING: The server is being bound to a non-localhost interface "
                f"({host}).\n"
                "This exposes the server to other machines on the network or Internet.\n"
                "The server has NO authentication and runs with the user's privileges.\n"
                "Any process or user that can reach this interface can read files and\n"
                "fetch network resources accessible to this user.\n"
                "Only proceed if you understand the security implications.\n",
                file=sys.stderr,
            )
        starlette_app = create_starlette_app(mcp_server, debug=True)
        uvicorn.run(
            starlette_app,
            host=host,
            port=args.port if args.port else 3001,
        )
    else:
        # STDIO mode: clean stale dirs on start, clean up on exit
        _cleanup_old_dirs(_temp_root, max_age_seconds=86400)
        try:
            mcp.run()
        finally:
            _cleanup_all(_temp_root)


if __name__ == "__main__":
    main()
