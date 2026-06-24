# MarkItDown-CN 项目介绍与使用指南

## 一、项目背景

### 1.1 原始项目

[markitdown](https://github.com/microsoft/markitdown) 是微软开源的文档转 Markdown 工具，由 AutoGen 团队开发。它能将 PDF、Word、PPT、Excel、图片、音频等多种格式转换为 Markdown，广泛应用于 LLM 数据预处理和文本分析场景。

原始设计的一个核心依赖是：当文档中包含图片时，需要配置外部 LLM（如 OpenAI GPT-4o）来进行图片内容识别和 OCR。这带来了额外的 API 成本、网络延迟和配置复杂度。

### 1.2 为什么需要改造

在实际使用中，我们发现一个明显的冗余：**当用户通过 AI 助手（如 QoderWork、CodeBuddy、Qoder）使用 markitdown 时，AI 助手本身就具备视觉能力**。用户已经在和助手对话，却还要单独配置一个外部 LLM 来识别图片——这就像你面前坐着一位翻译，却还要打电话找另一位翻译。

这引发了一个核心问题：能否让 AI 助手直接"看"文档中的图片，用自己的视觉能力完成识别，从而消除对外部 LLM 的依赖？

### 1.3 改造目标

1. **零外部 LLM 依赖**：图片识别完全由 AI 助手自身的视觉能力完成
2. **保持兼容性**：不改变 markitdown 的公共 API，新功能作为可选参数
3. **MCP 协议集成**：通过标准 MCP 协议暴露工具，AI 助手即插即用
4. **数据高效**：大文件（图片）走磁盘文件传输，不通过 MCP JSON 传递大量数据

## 二、技术思路

### 2.1 核心架构：文件侧信道 + 两阶段协作

传统的 MCP 工具调用，所有数据都在 JSON 消息中传递。对于图片这种大文件，base64 编码会显著增加传输开销。我们借鉴了 CodeWiki MCP 的设计模式——**文件侧信道（File Side-Channel）**：

```
┌──────────────────────────────────────────────────────────────┐
│                      MCP 协议通道                            │
│                                                              │
│  AI 助手 ──调用──→ analyze_document("/path/to/file.pdf")     │
│                                                              │
│  MCP Server ──返回──→ JSON {                                 │
│    text_skeleton: "文档文本... ![image](/tmp/img_1.png) ...", │
│    images: [{path: "/tmp/img_1.png", size: "1920x1080", ...}]│
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
                                                              │
                                                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    文件侧信道（磁盘）                         │
│                                                              │
│  /tmp/markitdown_mcp_xxx/                                    │
│  └── a1b2c3d4/                                               │
│      └── images/                                             │
│          ├── img_1.png    ← AI 助手通过 Read 工具直接读取     │
│          ├── img_2.jpg                                       │
│          └── img_3.tiff                                      │
└──────────────────────────────────────────────────────────────┘
```

MCP 只传递轻量级的元数据（路径、尺寸），实际的图片数据通过磁盘文件传递。AI 助手通过文件系统的 Read 工具直接读取图片，用自己的视觉能力进行分析。

### 2.2 两阶段工作流

**Phase 1：提取阶段（MCP Server 完成）**

AI 助手调用 `analyze_document` 工具，MCP Server 以 `extract_only=True` 模式运行 markitdown：

- 文本内容正常提取为 Markdown
- 遇到图片时，不调用 LLM，而是将图片保存到临时目录
- 在 Markdown 中留下 `![image](<磁盘路径>)` 占位符
- 返回 JSON 包含：文本骨架 + 图片清单（路径、尺寸、在文档中的位置）

**Phase 2：识别阶段（AI 助手完成）**

AI 助手根据图片清单，智能选择需要处理的图片：

- **大于 10KB 的图片**：完整 OCR，逐行提取文字
- **小于 2KB 的图片**：可能是图标，标记为 `[icon]` 跳过
- **图表类图片**：生成描述性文字，标注图表类型
- **文字密集的扫描件**：用 blockquote 格式输出 OCR 结果

最终，助手将识别结果替换回文本骨架中的占位符，输出完整的 Markdown 文档。

### 2.3 关键设计决策

**为什么新建 `analyze_document` 而不是修改 `convert_to_markdown`？**

`convert_to_markdown` 返回纯文本 Markdown，AI 助手无法区分哪些部分是图片占位符。`analyze_document` 返回结构化 JSON，助手可以精确知道每张图片的位置、大小和上下文，从而做出智能决策。

**为什么在现有 Converter 类中添加 extract_only 分支，而不是创建新类？**

保持代码简洁，避免类继承层级膨胀。`extract_only` 作为一个布尔开关，在现有转换流程的关键节点（图片处理处）插入分支，对原有逻辑零侵入。

**临时目录的生命周期如何管理？**

MCP Server 在启动时创建临时根目录，每个文档的子目录基于文件路径的 SHA-256 哈希命名。启动时清理超过 24 小时的旧目录，关闭时清理所有临时数据。

## 三、实现过程

### 3.1 设计阶段

使用 OpenSpec 工作流（propose → design → specs → tasks）进行规范化设计：

- **proposal.md**：阐述动机和目标——消除外部 LLM 依赖
- **design.md**：4 个关键技术决策的详细论证
- **specs/**：3 个功能模块的精确规范（extract-only-mode、mcp-analyze-document、assistant-orchestration）
- **tasks.md**：5 个任务组、22 项具体任务

### 3.2 代码修改范围

共修改 **9 个源文件**，新增约 **770 行代码**：

| 文件 | 修改内容 |
|------|---------|
| `markitdown/_markitdown.py` | 核心类添加 `extract_only` 和 `image_output_dir` 参数，在 `_convert()` 中向下传递 |
| `converters/_image_converter.py` | `ImageConverter` 添加 extract_only 分支：保存图片到磁盘，返回带元数据注释的占位符 |
| `markitdown_mcp/__main__.py` | MCP Server 新增 `analyze_document` 工具：创建临时目录、运行 extract_only 转换、收集图片元数据、返回 JSON |
| `markitdown_ocr/_ocr_service.py` | 新增 `format_image_reference()` 共享函数，生成带注释的 Markdown 图片引用 |
| `markitdown_ocr/_pdf_converter_with_ocr.py` | PDF OCR 转换器添加 extract_only 分支 |
| `markitdown_ocr/_docx_converter_with_ocr.py` | DOCX OCR 转换器添加 extract_only 分支 |
| `markitdown_ocr/_pptx_converter_with_ocr.py` | PPTX OCR 转换器添加 extract_only 分支 |
| `markitdown_ocr/_xlsx_converter_with_ocr.py` | XLSX OCR 转换器添加 extract_only 分支 |
| `markitdown-mcp/pyproject.toml` | 依赖约束调整，兼容 Python 3.13/3.14 |

### 3.3 配套产出

| 产出 | 说明 |
|------|------|
| **assistant-orchestration Skill** | 234 行的 AI 助手编排技能，定义两阶段工作流、智能图片选择策略、批处理方案 |
| **repowiki/** | 10 篇模块级技术文档，覆盖核心引擎、转换器、MCP Server、OCR 插件等 |
| **openspec/ 设计文档** | 完整的提案、设计、规范和任务清单 |

## 四、使用方法

### 4.1 环境准备

```bash
# 1. 安装 Python 3.13（推荐）
# Windows: 从 https://www.python.org 下载安装
# macOS: brew install python@3.13

# 2. 克隆项目
git clone https://github.com/mambo-wang/markitdown-mcp.git
cd markitdown-mcp

# 3. 安装依赖
pip install -e packages/markitdown
pip install -e packages/markitdown-mcp

# 4. 验证安装
python -c "from markitdown import MarkItDown; print('OK')"
python -c "from markitdown_mcp.__main__ import mcp; print('MCP OK')"
```

### 4.2 配置 MCP Server

在 QoderWork 中配置 markitdown MCP Server（STDIO 模式）：

1. 打开 QoderWork → Settings → Connectors
2. 添加自定义 MCP Server
3. 粘贴以下 JSON 配置：

```json
{
  "mcpServers": {
    "markitdown": {
      "command": "你的Python路径",
      "args": ["-m", "markitdown_mcp"]
    }
  }
}
```

4. 保存后，`convert_to_markdown` 和 `analyze_document` 两个工具将自动注册

### 4.3 使用 AI 助手分析文档

配置完成后，在 QoderWork 中直接与助手对话：

> "帮我把 C:\Documents\report.pdf 转换为 Markdown"

助手会自动执行两阶段流程：

1. 调用 `analyze_document` 提取文本和图片
2. 用自身的视觉能力读取每张图片并识别内容
3. 输出完整的 Markdown 文档

### 4.4 Python API 直接使用

不通过 MCP 也可以直接在 Python 中使用 extract_only 模式：

```python
from markitdown import MarkItDown

md = MarkItDown(extract_only=True, image_output_dir="./extracted_images")
result = md.convert("report.pdf")

# text_content 包含文本骨架和图片占位符
print(result.text_content)
# 输出:
# # 年度报告
# 
# ## 第一章 概述
# 公司今年业绩...
# 
# <!-- image: 1920x1080, 239KB -->
# ![image](./extracted_images/img_a1b2c3d4.png)
#
# ## 第二章 财务数据
# ...

# extracted_images/ 目录下有提取出的图片文件
```

### 4.5 命令行使用

```bash
# 基本转换
markitdown document.pdf -o output.md

# 启用插件（含 OCR）
markitdown --use-plugins scanned_document.pdf -o output.md

# 启用 OCR 插件的环境变量
MARKITDOWN_ENABLE_PLUGINS=true markitdown document.pdf
```

## 五、技术栈

| 组件 | 技术 |
|------|------|
| 核心引擎 | Python 3.10+, magika（文件类型检测） |
| 文档解析 | pdfplumber, pdfminer.six, python-docx, python-pptx, openpyxl, mammoth |
| MCP Server | MCP SDK 1.28.0, Starlette, uvicorn |
| MCP 协议 | 2025-11-25 |
| 传输模式 | STDIO / SSE / Streamable HTTP |
| AI 集成 | 文件侧信道 + Read 工具视觉识别 |

## 六、与原版的主要差异

| 方面 | 原版 markitdown | markitdown-mcp |
|------|----------------|---------------|
| 图片识别 | 需要外部 LLM（OpenAI GPT-4o 等） | AI 助手自身视觉能力 |
| MCP 工具 | 仅 `convert_to_markdown` | 新增 `analyze_document` |
| extract_only 模式 | 无 | 核心新增，跳过 LLM 调用 |
| OCR 插件 | 依赖外部 LLM client | 同样支持 extract_only |
| 编排技能 | 无 | 提供 assistant-orchestration Skill |
| MCP SDK 版本 | ~=1.8.0 | >=1.8.0（已验证 1.28.0） |
| 语言 | 英文 | 中文增强 |
