"""
Centralized configuration for the AI Pharma Data Extraction Pipeline.
All modules import settings from this file.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


# Project root is two levels up from this file (config/settings.py → Project_skeleton/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Pipeline configuration loaded from environment variables / .env file."""

    # ── Anthropic (Claude API) ──────────────────────────────────────────
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude access",
    )
    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model identifier to use for extraction",
    )

    # ── Airtable ────────────────────────────────────────────────────────
    airtable_personal_access_token: str = Field(
        default="",
        description="Airtable Personal Access Token",
    )
    airtable_base_id: str = Field(
        default="",
        description="Airtable Base ID",
    )
    airtable_table_name: str = Field(
        default="Extracted Records",
        description="Target table name in Airtable",
    )

    # ── File Paths ──────────────────────────────────────────────────────
    input_dir: Path = Field(default=PROJECT_ROOT / "data" / "input")
    processed_dir: Path = Field(default=PROJECT_ROOT / "data" / "processed")
    failed_dir: Path = Field(default=PROJECT_ROOT / "data" / "failed")

    # ── Pipeline Settings ───────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    max_retries: int = Field(default=3)
    confidence_threshold: float = Field(
        default=0.6,
        description="Minimum confidence score to accept an extracted record",
    )
    dry_run: bool = Field(
        default=False,
        description="If True, skip Airtable writes and print output instead",
    )
    enable_vision: bool = Field(
        default=False,
        description="If True, send slide images to Claude for chart/graph analysis",
    )

    # ── Pydantic-Settings Config ────────────────────────────────────────
    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton instance — import this everywhere
settings = Settings()
