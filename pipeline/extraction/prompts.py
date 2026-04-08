"""
Prompt templates for the Claude AI extraction layer.

Contains system prompts, extraction prompts, and utilities for
chunking presentation content into manageable prompt payloads.
"""

from __future__ import annotations

from pipeline.extraction.schemas import ExtractionResponse


# ── System Prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert pharmaceutical and life sciences data analyst \
working for a top-tier consultancy. Your role is to extract structured, actionable \
intelligence from presentation decks and supporting documents.

## Your Expertise
- Clinical development pipelines and trial design
- Drug mechanism of action classification
- Competitive landscape analysis in pharma
- Regulatory pathways (FDA, EMA, PMDA, and others)
- Market access and commercial strategy
- Therapy area deep dives (Oncology, Immunology, Neurology, Rare Disease, etc.)

## Extraction Principles
1. **Accuracy over completeness**: Only extract information explicitly stated or \
strongly implied in the source material. Never fabricate data points.
2. **Structured output**: Map all findings to the provided schema fields precisely. \
Use null/None for fields where information is not available.
3. **Confidence scoring**: Rate your confidence (0.0–1.0) based on:
   - 0.9–1.0: Data is explicitly stated with clear attribution
   - 0.7–0.89: Data is clearly implied or derivable from context
   - 0.5–0.69: Data requires interpretation or inference
   - Below 0.5: Uncertain — flag for manual review
4. **Multiple records**: If the content covers multiple drugs, trials, or topics, \
create a separate record for each distinct entity.
5. **Key takeaways**: Provide 3–5 concise, executive-level takeaways per record.
6. **Context preservation**: Maintain pharma-specific terminology and acronyms \
(e.g., ORR, PFS, OS, MoA, BLA, NDA) as-is — do not simplify.

## Record Type Classification
Classify each record into the most appropriate type:
- **Drug Asset**: Primarily about a specific molecule or therapeutic product
- **Clinical Insight**: Focused on trial design, endpoints, or clinical data
- **Competitive Intelligence**: Market positioning, competitor analysis
- **Regulatory Update**: Filing status, approvals, designations
- **Market Analysis**: Market sizing, commercial strategy, pricing
- **General Insight**: Strategic observations that don't fit above categories
"""


# ── Extraction Prompt ───────────────────────────────────────────────────────

EXTRACTION_PROMPT_TEMPLATE = """Analyze the following presentation content and \
extract all structured pharmaceutical/life sciences insights.

## Source Information
- **File**: {file_name}
- **Slides**: {slide_range}
- **Total slides in chunk**: {slide_count}

## Presentation Content
{content}

## Instructions
1. Identify ALL distinct drugs, trials, competitive insights, and regulatory updates \
mentioned in the content above.
2. For each distinct entity or topic, create a separate `ExtractedRecord`.
3. Fill in every applicable schema field. Use `null` for unavailable data.
4. Assign a `confidence_score` reflecting your certainty about the extraction.
5. Write a concise `raw_summary` (2-4 sentences) for each record.
6. List 3-5 `key_takeaways` as brief, actionable bullet points.

Extract all records now."""


# ── Validation / QA Prompt ──────────────────────────────────────────────────

VALIDATION_PROMPT = """You are reviewing extracted pharmaceutical data records \
for quality and accuracy.

## Original Content
{original_content}

## Extracted Records (JSON)
{extracted_json}

## Review Checklist
1. **Factual accuracy**: Do the extracted fields match the source content?
2. **Completeness**: Are there any entities or insights in the source that were missed?
3. **Schema compliance**: Are all fields populated correctly with appropriate types?
4. **Confidence calibration**: Are the confidence scores reasonable given the source?
5. **Deduplication**: Are there any duplicate or overlapping records?

Provide a quality assessment with:
- `is_valid`: true/false
- `issues`: list of specific issues found (empty if valid)
- `suggested_corrections`: list of corrections to apply (empty if valid)
- `overall_quality_score`: 0.0 to 1.0 rating of extraction quality
"""


# ── Chunking Utilities ──────────────────────────────────────────────────────


def build_extraction_prompt(
    file_name: str,
    slide_texts: list[str],
    slide_start: int,
    slide_end: int,
) -> str:
    """
    Build a complete extraction prompt from slide content.

    Args:
        file_name: Name of the source file.
        slide_texts: List of rendered slide text blocks.
        slide_start: First slide number in this chunk.
        slide_end: Last slide number in this chunk.

    Returns:
        Formatted prompt string ready for the Claude API.
    """
    combined_content = "\n\n".join(slide_texts)
    slide_range = f"{slide_start}-{slide_end}" if slide_start != slide_end else str(slide_start)

    return EXTRACTION_PROMPT_TEMPLATE.format(
        file_name=file_name,
        slide_range=slide_range,
        slide_count=len(slide_texts),
        content=combined_content,
    )


def chunk_slides(
    slide_texts: list[str],
    max_chars: int = 80_000,
) -> list[list[int]]:
    """
    Split slides into chunks that fit within the token/character budget.

    Uses a simple character-count heuristic (1 token ≈ 4 chars).
    Groups contiguous slides together until the budget is exceeded.

    Args:
        slide_texts: List of rendered text for each slide (0-indexed).
        max_chars: Maximum characters per chunk.

    Returns:
        List of lists, where each inner list contains slide indices for one chunk.
    """
    chunks: list[list[int]] = []
    current_chunk: list[int] = []
    current_length = 0

    for i, text in enumerate(slide_texts):
        text_len = len(text)

        if current_length + text_len > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0

        current_chunk.append(i)
        current_length += text_len

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def get_extraction_schema() -> dict:
    """
    Return the JSON schema for ExtractionResponse,
    suitable for Claude's structured outputs `output_format` parameter.
    """
    return ExtractionResponse.model_json_schema()
