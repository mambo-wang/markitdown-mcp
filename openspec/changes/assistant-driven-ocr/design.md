## Context

markitdown 是一个多格式文档转 Markdown 的 Python 库，当前在以下场景依赖外部 LLM 配置：

1. **ImageConverter** → `llm_caption()` 调用 OpenAI 兼容 API 为图片生成文字描述
2. **OCR 插件** (`markitdown-ocr`) → `LLMVisionOCRService` 调用视觉模型对文档嵌入图片做 OCR
3. **AudioConverter** → 使用 SpeechRecognition 本地引擎，不依赖 LLM

用户通过 AI 助手（QoderWork/CodeBuddy/Qoder）的 MCP 工具使用 markitdown 时，助手本身就是多模态 LLM，具备视觉理解能力。当前架构要求用户额外配置 `llm_client` + `llm_model`，造成双重配置和维护负担。

约束条件：
- MCP 使用 STDIO 传输，不适合在协议层传递大量 base64 图片数据
- AI 助手具备文件读取能力（Read 工具可直接读取图片）
- 助手上下文窗口有限，不能一次性塞入大量图片

## Goals / Non-Goals

**Goals:**
- 消除 markitdown 对独立 LLM 配置的依赖（当通过 AI 助手使用时）
- 利用文件侧通道传递图片数据，避免 MCP 协议层的数据膨胀
- 让 AI 助手自主决策哪些图片需要 OCR、哪些只需简要描述
- 保持 API 向后兼容，extract-only 模式为可选参数

**Non-Goals:**
- 不替代现有的 LLM 直调模式（保留给非助手场景使用）
- 不改造音频转录流程（SpeechRecognition 是本地引擎，不涉及 LLM）
- 不实现图片的批量并行处理（由助手侧的编排逻辑决定）
- 不提供图片内容的缓存或索引机制

## Decisions

### Decision 1: 文件侧通道而非协议内传输

**选择**：图片数据写入磁盘临时文件，MCP 只返回文件路径

**理由**：
- STDIO 模式下 MCP 协议传输 base64 图片会导致 JSON 消息体过大，影响传输效率
- AI 助手（QoderWork）的 Read 工具原生支持读取图片文件并作为多模态输入
- 与 CodeWiki MCP 的"文件侧通道"模式一致，是经过验证的模式

**备选方案**：
- 在 MCP 响应中嵌入 base64 → 排除，数据量过大
- 使用 HTTP 模式 + multipart 上传 → 排除，增加部署复杂度，且 STDIO 模式更常用

### Decision 2: 两阶段工具调用（analyze_document）

**选择**：新增独立的 `analyze_document` MCP 工具，而非修改现有 `convert_to_markdown`

**理由**：
- `convert_to_markdown` 保持原有语义（返回完整 Markdown），不破坏已有客户端
- `analyze_document` 返回结构化数据（文本骨架 + 图片列表 + 位置标记），助手可以智能编排后续处理
- 两阶段设计让助手拥有决策权：可以跳过不重要的图片、合并相似图片、按需选择 OCR 深度

**备选方案**：
- 在 `convert_to_markdown` 中加 `extract_images=true` 参数 → 排除，返回结构变化会影响已有客户端
- 只提供 `extract_images` 工具不做文本转换 → 排除，助手仍需调 `convert_to_markdown`，两次调用不如一次集成

### Decision 3: 转换器层面的 extract-only 分支

**选择**：在 `ImageConverter` 和 OCR 转换器中添加 `extract_only` 参数分支

**理由**：
- 最小化代码改动，不引入新的转换器类
- extract_only=True 时跳过 LLM 调用，输出占位符 `![image](<file_path>)`，助手后续替换
- 保留原有 LLM 路径，向后兼容

**备选方案**：
- 创建独立的 `ImageExtractor` 转换器类 → 排除，代码重复度高
- 通过环境变量全局切换 → 排除，粒度太粗，影响所有实例

### Decision 4: 临时目录生命周期管理

**选择**：MCP Server 的 lifespan 中管理临时目录，会话结束时自动清理

**理由**：
- `analyze_document` 每次调用创建 `{session_tempdir}/{doc_id}/images/` 子目录
- MCP Server 的 `lifespan()` 已有资源管理逻辑，扩展即可
- 避免孤儿文件累积占用磁盘

## Risks / Trade-offs

**[助手编排复杂度]** → 助手需要额外的编排逻辑来组合文本和图片分析结果
→ 缓解：提供标准化的 Skill/提示词模板，封装编排逻辑

**[大量图片的 token 预算]** → 100 页扫描 PDF 可能有数百张图片，助手无法逐张处理
→ 缓解：`analyze_document` 返回图片尺寸和位置元数据，助手可智能筛选（如只 OCR 大于阈值的图片）

**[临时文件清理]** → 进程异常退出可能导致临时文件残留
→ 缓解：使用 `tempfile.mkdtemp()` + 启动时清理旧目录 + lifespan 退出钩子

**[两次调用开销]** → 助手需要两次工具调用（analyze_document + 图片读取）而非一次
→ 缓解：相比配置和维护外部 LLM 的成本，两次调用的开销可接受
