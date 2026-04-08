"""
Validator — Post-extraction validation, business rules, and deduplication.

Enforces schema compliance, confidence thresholds, required fields,
and fuzzy deduplication across extracted records.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from config.settings import settings
from pipeline.extraction.schemas import ExtractedRecord, RecordType

logger = logging.getLogger(__name__)


# ── Validation Result ───────────────────────────────────────────────────────


@dataclass
class ValidationIssue:
    """A single validation issue found in a record."""

    field: str
    severity: str  # "error", "warning", "info"
    message: str


@dataclass
class ValidationResult:
    """Result of validating a single record."""

    record: ExtractedRecord
    is_valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


@dataclass
class BatchValidationResult:
    """Result of validating an entire batch of records."""

    results: list[ValidationResult] = field(default_factory=list)
    duplicates_removed: int = 0

    @property
    def valid_records(self) -> list[ExtractedRecord]:
        """Return only records that passed validation."""
        return [r.record for r in self.results if r.is_valid]

    @property
    def invalid_records(self) -> list[ValidationResult]:
        """Return results for records that failed validation."""
        return [r for r in self.results if not r.is_valid]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_records)

    def summary(self) -> dict:
        return {
            "total_records": self.total,
            "valid": self.valid_count,
            "invalid": self.invalid_count,
            "duplicates_removed": self.duplicates_removed,
            "errors": sum(r.error_count for r in self.results),
            "warnings": sum(r.warning_count for r in self.results),
        }


# ── Validator ───────────────────────────────────────────────────────────────


class RecordValidator:
    """
    Validates extracted records against business rules and schema constraints.

    Usage:
        validator = RecordValidator()
        result = validator.validate_batch(records)
        clean_records = result.valid_records
    """

    def __init__(
        self,
        confidence_threshold: float | None = None,
        similarity_threshold: float = 0.85,
    ):
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.confidence_threshold
        )
        self.similarity_threshold = similarity_threshold

    # ── Public API ──────────────────────────────────────────────────────

    def validate_batch(
        self, records: list[ExtractedRecord]
    ) -> BatchValidationResult:
        """
        Validate a batch of extracted records.

        Steps:
        1. Validate each record individually
        2. Deduplicate across the batch
        3. Return aggregated results
        """
        batch_result = BatchValidationResult()

        # Step 1: Individual validation
        for record in records:
            result = self._validate_record(record)
            batch_result.results.append(result)

        # Step 2: Deduplication (among valid records only)
        valid_results = [r for r in batch_result.results if r.is_valid]
        dedup_count = self._deduplicate(valid_results)
        batch_result.duplicates_removed = dedup_count

        # Log summary
        summary = batch_result.summary()
        logger.info(
            "Validation complete: %d total, %d valid, %d invalid, %d duplicates removed",
            summary["total_records"],
            summary["valid"],
            summary["invalid"],
            summary["duplicates_removed"],
        )

        return batch_result

    def validate_single(self, record: ExtractedRecord) -> ValidationResult:
        """Validate a single record."""
        return self._validate_record(record)

    # ── Private: Record Validation ──────────────────────────────────────

    def _validate_record(self, record: ExtractedRecord) -> ValidationResult:
        """Run all validation checks on a single record."""
        result = ValidationResult(record=record)

        self._check_confidence(record, result)
        self._check_required_fields(record, result)
        self._check_record_type_consistency(record, result)
        self._check_key_takeaways(record, result)
        self._check_summary(record, result)

        # Mark as invalid if there are any errors
        if result.error_count > 0:
            result.is_valid = False

        return result

    def _check_confidence(
        self, record: ExtractedRecord, result: ValidationResult
    ) -> None:
        """Check if confidence score meets the threshold."""
        if record.confidence_score < self.confidence_threshold:
            result.issues.append(
                ValidationIssue(
                    field="confidence_score",
                    severity="error",
                    message=(
                        f"Confidence {record.confidence_score:.2f} below "
                        f"threshold {self.confidence_threshold:.2f}"
                    ),
                )
            )

    def _check_required_fields(
        self, record: ExtractedRecord, result: ValidationResult
    ) -> None:
        """Check that essential fields are populated."""
        if not record.source_file:
            result.issues.append(
                ValidationIssue(
                    field="source_file",
                    severity="error",
                    message="Source file is missing",
                )
            )

        if not record.raw_summary or len(record.raw_summary.strip()) < 10:
            result.issues.append(
                ValidationIssue(
                    field="raw_summary",
                    severity="error",
                    message="Raw summary is missing or too short (< 10 chars)",
                )
            )

    def _check_record_type_consistency(
        self, record: ExtractedRecord, result: ValidationResult
    ) -> None:
        """Verify that the record type aligns with populated sub-models."""
        type_to_field = {
            RecordType.DRUG_ASSET: record.drug_asset,
            RecordType.CLINICAL_INSIGHT: record.clinical_insight,
            RecordType.COMPETITIVE_INTELLIGENCE: record.competitive_intel,
            RecordType.REGULATORY_UPDATE: record.regulatory_update,
        }

        expected_field = type_to_field.get(record.record_type)

        if expected_field is None and record.record_type in type_to_field:
            result.issues.append(
                ValidationIssue(
                    field="record_type",
                    severity="warning",
                    message=(
                        f"Record type is '{record.record_type.value}' but the "
                        f"corresponding data model is empty"
                    ),
                )
            )

    def _check_key_takeaways(
        self, record: ExtractedRecord, result: ValidationResult
    ) -> None:
        """Verify key takeaways are present and reasonable."""
        if len(record.key_takeaways) == 0:
            result.issues.append(
                ValidationIssue(
                    field="key_takeaways",
                    severity="warning",
                    message="No key takeaways provided",
                )
            )
        elif len(record.key_takeaways) > 10:
            result.issues.append(
                ValidationIssue(
                    field="key_takeaways",
                    severity="warning",
                    message=f"Too many key takeaways ({len(record.key_takeaways)}), expected 3-5",
                )
            )

    def _check_summary(
        self, record: ExtractedRecord, result: ValidationResult
    ) -> None:
        """Validate raw summary quality."""
        if record.raw_summary and len(record.raw_summary) > 2000:
            result.issues.append(
                ValidationIssue(
                    field="raw_summary",
                    severity="warning",
                    message=f"Summary is very long ({len(record.raw_summary)} chars), consider condensing",
                )
            )

    # ── Private: Deduplication ──────────────────────────────────────────

    def _deduplicate(self, results: list[ValidationResult]) -> int:
        """
        Remove near-duplicate records using fuzzy matching on key identifiers.
        Returns the number of duplicates removed.
        """
        if len(results) <= 1:
            return 0

        duplicates_found = 0
        seen: list[ValidationResult] = []

        for result in results:
            is_duplicate = False

            for seen_result in seen:
                if self._are_duplicates(result.record, seen_result.record):
                    result.is_valid = False
                    result.issues.append(
                        ValidationIssue(
                            field="duplicate",
                            severity="error",
                            message=(
                                f"Duplicate of record from slides "
                                f"{seen_result.record.slide_range}"
                            ),
                        )
                    )
                    is_duplicate = True
                    duplicates_found += 1
                    break

            if not is_duplicate:
                seen.append(result)

        return duplicates_found

    def _are_duplicates(self, a: ExtractedRecord, b: ExtractedRecord) -> bool:
        """Check if two records are near-duplicates."""
        # Must be same record type
        if a.record_type != b.record_type:
            return False

        # Compare drug names if both have drug assets
        if a.drug_asset and b.drug_asset:
            name_sim = self._similarity(
                a.drug_asset.molecule_name, b.drug_asset.molecule_name
            )
            if name_sim > self.similarity_threshold:
                # Also check if sponsor matches
                if a.drug_asset.sponsor_company and b.drug_asset.sponsor_company:
                    sponsor_sim = self._similarity(
                        a.drug_asset.sponsor_company, b.drug_asset.sponsor_company
                    )
                    if sponsor_sim > self.similarity_threshold:
                        return True
                else:
                    return True

        # Compare summaries as fallback
        summary_sim = self._similarity(a.raw_summary, b.raw_summary)
        if summary_sim > 0.90:
            return True

        return False

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Compute string similarity ratio (0.0 to 1.0)."""
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
