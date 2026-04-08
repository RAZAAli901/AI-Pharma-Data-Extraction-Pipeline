"""
Test suite for the validation module.
"""

import pytest
from pipeline.extraction.schemas import (
    DrugAsset,
    ExtractedRecord,
    RecordType,
)
from pipeline.validation.validator import RecordValidator, ValidationResult


def make_record(**overrides) -> ExtractedRecord:
    """Helper to create a test record with sensible defaults."""
    defaults = {
        "source_file": "test.pptx",
        "slide_range": "1-5",
        "extraction_timestamp": "2025-01-01T00:00:00Z",
        "record_type": RecordType.DRUG_ASSET,
        "confidence_score": 0.85,
        "raw_summary": "This is a test summary with enough length.",
        "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
        "drug_asset": DrugAsset(molecule_name="TestDrug", sponsor_company="TestCo"),
    }
    defaults.update(overrides)
    return ExtractedRecord(**defaults)


class TestRecordValidator:
    """Tests for the RecordValidator."""

    def setup_method(self):
        self.validator = RecordValidator(confidence_threshold=0.6)

    def test_valid_record_passes(self):
        record = make_record()
        result = self.validator.validate_single(record)
        assert result.is_valid is True
        assert result.error_count == 0

    def test_low_confidence_fails(self):
        record = make_record(confidence_score=0.3)
        result = self.validator.validate_single(record)
        assert result.is_valid is False
        assert any(i.field == "confidence_score" for i in result.issues)

    def test_missing_summary_fails(self):
        record = make_record(raw_summary="Short")
        result = self.validator.validate_single(record)
        assert result.is_valid is False
        assert any(i.field == "raw_summary" for i in result.issues)

    def test_missing_source_file_fails(self):
        record = make_record(source_file="")
        result = self.validator.validate_single(record)
        assert result.is_valid is False

    def test_empty_takeaways_warning(self):
        record = make_record(key_takeaways=[])
        result = self.validator.validate_single(record)
        # Should be a warning, not an error, so still valid
        assert result.is_valid is True
        assert result.warning_count > 0

    def test_record_type_consistency_warning(self):
        """Drug Asset type but no drug_asset data triggers warning."""
        record = make_record(
            record_type=RecordType.DRUG_ASSET,
            drug_asset=None,
        )
        result = self.validator.validate_single(record)
        assert any(
            i.field == "record_type" and i.severity == "warning"
            for i in result.issues
        )

    def test_batch_validation(self):
        records = [make_record(), make_record(confidence_score=0.3)]
        batch_result = self.validator.validate_batch(records)
        assert batch_result.total == 2
        assert batch_result.valid_count == 1
        assert batch_result.invalid_count == 1

    def test_deduplication(self):
        """Two records with same drug name + company should be deduplicated."""
        records = [
            make_record(
                drug_asset=DrugAsset(molecule_name="DrugX", sponsor_company="CompanyA"),
                raw_summary="First summary about DrugX."
            ),
            make_record(
                drug_asset=DrugAsset(molecule_name="DrugX", sponsor_company="CompanyA"),
                raw_summary="Second summary about DrugX."
            ),
        ]
        batch_result = self.validator.validate_batch(records)
        assert batch_result.duplicates_removed == 1
        assert batch_result.valid_count == 1

    def test_no_deduplication_different_drugs(self):
        records = [
            make_record(
                drug_asset=DrugAsset(molecule_name="DrugA", sponsor_company="Co1"),
                raw_summary="DrugA is an oncology compound in Phase III development.",
            ),
            make_record(
                drug_asset=DrugAsset(molecule_name="DrugB", sponsor_company="Co2"),
                raw_summary="DrugB is an immunology biologic with novel mechanism.",
            ),
        ]
        batch_result = self.validator.validate_batch(records)
        assert batch_result.duplicates_removed == 0
        assert batch_result.valid_count == 2

    def test_summary_dict(self):
        records = [make_record()]
        batch_result = self.validator.validate_batch(records)
        summary = batch_result.summary()
        assert "total_records" in summary
        assert "valid" in summary
        assert "duplicates_removed" in summary
