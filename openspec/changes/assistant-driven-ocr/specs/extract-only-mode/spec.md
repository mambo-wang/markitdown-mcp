## ADDED Requirements

### Requirement: Extract-only mode for ImageConverter
`ImageConverter` SHALL support an `extract_only` mode. When `extract_only=True`, the converter SHALL extract the image to a file on disk and return a `DocumentConverterResult` containing a Markdown image reference `![image](<file_path>)` instead of calling `llm_caption()`.

#### Scenario: Extract-only mode with local file
- **WHEN** `ImageConverter.convert()` is called with `extract_only=True` and an `image_output_dir` parameter
- **THEN** the image SHALL be saved to `{image_output_dir}/{unique_id}.{ext}` and the returned markdown SHALL contain `![image]({file_path})`

#### Scenario: Extract-only mode without output directory
- **WHEN** `ImageConverter.convert()` is called with `extract_only=True` but no `image_output_dir`
- **THEN** a temporary directory SHALL be created automatically using `tempfile.mkdtemp()`

#### Scenario: Default behavior unchanged
- **WHEN** `ImageConverter.convert()` is called without `extract_only` parameter (or `extract_only=False`)
- **THEN** the existing `llm_caption()` flow SHALL be used as before

### Requirement: Extract-only mode for OCR plugin converters
All OCR-enhanced converters (`PdfConverterWithOCR`, `DocxConverterWithOCR`, `PptxConverterWithOCR`, `XlsxConverterWithOCR`) SHALL support `extract_only` mode. In this mode, embedded images SHALL be extracted to disk and referenced by path, without invoking `LLMVisionOCRService`.

#### Scenario: PDF extract-only with embedded images
- **WHEN** `PdfConverterWithOCR.convert()` is called with `extract_only=True`
- **THEN** each page's embedded images SHALL be saved to `{image_output_dir}/page_{n}_{idx}.{ext}` and referenced in the output markdown

#### Scenario: DOCX extract-only with embedded images
- **WHEN** `DocxConverterWithOCR.convert()` is called with `extract_only=True`
- **THEN** embedded images in the DOCX SHALL be extracted and referenced by file path instead of being sent to the OCR service

### Requirement: MarkItDown constructor supports extract_only
`MarkItDown.__init__()` SHALL accept an `extract_only` boolean parameter (default `False`). When `True`, it SHALL be passed as a default kwarg to all converters during conversion.

#### Scenario: Global extract-only mode
- **WHEN** `MarkItDown(extract_only=True)` is instantiated and `convert()` is called
- **THEN** all converters that support `extract_only` SHALL operate in extract-only mode

#### Scenario: Per-call override
- **WHEN** `MarkItDown(extract_only=True)` is instantiated but `convert()` is called with `extract_only=False`
- **THEN** the per-call parameter SHALL override the instance default

### Requirement: Image metadata in extract-only output
In extract-only mode, the output SHALL include image metadata as a structured comment block preceding each image reference, containing dimensions (width, height) and file size.

#### Scenario: Image metadata comment
- **WHEN** an image of 1920x1080 pixels and 245KB is extracted in extract-only mode
- **THEN** the output SHALL contain `<!-- image: 1920x1080, 245KB -->` followed by `![image](<file_path>)`
