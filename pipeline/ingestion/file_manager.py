"""
File Manager — Handles file discovery, staging, deduplication, and state tracking.

Scans the input directory for .pptx files, tracks processing state via a
JSON manifest, and moves files to processed/failed directories on completion.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from config.settings import settings

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = ".processing_manifest.json"


@dataclass
class FileRecord:
    """Tracks the processing state of a single file."""

    file_name: str
    file_path: str
    sha256: str
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    discovered_at: str = ""
    processed_at: str | None = None
    error_message: str | None = None
    records_extracted: int = 0

    def __post_init__(self):
        if not self.discovered_at:
            self.discovered_at = datetime.now(timezone.utc).isoformat()


class FileManager:
    """
    Discovers, deduplicates, and tracks .pptx files through the pipeline.

    Usage:
        fm = FileManager()
        pending = fm.discover_files()
        for record in pending:
            fm.mark_processing(record)
            # ... process ...
            fm.mark_completed(record, records_extracted=5)
            fm.move_to_processed(record)
    """

    def __init__(
        self,
        input_dir: Path | None = None,
        processed_dir: Path | None = None,
        failed_dir: Path | None = None,
    ):
        self.input_dir = input_dir or settings.input_dir
        self.processed_dir = processed_dir or settings.processed_dir
        self.failed_dir = failed_dir or settings.failed_dir
        self.manifest_path = self.input_dir / MANIFEST_FILENAME
        self._manifest: dict[str, FileRecord] = {}
        self._load_manifest()

    # ── Public API ──────────────────────────────────────────────────────

    def discover_files(self) -> list[FileRecord]:
        """
        Scan the input directory for new .pptx files.
        Returns a list of FileRecord objects for files not yet processed.
        """
        self.input_dir.mkdir(parents=True, exist_ok=True)

        pptx_files = sorted(self.input_dir.glob("*.pptx"))
        new_files: list[FileRecord] = []

        for fpath in pptx_files:
            sha = self._compute_hash(fpath)

            # Skip if already in manifest (deduplicate by hash)
            if sha in self._manifest:
                existing = self._manifest[sha]
                if existing.status in ("completed", "processing"):
                    logger.debug("Skipping already-processed file: %s", fpath.name)
                    continue
                # If previously failed, allow retry
                if existing.status == "failed":
                    logger.info("Retrying previously failed file: %s", fpath.name)
                    existing.status = "pending"
                    existing.error_message = None
                    new_files.append(existing)
                    continue

            record = FileRecord(
                file_name=fpath.name,
                file_path=str(fpath.resolve()),
                sha256=sha,
            )
            self._manifest[sha] = record
            new_files.append(record)

        self._save_manifest()
        logger.info(
            "Discovered %d new file(s) in %s (total tracked: %d)",
            len(new_files),
            self.input_dir,
            len(self._manifest),
        )
        return new_files

    def mark_processing(self, record: FileRecord) -> None:
        """Mark a file as currently being processed."""
        record.status = "processing"
        self._save_manifest()
        logger.info("Processing: %s", record.file_name)

    def mark_completed(self, record: FileRecord, records_extracted: int = 0) -> None:
        """Mark a file as successfully processed."""
        record.status = "completed"
        record.processed_at = datetime.now(timezone.utc).isoformat()
        record.records_extracted = records_extracted
        self._save_manifest()
        logger.info(
            "Completed: %s (%d records extracted)",
            record.file_name,
            records_extracted,
        )

    def mark_failed(self, record: FileRecord, error: str) -> None:
        """Mark a file as failed with an error message."""
        record.status = "failed"
        record.processed_at = datetime.now(timezone.utc).isoformat()
        record.error_message = error
        self._save_manifest()
        logger.error("Failed: %s — %s", record.file_name, error)

    def move_to_processed(self, record: FileRecord) -> None:
        """Move a completed file from input/ to processed/."""
        self._move_file(record, self.processed_dir)

    def move_to_failed(self, record: FileRecord) -> None:
        """Move a failed file from input/ to failed/."""
        self._move_file(record, self.failed_dir)

    def get_summary(self) -> dict[str, int]:
        """Return a summary of file processing states."""
        summary: dict[str, int] = {
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
        }
        for record in self._manifest.values():
            summary[record.status] = summary.get(record.status, 0) + 1
        return summary

    # ── Private Helpers ─────────────────────────────────────────────────

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _move_file(self, record: FileRecord, dest_dir: Path) -> None:
        """Move a file to the destination directory."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        src = Path(record.file_path)
        if src.exists():
            dest = dest_dir / src.name
            # Handle name collisions
            counter = 1
            while dest.exists():
                dest = dest_dir / f"{src.stem}_{counter}{src.suffix}"
                counter += 1
            shutil.move(str(src), str(dest))
            record.file_path = str(dest.resolve())
            self._save_manifest()
            logger.info("Moved %s → %s", src.name, dest)

    def _load_manifest(self) -> None:
        """Load the processing manifest from disk."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._manifest = {
                    k: FileRecord(**v) for k, v in data.items()
                }
                logger.debug("Loaded manifest with %d entries", len(self._manifest))
            except Exception as e:
                logger.warning("Failed to load manifest, starting fresh: %s", e)
                self._manifest = {}
        else:
            self._manifest = {}

    def _save_manifest(self) -> None:
        """Persist the processing manifest to disk."""
        try:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: asdict(v) for k, v in self._manifest.items()}
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save manifest: %s", e)
