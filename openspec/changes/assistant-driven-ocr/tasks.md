## 1. 核心库 extract-only 模式

- [ ] 1.1 在 `MarkItDown.__init__()` 中添加 `extract_only` 参数，默认为 False，存入实例属性
- [ ] 1.2 在 `MarkItDown._convert()` 中将 `extract_only` 和 `image_output_dir` 作为 kwargs 传递给转换器
- [ ] 1.3 改造 `ImageConverter.convert()`：当 `extract_only=True` 时，将图片写入 `image_output_dir`，返回 `![image](<path>)` 占位符和元数据注释，跳过 `llm_caption()` 调用
- [ ] 1.4 改造 `ImageConverter.accepts()` 确保 extract-only 模式下仍正确识别图片类型
- [ ] 1.5 为 `ImageConverter` 的 extract-only 模式编写单元测试：验证图片文件生成、路径正确性、元数据注释格式

## 2. OCR 插件 extract-only 模式

- [ ] 2.1 改造 `PdfConverterWithOCR.convert()`：添加 `extract_only` 分支，提取每页嵌入图片到 `{image_output_dir}/page_{n}_{idx}.{ext}`
- [ ] 2.2 改造 `DocxConverterWithOCR.convert()`：添加 `extract_only` 分支，提取嵌入图片并返回路径引用
- [ ] 2.3 改造 `PptxConverterWithOCR.convert()`：添加 `extract_only` 分支，提取幻灯片嵌入图片
- [ ] 2.4 改造 `XlsxConverterWithOCR.convert()`：添加 `extract_only` 分支，提取工作表嵌入图片
- [ ] 2.5 改造 `LLMVisionOCRService`：在 extract-only 模式下跳过 OCR 调用，仅执行图片提取
- [ ] 2.6 为 OCR 插件的 extract-only 模式编写单元测试：验证四种格式的图片提取和路径输出

## 3. MCP Server analyze_document 工具

- [ ] 3.1 在 `markitdown-mcp` 包中注册新的 MCP 工具 `analyze_document`，定义输入 schema（path/URI）和输出 schema（text_skeleton + images 数组 + metadata）
- [ ] 3.2 实现 `analyze_document` 核心逻辑：调用 `MarkItDown(extract_only=True)` 转换文档，收集文本骨架和图片路径列表
- [ ] 3.3 实现图片目录管理：使用 `tempfile.mkdtemp()` 创建 `{server_temp_root}/{document_hash}/images/` 结构
- [ ] 3.4 实现图片元数据收集：提取每张图片的 width、height、size_bytes、position 信息
- [ ] 3.5 实现临时目录生命周期管理：在 `lifespan()` 中添加启动时清理旧目录（>24h）和退出时清理所有临时目录的逻辑
- [ ] 3.6 支持 URI 输入：复用 `MarkItDown.convert()` 的 URI 处理能力（http/https/file/data）
- [ ] 3.7 为 `analyze_document` 编写集成测试：PDF 带图片、纯文本、HTTP URL 三种场景

## 4. 编排层 Skill

- [ ] 4.1 创建 Skill 目录结构和 SKILL.md 文件
- [ ] 4.2 编写两阶段工作流说明：Phase 1 调用 `analyze_document`，Phase 2 逐图片读取和 OCR
- [ ] 4.3 编写智能图片选择策略：按文件大小排序、阈值过滤（>10KB 做 OCR，其余摘要）、批量处理指导（每批 5-10 张）
- [ ] 4.4 编写占位符替换指南：如何将图片占位符替换为 OCR 文本或描述性文字
- [ ] 4.5 编写边界情况处理：无图片文档、超多图片文档（100+）、混合内容文档的策略

## 5. 文档与集成验证

- [ ] 5.1 更新 README.md：添加 extract-only 模式和 `analyze_document` 工具的使用说明
- [ ] 5.2 更新 MCP Server 文档：新增 `analyze_document` 工具的参数和返回值说明
- [ ] 5.3 端到端集成测试：使用 AI 助手 + MCP Server 完整流程验证（文档上传 → analyze_document → 图片 OCR → 最终 Markdown）
