"""
Airtable Writer — Writes validated extraction records to Airtable.

Handles field mapping, batch creation, upsert logic, and dry-run mode.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pyairtable import Api, Table
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings
from pipeline.extraction.schemas import ExtractedRecord

logger = logging.getLogger(__name__)


class AirtableWriter:
    """
    Writes ExtractedRecord objects to an Airtable table.

    Usage:
        writer = AirtableWriter()
        results = writer.write_records(validated_records)

        # Dry-run mode (no writes):
        writer = AirtableWriter(dry_run=True)
        results = writer.write_records(validated_records)
    """

    # ── Field Mapping ───────────────────────────────────────────────────
    # Maps ExtractedRecord fields → Airtable column names.
    # Update this mapping to match your actual Airtable schema.
    FIELD_MAP = {
        # Core fields
        "source_file": "Source File",
        "slide_range": "Slide Range",
        "extraction_timestamp": "Extraction Timestamp",
        "record_type": "Record Type",
        "confidence_score": "Confidence Score",
        "raw_summary": "Summary",
        "key_takeaways": "Key Takeaways",
        # Drug Asset fields
        "molecule_name": "Molecule Name",
        "mechanism_of_action": "Mechanism of Action",
        "drug_class": "Drug Class",
        "sponsor_company": "Sponsor Company",
        "therapy_area": "Therapy Area",
        "indication": "Indication",
        "route_of_administration": "Route of Administration",
        # Clinical Insight fields
        "trial_phase": "Trial Phase",
        "trial_status": "Trial Status",
        "trial_identifier": "Trial Identifier",
        "primary_endpoints": "Primary Endpoints",
        "secondary_endpoints": "Secondary Endpoints",
        "patient_population": "Patient Population",
        "enrollment_target": "Enrollment Target",
        "efficacy_data": "Efficacy Data",
        "safety_signals": "Safety Signals",
        # Competitive Intelligence fields
        "competitive_positioning": "Competitive Positioning",
        "market_landscape": "Market Landscape",
        "key_differentiators": "Key Differentiators",
        "strategic_implications": "Strategic Implications",
        "competitors": "Competitors",
        "market_size_estimate": "Market Size Estimate",
        # Regulatory Update fields
        "approval_status": "Approval Status",
        "regulatory_authority": "Regulatory Authority",
        "submission_date": "Submission Date",
        "approval_date": "Approval Date",
        "designations": "Designations",
        "pdufa_date": "PDUFA Date",
    }

    def __init__(
        self,
        api_token: str | None = None,
        base_id: str | None = None,
        table_name: str | None = None,
        dry_run: bool | None = None,
    ):
        self._token = api_token or settings.airtable_personal_access_token
        self._base_id = base_id or settings.airtable_base_id
        self._table_name = table_name or settings.airtable_table_name
        self._dry_run = dry_run if dry_run is not None else settings.dry_run

        self._table: Table | None = None

        if not self._dry_run:
            if not self._token:
                raise ValueError(
                    "Airtable token not configured. "
                    "Set AIRTABLE_PERSONAL_ACCESS_TOKEN in .env"
                )
            if not self._base_id:
                raise ValueError(
                    "Airtable base ID not configured. "
                    "Set AIRTABLE_BASE_ID in .env"
                )
            api = Api(self._token)
            self._table = api.table(self._base_id, self._table_name)
            logger.info(
                "Airtable writer initialized (base: %s, table: %s)",
                self._base_id,
                self._table_name,
            )
        else:
            logger.info("Airtable writer initialized in DRY-RUN mode")

    # ── Public API ──────────────────────────────────────────────────────

    def write_records(
        self, records: list[ExtractedRecord]
    ) -> WriteResult:
        """
        Write a list of validated records to Airtable.

        Args:
            records: List of ExtractedRecord objects to write.

        Returns:
            WriteResult with success/failure counts and details.
        """
        if not records:
            logger.info("No records to write")
            return WriteResult()

        result = WriteResult()

        # Transform records to Airtable field dicts
        airtable_records = []
        for record in records:
            try:
                fields = self._record_to_fields(record)
                airtable_records.append(fields)
                result.transformed += 1
            except Exception as e:
                logger.error(
                    "Failed to transform record (%s): %s",
                    record.source_file,
                    e,
                )
                result.errors.append(f"Transform error: {e}")

        if self._dry_run:
            logger.info("DRY RUN: Would write %d records", len(airtable_records))
            for i, fields in enumerate(airtable_records, 1):
                logger.info("  Record %d: %s", i, json.dumps(fields, indent=2, default=str))
            result.written = len(airtable_records)
            return result

        # Batch write to Airtable
        result.written = self._batch_write(airtable_records, result)

        logger.info(
            "Write complete: %d transformed, %d written, %d errors",
            result.transformed,
            result.written,
            len(result.errors),
        )
        return result

    def check_existing(self, source_file: str) -> list[dict[str, Any]]:
        """
        Check for existing records from a given source file.
        Useful for upsert / deduplication logic.
        """
        if self._dry_run or not self._table:
            return []

        try:
            formula = f"{{Source File}} = '{source_file}'"
            existing = self._table.all(formula=formula)
            return existing
        except Exception as e:
            logger.warning("Failed to check existing records: %s", e)
            return []

    def delete_existing(self, source_file: str) -> int:
        """
        Delete all existing records from a given source file.
        Useful for re-processing a file from scratch.
        """
        if self._dry_run or not self._table:
            logger.info("DRY RUN: Would delete records for %s", source_file)
            return 0

        existing = self.check_existing(source_file)
        if not existing:
            return 0

        record_ids = [r["id"] for r in existing]
        try:
            self._table.batch_delete(record_ids)
            logger.info("Deleted %d existing records for %s", len(record_ids), source_file)
            return len(record_ids)
        except Exception as e:
            logger.error("Failed to delete existing records: %s", e)
            return 0

    # ── Private Helpers ─────────────────────────────────────────────────

    def _record_to_fields(self, record: ExtractedRecord) -> dict[str, Any]:
        """
        Transform an ExtractedRecord into a flat dict of Airtable fields.
        """
        fields: dict[str, Any] = {}

        # Core fields
        fields[self.FIELD_MAP["source_file"]] = record.source_file
        fields[self.FIELD_MAP["slide_range"]] = record.slide_range
        fields[self.FIELD_MAP["extraction_timestamp"]] = record.extraction_timestamp
        fields[self.FIELD_MAP["record_type"]] = record.record_type.value
        fields[self.FIELD_MAP["confidence_score"]] = record.confidence_score
        fields[self.FIELD_MAP["raw_summary"]] = record.raw_summary

        # Key takeaways as newline-separated text
        if record.key_takeaways:
            fields[self.FIELD_MAP["key_takeaways"]] = "\n".join(
                f"• {t}" for t in record.key_takeaways
            )

        # Drug Asset
        if record.drug_asset:
            da = record.drug_asset
            self._set_if_present(fields, "molecule_name", da.molecule_name)
            self._set_if_present(fields, "mechanism_of_action", da.mechanism_of_action)
            self._set_if_present(fields, "drug_class", da.drug_class)
            self._set_if_present(fields, "sponsor_company", da.sponsor_company)
            self._set_if_present(fields, "therapy_area", da.therapy_area)
            self._set_if_present(fields, "indication", da.indication)
            self._set_if_present(fields, "route_of_administration", da.route_of_administration)

        # Clinical Insight
        if record.clinical_insight:
            ci = record.clinical_insight
            self._set_if_present(
                fields, "trial_phase", ci.trial_phase.value if ci.trial_phase else None
            )
            self._set_if_present(
                fields, "trial_status", ci.trial_status.value if ci.trial_status else None
            )
            self._set_if_present(fields, "trial_identifier", ci.trial_identifier)
            if ci.primary_endpoints:
                fields[self.FIELD_MAP["primary_endpoints"]] = "\n".join(ci.primary_endpoints)
            if ci.secondary_endpoints:
                fields[self.FIELD_MAP["secondary_endpoints"]] = "\n".join(ci.secondary_endpoints)
            self._set_if_present(fields, "patient_population", ci.patient_population)
            self._set_if_present(fields, "enrollment_target", ci.enrollment_target)
            self._set_if_present(fields, "efficacy_data", ci.efficacy_data)
            self._set_if_present(fields, "safety_signals", ci.safety_signals)

        # Competitive Intelligence
        if record.competitive_intel:
            comp = record.competitive_intel
            self._set_if_present(fields, "competitive_positioning", comp.competitive_positioning)
            self._set_if_present(fields, "market_landscape", comp.market_landscape)
            if comp.key_differentiators:
                fields[self.FIELD_MAP["key_differentiators"]] = "\n".join(comp.key_differentiators)
            self._set_if_present(fields, "strategic_implications", comp.strategic_implications)
            if comp.competitors:
                fields[self.FIELD_MAP["competitors"]] = ", ".join(comp.competitors)
            self._set_if_present(fields, "market_size_estimate", comp.market_size_estimate)

        # Regulatory Update
        if record.regulatory_update:
            reg = record.regulatory_update
            self._set_if_present(fields, "approval_status", reg.approval_status)
            self._set_if_present(
                fields,
                "regulatory_authority",
                reg.regulatory_authority.value if reg.regulatory_authority else None,
            )
            self._set_if_present(fields, "submission_date", reg.submission_date)
            self._set_if_present(fields, "approval_date", reg.approval_date)
            if reg.designations:
                fields[self.FIELD_MAP["designations"]] = ", ".join(reg.designations)
            self._set_if_present(fields, "pdufa_date", reg.pdufa_date)

        return fields

    def _set_if_present(
        self, fields: dict[str, Any], key: str, value: Any
    ) -> None:
        """Set a field only if the value is not None."""
        if value is not None:
            airtable_key = self.FIELD_MAP.get(key, key)
            fields[airtable_key] = value

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def _batch_write(
        self, records: list[dict[str, Any]], result: WriteResult
    ) -> int:
        """Write records to Airtable using batch_create."""
        if not self._table:
            return 0

        try:
            created = self._table.batch_create(records, typecast=True)
            return len(created)
        except Exception as e:
            logger.error("Batch write failed: %s", e)
            result.errors.append(f"Batch write error: {e}")
            raise


# ── Write Result ────────────────────────────────────────────────────────────


class WriteResult:
    """Tracks the outcome of a write operation."""

    def __init__(self):
        self.transformed: int = 0
        self.written: int = 0
        self.skipped: int = 0
        self.errors: list[str] = []

    @property
    def success(self) -> bool:
        return self.written > 0 and len(self.errors) == 0

    def summary(self) -> dict:
        return {
            "transformed": self.transformed,
            "written": self.written,
            "skipped": self.skipped,
            "errors": self.errors,
        }
