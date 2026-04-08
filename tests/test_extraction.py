"""
Test suite for the extraction layer — schemas and prompts.
"""

import pytest
from pipeline.extraction.schemas import (
    DrugAsset,
    ClinicalInsight,
    CompetitiveIntelligence,
    RegulatoryUpdate,
    ExtractedRecord,
    ExtractionResponse,
    RecordType,
    TrialPhase,
    TrialStatus,
    RegulatoryAuthority,
)
from pipeline.extraction.prompts import (
    build_extraction_prompt,
    chunk_slides,
    get_extraction_schema,
)


class TestSchemas:
    """Tests for the Pydantic extraction schemas."""

    def test_drug_asset_minimal(self):
        da = DrugAsset(molecule_name="Pembrolizumab")
        assert da.molecule_name == "Pembrolizumab"
        assert da.mechanism_of_action is None

    def test_drug_asset_full(self):
        da = DrugAsset(
            molecule_name="Pembrolizumab",
            mechanism_of_action="PD-1 inhibitor",
            drug_class="Monoclonal antibody",
            sponsor_company="Merck",
            therapy_area="Oncology",
            indication="NSCLC",
            route_of_administration="IV",
        )
        assert da.therapy_area == "Oncology"

    def test_clinical_insight_enums(self):
        ci = ClinicalInsight(
            trial_phase=TrialPhase.PHASE_3,
            trial_status=TrialStatus.RECRUITING,
            primary_endpoints=["PFS", "OS"],
        )
        assert ci.trial_phase == TrialPhase.PHASE_3
        assert len(ci.primary_endpoints) == 2

    def test_extracted_record_confidence_validation(self):
        """Confidence score must be between 0 and 1."""
        with pytest.raises(Exception):
            ExtractedRecord(
                source_file="test.pptx",
                slide_range="1-5",
                extraction_timestamp="2025-01-01T00:00:00Z",
                record_type=RecordType.DRUG_ASSET,
                confidence_score=1.5,  # Invalid
                raw_summary="Test",
                key_takeaways=[],
            )

    def test_extracted_record_valid(self):
        record = ExtractedRecord(
            source_file="test.pptx",
            slide_range="1-5",
            extraction_timestamp="2025-01-01T00:00:00Z",
            record_type=RecordType.DRUG_ASSET,
            confidence_score=0.85,
            raw_summary="A drug in Phase III",
            key_takeaways=["Strong efficacy data"],
            drug_asset=DrugAsset(molecule_name="TestDrug"),
        )
        assert record.confidence_score == 0.85
        assert record.drug_asset.molecule_name == "TestDrug"

    def test_extraction_response(self):
        response = ExtractionResponse(records=[
            ExtractedRecord(
                source_file="deck.pptx",
                slide_range="1",
                extraction_timestamp="2025-01-01T00:00:00Z",
                record_type=RecordType.GENERAL_INSIGHT,
                confidence_score=0.7,
                raw_summary="Test summary",
                key_takeaways=["Point 1"],
            )
        ])
        assert len(response.records) == 1

    def test_extraction_response_json_schema(self):
        schema = ExtractionResponse.model_json_schema()
        assert "records" in schema.get("properties", {})


class TestPrompts:
    """Tests for prompt templates and utilities."""

    def test_build_extraction_prompt(self):
        prompt = build_extraction_prompt(
            file_name="test.pptx",
            slide_texts=["Slide 1 content", "Slide 2 content"],
            slide_start=1,
            slide_end=2,
        )
        assert "test.pptx" in prompt
        assert "1-2" in prompt
        assert "Slide 1 content" in prompt

    def test_build_extraction_prompt_single_slide(self):
        prompt = build_extraction_prompt(
            file_name="test.pptx",
            slide_texts=["Content"],
            slide_start=5,
            slide_end=5,
        )
        assert "5" in prompt
        assert "5-5" not in prompt  # Single slide should not show range

    def test_chunk_slides_small(self):
        texts = ["Short text"] * 3
        chunks = chunk_slides(texts, max_chars=1000)
        assert len(chunks) == 1
        assert chunks[0] == [0, 1, 2]

    def test_chunk_slides_split(self):
        texts = ["x" * 500] * 5
        chunks = chunk_slides(texts, max_chars=1200)
        assert len(chunks) >= 2

    def test_chunk_slides_empty(self):
        chunks = chunk_slides([], max_chars=1000)
        assert chunks == []

    def test_get_extraction_schema(self):
        schema = get_extraction_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
