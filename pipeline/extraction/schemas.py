"""
Pydantic schemas defining the target data extraction models for pharma consulting.

These models are used both as the target schema for Claude's structured outputs
and as the validation layer for extracted records.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────────


class TrialPhase(str, Enum):
    PRECLINICAL = "Preclinical"
    PHASE_1 = "Phase I"
    PHASE_1_2 = "Phase I/II"
    PHASE_2 = "Phase II"
    PHASE_2_3 = "Phase II/III"
    PHASE_3 = "Phase III"
    PHASE_3B = "Phase IIIb"
    PHASE_4 = "Phase IV"
    UNKNOWN = "Unknown"


class TrialStatus(str, Enum):
    NOT_YET_RECRUITING = "Not Yet Recruiting"
    RECRUITING = "Recruiting"
    ACTIVE = "Active, Not Recruiting"
    COMPLETED = "Completed"
    SUSPENDED = "Suspended"
    TERMINATED = "Terminated"
    WITHDRAWN = "Withdrawn"
    UNKNOWN = "Unknown"


class RegulatoryAuthority(str, Enum):
    FDA = "FDA"
    EMA = "EMA"
    PMDA = "PMDA"
    NMPA = "NMPA"
    MHRA = "MHRA"
    HEALTH_CANADA = "Health Canada"
    TGA = "TGA"
    OTHER = "Other"


class RecordType(str, Enum):
    DRUG_ASSET = "Drug Asset"
    CLINICAL_INSIGHT = "Clinical Insight"
    COMPETITIVE_INTELLIGENCE = "Competitive Intelligence"
    REGULATORY_UPDATE = "Regulatory Update"
    MARKET_ANALYSIS = "Market Analysis"
    GENERAL_INSIGHT = "General Insight"


# ── Sub-Models ──────────────────────────────────────────────────────────────


class DrugAsset(BaseModel):
    """Information about a specific drug or therapeutic asset."""

    molecule_name: str = Field(
        description="Name of the molecule, compound, or drug product"
    )
    mechanism_of_action: Optional[str] = Field(
        default=None,
        description="Mechanism of action (e.g., PD-1 inhibitor, EGFR TKI)",
    )
    drug_class: Optional[str] = Field(
        default=None,
        description="Therapeutic class (e.g., monoclonal antibody, small molecule)",
    )
    sponsor_company: Optional[str] = Field(
        default=None,
        description="Sponsoring pharmaceutical company or developer",
    )
    therapy_area: Optional[str] = Field(
        default=None,
        description="Primary therapy area (e.g., Oncology, Immunology, Neurology)",
    )
    indication: Optional[str] = Field(
        default=None,
        description="Specific indication or disease target",
    )
    route_of_administration: Optional[str] = Field(
        default=None,
        description="Route of administration (e.g., IV, oral, subcutaneous)",
    )


class ClinicalInsight(BaseModel):
    """Clinical trial and development data."""

    trial_phase: Optional[TrialPhase] = Field(
        default=None,
        description="Current phase of clinical development",
    )
    trial_status: Optional[TrialStatus] = Field(
        default=None,
        description="Current recruitment / activity status of the trial",
    )
    trial_identifier: Optional[str] = Field(
        default=None,
        description="Trial identifier (e.g., NCT number)",
    )
    primary_endpoints: list[str] = Field(
        default_factory=list,
        description="Primary efficacy or safety endpoints",
    )
    secondary_endpoints: list[str] = Field(
        default_factory=list,
        description="Secondary or exploratory endpoints",
    )
    patient_population: Optional[str] = Field(
        default=None,
        description="Target patient population description",
    )
    enrollment_target: Optional[int] = Field(
        default=None,
        description="Target enrollment number",
    )
    efficacy_data: Optional[str] = Field(
        default=None,
        description="Key efficacy results or data readouts if available",
    )
    safety_signals: Optional[str] = Field(
        default=None,
        description="Notable safety observations or signals",
    )


class CompetitiveIntelligence(BaseModel):
    """Competitive landscape and market positioning data."""

    competitive_positioning: Optional[str] = Field(
        default=None,
        description="How the asset is positioned versus competitors",
    )
    market_landscape: Optional[str] = Field(
        default=None,
        description="Overview of the competitive market landscape",
    )
    key_differentiators: list[str] = Field(
        default_factory=list,
        description="Key differentiating factors vs. competition",
    )
    strategic_implications: Optional[str] = Field(
        default=None,
        description="Strategic implications or recommendations",
    )
    competitors: list[str] = Field(
        default_factory=list,
        description="Named competitor drugs or companies",
    )
    market_size_estimate: Optional[str] = Field(
        default=None,
        description="Estimated market size or revenue potential",
    )


class RegulatoryUpdate(BaseModel):
    """Regulatory filing and approval data."""

    approval_status: Optional[str] = Field(
        default=None,
        description="Current approval status (e.g., Approved, Filed, Under Review)",
    )
    regulatory_authority: Optional[RegulatoryAuthority] = Field(
        default=None,
        description="Regulatory body (FDA, EMA, etc.)",
    )
    submission_date: Optional[str] = Field(
        default=None,
        description="Date of regulatory submission (ISO format if available)",
    )
    approval_date: Optional[str] = Field(
        default=None,
        description="Date of approval (ISO format if available)",
    )
    designations: list[str] = Field(
        default_factory=list,
        description="Special designations (Orphan Drug, Breakthrough Therapy, Fast Track, etc.)",
    )
    pdufa_date: Optional[str] = Field(
        default=None,
        description="PDUFA action date if applicable",
    )


# ── Top-Level Extraction Record ────────────────────────────────────────────


class ExtractedRecord(BaseModel):
    """
    Top-level record produced by the AI extraction pipeline.
    Each record represents structured insights from a portion of a presentation.
    """

    # ── Source Tracking ──
    source_file: str = Field(description="Name of the source .pptx file")
    slide_range: str = Field(
        description="Slide range this record was extracted from (e.g., '1-5', '12')"
    )
    extraction_timestamp: str = Field(
        description="ISO timestamp of when extraction was performed"
    )
    record_type: RecordType = Field(
        description="Primary type/category of this extracted record"
    )

    # ── Confidence ──
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="AI confidence in the extraction accuracy (0.0 to 1.0)",
    )

    # ── Structured Data ──
    drug_asset: Optional[DrugAsset] = Field(
        default=None,
        description="Drug/asset information if applicable",
    )
    clinical_insight: Optional[ClinicalInsight] = Field(
        default=None,
        description="Clinical trial data if applicable",
    )
    competitive_intel: Optional[CompetitiveIntelligence] = Field(
        default=None,
        description="Competitive intelligence if applicable",
    )
    regulatory_update: Optional[RegulatoryUpdate] = Field(
        default=None,
        description="Regulatory status if applicable",
    )

    # ── Summary ──
    key_takeaways: list[str] = Field(
        default_factory=list,
        description="Top 3-5 key takeaways from this section",
    )
    raw_summary: str = Field(
        description="Free-text summary of the extracted content",
    )


class ExtractionResponse(BaseModel):
    """
    Wrapper for the full extraction response from Claude.
    Contains one or more ExtractedRecord objects from a single API call.
    """

    records: list[ExtractedRecord] = Field(
        description="List of structured records extracted from the presentation content"
    )
