"""
Test suite for the Airtable writer module.
"""

import pytest
from unittest.mock import MagicMock, patch
from pipeline.extraction.schemas import (
    DrugAsset,
    ClinicalInsight,
    CompetitiveIntelligence,
    RegulatoryUpdate,
    ExtractedRecord,
    RecordType,
    TrialPhase,
    TrialStatus,
    RegulatoryAuthority,
)
from pipeline.output.airtable_writer import AirtableWriter, WriteResult


def make_full_record() -> ExtractedRecord:
    """Create a fully populated record for testing field mapping."""
    return ExtractedRecord(
        source_file="test_deck.pptx",
        slide_range="3-8",
        extraction_timestamp="2025-06-15T10:30:00Z",
        record_type=RecordType.DRUG_ASSET,
        confidence_score=0.92,
        raw_summary="Pembrolizumab shows strong OS benefit in NSCLC.",
        key_takeaways=[
            "Significant OS improvement vs SOC",
            "Favorable safety profile",
            "Potential for first-line monotherapy",
        ],
        drug_asset=DrugAsset(
            molecule_name="Pembrolizumab",
            mechanism_of_action="PD-1 inhibitor",
            drug_class="Monoclonal antibody",
            sponsor_company="Merck",
            therapy_area="Oncology",
            indication="NSCLC",
        ),
        clinical_insight=ClinicalInsight(
            trial_phase=TrialPhase.PHASE_3,
            trial_status=TrialStatus.ACTIVE,
            primary_endpoints=["OS", "PFS"],
            enrollment_target=800,
        ),
        competitive_intel=CompetitiveIntelligence(
            competitive_positioning="Best-in-class PD-1",
            competitors=["Nivolumab", "Atezolizumab"],
        ),
        regulatory_update=RegulatoryUpdate(
            approval_status="Approved",
            regulatory_authority=RegulatoryAuthority.FDA,
            designations=["Breakthrough Therapy"],
        ),
    )


class TestAirtableWriterDryRun:
    """Tests for AirtableWriter in dry-run mode (no API calls)."""

    def setup_method(self):
        self.writer = AirtableWriter(dry_run=True)

    def test_write_records_dry_run(self):
        records = [make_full_record()]
        result = self.writer.write_records(records)
        assert result.transformed == 1
        assert result.written == 1
        assert len(result.errors) == 0

    def test_write_empty_list(self):
        result = self.writer.write_records([])
        assert result.written == 0

    def test_field_mapping(self):
        record = make_full_record()
        fields = self.writer._record_to_fields(record)

        assert fields["Source File"] == "test_deck.pptx"
        assert fields["Molecule Name"] == "Pembrolizumab"
        assert fields["Therapy Area"] == "Oncology"
        assert fields["Trial Phase"] == "Phase III"
        assert fields["Confidence Score"] == 0.92
        assert "Breakthrough Therapy" in fields.get("Designations", "")
        assert "Nivolumab" in fields.get("Competitors", "")

    def test_field_mapping_minimal_record(self):
        record = ExtractedRecord(
            source_file="min.pptx",
            slide_range="1",
            extraction_timestamp="2025-01-01T00:00:00Z",
            record_type=RecordType.GENERAL_INSIGHT,
            confidence_score=0.7,
            raw_summary="General observation",
            key_takeaways=["Point 1"],
        )
        fields = self.writer._record_to_fields(record)
        assert fields["Source File"] == "min.pptx"
        assert "Molecule Name" not in fields
        assert "Trial Phase" not in fields


class TestWriteResult:
    """Tests for the WriteResult class."""

    def test_success_property(self):
        result = WriteResult()
        result.written = 5
        assert result.success is True

    def test_failure_with_errors(self):
        result = WriteResult()
        result.written = 3
        result.errors = ["Something went wrong"]
        assert result.success is False

    def test_failure_no_writes(self):
        result = WriteResult()
        assert result.success is False

    def test_summary(self):
        result = WriteResult()
        result.transformed = 5
        result.written = 4
        result.skipped = 1
        summary = result.summary()
        assert summary["transformed"] == 5
        assert summary["written"] == 4
