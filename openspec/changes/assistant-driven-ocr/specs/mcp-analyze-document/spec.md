## ADDED Requirements

### Requirement: analyze_document MCP tool
The MCP server SHALL expose an `analyze_document` tool that accepts a file path (local path or URI) and returns a structured JSON response containing: text skeleton (markdown with image placeholders), image manifest (list of extracted image file paths with metadata), and document metadata.

#### Scenario: Analyze a PDF with embedded images
- **WHEN** the `analyze_document` tool is called with a PDF file path containing 3 embedded images
- **THEN** the response SHALL contain a `text_skeleton` field with markdown text, an `images` array with 3 entries each containing `path`, `position`, `width`, `height`, and `size_bytes` fields, and a `metadata` object with `page_count`

#### Scenario: Analyze a DOCX document
- **WHEN** the `analyze_document` tool is called with a DOCX file containing 2 embedded images
- **THEN** the images SHALL be extracted to `{temp_dir}/{doc_id}/images/` and their paths returned in the `images` array

#### Scenario: Analyze a text-only document
- **WHEN** the `analyze_document` tool is called with a plain text file
- **THEN** the response SHALL contain a `text_skeleton` field and an empty `images` array

### Requirement: File side-channel for image data
All image data SHALL be written to disk files rather than embedded in the MCP response. The MCP response SHALL only contain file paths and metadata.

#### Scenario: Image files written to temp directory
- **WHEN** `analyze_document` processes a document with images
- **THEN** each image SHALL be written as a separate file under a session-scoped temporary directory, and the MCP response SHALL contain absolute file paths

#### Scenario: Response payload size
- **WHEN** `analyze_document` processes a document with 50 embedded images
- **THEN** the MCP response JSON SHALL be under 100KB (paths and metadata only, not image data)

### Requirement: Temporary directory lifecycle management
The MCP server SHALL manage temporary directories for extracted images with automatic cleanup on session end.

#### Scenario: Directory created per document
- **WHEN** `analyze_document` is called
- **THEN** images SHALL be written to `{server_temp_root}/{document_hash}/images/`

#### Scenario: Cleanup on server shutdown
- **WHEN** the MCP server's lifespan context exits
- **THEN** all temporary directories under `server_temp_root` SHALL be removed

#### Scenario: Cleanup of stale directories
- **WHEN** the MCP server starts
- **THEN** temporary directories older than 24 hours SHALL be removed during startup

### Requirement: analyze_document supports URI input
The `analyze_document` tool SHALL accept the same input types as `convert_to_markdown`: local file paths, `http://` / `https://` URLs, `file://` URIs, and `data:` URIs.

#### Scenario: Analyze from HTTP URL
- **WHEN** `analyze_document` is called with an `https://` URL
- **THEN** the document SHALL be fetched, processed in extract-only mode, and the response SHALL include text skeleton and image paths
