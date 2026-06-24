## Why

markitdown 的 OCR 和图片分析功能（`LLMVisionOCRService`、`llm_caption`）要求用户单独配置 OpenAI 兼容的 LLM client（endpoint + API key），这对于已通过 AI 助手（CodeBuddy/Qoder/QoderWork）使用 markitdown 的用户来说是冗余的——助手本身就是多模态 LLM，完全具备视觉理解能力。当前架构让用户需要维护两套 LLM 配置，且无法利用助手侧的智能决策（如判断哪些图片值得 OCR）。

## What Changes

- 新增"提取模式"（extract-only mode）：markitdown 转换文档时，将嵌入图片提取为独立文件写入磁盘，而非调用 LLM 分析
- 新增 MCP 工具 `analyze_document`：接收文件路径，返回文本骨架 + 图片文件路径列表 + 位置标记，所有图片数据走文件侧通道
- 改造 `ImageConverter` 和 OCR 插件转换器，支持 extract-only 模式（跳过 LLM 调用，输出图片占位符）
- 改造 `markitdown-mcp` 包，新增 `analyze_document` 工具，使用文件侧通道传递图片数据
- 提供编排层 Skill/提示词，指导 AI 助手如何组合文本骨架与图片分析结果生成最终 Markdown

## Capabilities

### New Capabilities
- `extract-only-mode`: 文档转换的提取模式，将嵌入图片提取到磁盘文件，返回文本骨架和图片路径，不调用任何 LLM
- `mcp-analyze-document`: MCP 工具 `analyze_document`，通过文件侧通道返回文档文本和图片路径，供助手二次处理
- `assistant-orchestration`: AI 助手编排层，指导助手读取图片文件并用自己的视觉能力完成 OCR/描述，组合最终输出

### Modified Capabilities

## Impact

- **核心库** (`packages/markitdown`)：`ImageConverter`、`llm_caption.py`、OCR 插件的 4 个转换器需要支持 extract-only 分支
- **MCP 包** (`packages/markitdown-mcp`)：新增 `analyze_document` 工具，管理临时图片目录的生命周期
- **依赖**：extract-only 模式下不再需要 `openai` 依赖，降低安装门槛
- **API 兼容性**：新增模式为可选参数，不破坏现有 API
- **文件系统**：运行时会在临时目录写入图片文件，需要清理机制
