# MarkItDown-CN

[![PyPI](https://img.shields.io/pypi/v/markitdown.svg)](https://pypi.org/project/markitdown/)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 基于 [microsoft/markitdown](https://github.com/microsoft/markitdown) 的中文增强版，核心改进：**AI 助手驱动的 OCR 方案**，无需配置外部 LLM，通过 MCP 协议与 AI 助手（QoderWork / CodeBuddy / Qoder）深度协作，利用助手自身的视觉能力完成图片识别和文档分析。

MarkItDown 是一个轻量级 Python 工具，用于将各类文件转换为 Markdown，主要服务于 LLM 和文本分析场景。它在保留文档结构（标题、列表、表格、链接等）的同时，输出对 AI 友好的 Markdown 文本。

## 支持的格式

| 类别 | 格式 |
|------|------|
| 文档 | PDF、Word (.docx)、PowerPoint (.pptx)、EPUB |
| 表格 | Excel (.xlsx/.xls)、CSV、JSON、XML |
| 图片 | PNG、JPG、BMP、WebP 等（EXIF 元数据 + OCR） |
| 音频 | WAV、MP3（EXIF 元数据 + 语音转写） |
| 网页 | HTML、YouTube、Wikipedia、RSS |
| 其他 | ZIP（递归处理）、Outlook 邮件、Jupyter Notebook |

## 项目结构

```
markitdown-mcp/
├── packages/
│   ├── markitdown/              # 核心库 — 格式转换引擎
│   ├── markitdown-mcp/          # MCP Server — AI 助手集成入口
│   ├── markitdown-ocr/          # OCR 插件 — 文档内嵌图片的文字提取
│   └── markitdown-sample-plugin/# 插件开发示例
├── openspec/                    # 设计文档与规范
│   └── changes/assistant-driven-ocr/
├── repowiki/                    # 项目 Wiki（模块级技术文档）
└── README.md
```

## 核心特性：AI 助手驱动模式

传统方案需要单独配置 OpenAI 等外部 LLM 来驱动 OCR 和图片描述。本项目的 **extract_only** 模式彻底消除了这一依赖：

```
传统流程:  文档 → MarkItDown → 调用外部 LLM → Markdown
AI 助手流程: 文档 → MarkItDown (extract_only) → 文本骨架 + 图片文件
                                                      ↓
                                              AI 助手读取图片
                                                      ↓
                                              最终 Markdown
```

**工作原理：**

1. **Phase 1 — 提取**：MCP Server 的 `analyze_document` 工具将文档转换为文本骨架（Markdown），同时将嵌入的图片提取到磁盘临时目录，返回 JSON 格式的图片清单（路径、尺寸、位置）
2. **Phase 2 — 识别**：AI 助手通过 Read 工具直接读取磁盘上的图片文件，利用自身的视觉能力进行 OCR / 图表描述 / 内容分析
3. **合并输出**：助手将识别结果替换回文本骨架中的图片占位符，生成完整的 Markdown 文档

## 安装

### 环境要求

- Python 3.10+（推荐 3.13）
- 建议使用虚拟环境

### 从源码安装（开发模式）

```bash
git clone https://github.com/mambo-wang/markitdown-mcp.git
cd markitdown-mcp

# 安装核心库
pip install -e packages/markitdown

# 安装 MCP Server
pip install -e packages/markitdown-mcp

# 安装 OCR 插件（可选）
pip install -e packages/markitdown-ocr
```

### 使用 pip 安装（PyPI 原版）

```bash
pip install 'markitdown[all]'
```

## 使用方法

### 命令行

```bash
# 转换文件为 Markdown
markitdown document.pdf > output.md

# 指定输出文件
markitdown document.pdf -o output.md

# 管道输入
cat document.pdf | markitdown
```

### Python API

```python
from markitdown import MarkItDown

# 基本转换
md = MarkItDown()
result = md.convert("report.pdf")
print(result.text_content)

# extract_only 模式（不依赖外部 LLM）
md = MarkItDown(extract_only=True)
result = md.convert("report_with_images.pdf")
# 输出包含图片占位符和元数据注释：
# <!-- image: 1920x1080, 239KB -->
# ![image](/tmp/markitdown_images/abc123.png)
```

### MCP Server 配置

MCP Server 提供两个工具：

| 工具 | 说明 |
|------|------|
| `convert_to_markdown(uri)` | 将 URI 资源转换为 Markdown（原有工具） |
| `analyze_document(path)` | 提取文本骨架 + 图片清单（新增，用于 AI 助手协作） |

#### STDIO 模式（推荐）

在 QoderWork 的 Connectors 设置中，添加自定义 MCP Server，粘贴以下配置：

```json
{
  "mcpServers": {
    "markitdown": {
      "command": "C:\\Program Files\\Python313\\python.exe",
      "args": ["-m", "markitdown_mcp"]
    }
  }
}
```

> 将 `command` 路径替换为你的 Python 解释器路径。

#### HTTP 模式

```bash
# 启动 SSE / Streamable HTTP 服务器
python -m markitdown_mcp --http --host 127.0.0.1 --port 3001
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MARKITDOWN_ENABLE_PLUGINS` | 启用插件 | `false` |

## 可选依赖

markitdown 支持按需安装格式依赖：

```bash
pip install 'markitdown[pdf]'              # 仅 PDF
pip install 'markitdown[docx, pptx]'       # Word + PPT
pip install 'markitdown[az-doc-intel]'     # Azure Document Intelligence
pip install 'markitdown[az-content-understanding]'  # Azure Content Understanding
```

完整列表：`all`, `pptx`, `docx`, `xlsx`, `xls`, `pdf`, `outlook`, `audio-transcription`, `youtube-transcription`, `az-doc-intel`, `az-content-understanding`

## 插件系统

markitdown 通过 Python `entry_points` 机制支持第三方插件。OCR 插件 `markitdown-ocr` 为 PDF、DOCX、PPTX、XLSX 中嵌入的图片提供 OCR 支持。

```bash
# 列出已安装的插件
markitdown --list-plugins

# 启用插件进行转换
markitdown --use-plugins document.pdf
```

开发自定义插件请参考 `packages/markitdown-sample-plugin`。

## 版本信息

| 组件 | 版本 |
|------|------|
| markitdown | 0.1.6 |
| markitdown-mcp | 0.0.1a5 |
| MCP SDK | >=1.8.0（已验证 1.28.0） |
| MCP 协议 | 2025-11-25 |

## 文档

- [项目介绍与使用指南](PROJECT_GUIDE.md) — AI 助手驱动方案的设计思路、实现过程和使用方法
- [repowiki/](repowiki/) — 各模块的技术文档（Core Engine、MCP Server、OCR Plugin 等）
- [openspec/](openspec/changes/assistant-driven-ocr/) — extract_only 模式的设计提案与规范

## 致谢

本项目基于 Microsoft 的 [markitdown](https://github.com/microsoft/markitdown) 进行增强开发。感谢 AutoGen Team 的原始工作。

## License

MIT
