## ADDED Requirements

### Requirement: Orchestration Skill for AI assistants
A Skill file (SKILL.md) SHALL be provided that instructs AI assistants on how to use `analyze_document` and combine the text skeleton with vision-based image analysis to produce the final Markdown output.

#### Scenario: Skill guides two-phase processing
- **WHEN** an AI assistant loads the orchestration Skill
- **THEN** the Skill SHALL describe a two-phase workflow: (1) call `analyze_document` to get text skeleton and image manifest, (2) read each image file using the Read tool and generate OCR/description using the assistant's own vision capability

#### Scenario: Skill includes intelligent image selection
- **WHEN** the image manifest contains images of varying sizes
- **THEN** the Skill SHALL guide the assistant to prioritize images above a size threshold (e.g., >10KB) for detailed OCR, and skip or summarize small decorative images

### Requirement: Orchestration produces complete Markdown output
The orchestration workflow SHALL produce a complete Markdown document where all image placeholders from the text skeleton are replaced with actual OCR results or image descriptions.

#### Scenario: Placeholder replacement
- **WHEN** the text skeleton contains `![image](/tmp/doc123/images/img_0.png)` and the assistant performs OCR on that image
- **THEN** the final output SHALL replace the placeholder with the OCR text content or a descriptive caption

#### Scenario: Document with no images
- **WHEN** `analyze_document` returns an empty images array
- **THEN** the text skeleton SHALL be returned as-is without further processing

### Requirement: Orchestration handles batch processing
The Skill SHALL guide assistants on efficiently processing documents with many images, including batching and prioritization strategies.

#### Scenario: Large document with 100+ images
- **WHEN** a scanned PDF produces 100+ image references
- **THEN** the Skill SHALL recommend processing images in batches of 5-10, prioritizing by file size, and summarizing remaining images as "[image omitted]"

#### Scenario: Mixed content document
- **WHEN** a document contains both text-heavy pages and image-heavy pages
- **THEN** the Skill SHALL recommend OCR for text-containing images and brief descriptions for purely visual images
