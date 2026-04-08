"""
Pipeline Orchestrator — End-to-end runner for the AI pharma extraction pipeline.

Coordinates: file discovery → PPTX parsing → Claude extraction →
validation → Airtable writing, with structured logging and CLI interface.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table as RichTable

from config.settings import settings, PROJECT_ROOT
from pipeline.ingestion.file_manager import FileManager, FileRecord
from pipeline.ingestion.pptx_parser import PPTXParser, PresentationContent
from pipeline.extraction.claude_client import ClaudeClient
from pipeline.extraction.schemas import ExtractedRecord
from pipeline.validation.validator import RecordValidator, BatchValidationResult
from pipeline.output.airtable_writer import AirtableWriter, WriteResult

console = Console()
logger = logging.getLogger("pipeline")


# ── Pipeline Result ─────────────────────────────────────────────────────────


@dataclass
class PipelineResult:
    """Aggregated result from a full pipeline run."""

    started_at: str = ""
    completed_at: str = ""
    files_discovered: int = 0
    files_processed: int = 0
    files_failed: int = 0
    total_records_extracted: int = 0
    total_records_validated: int = 0
    total_records_written: int = 0
    file_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "files_discovered": self.files_discovered,
            "files_processed": self.files_processed,
            "files_failed": self.files_failed,
            "total_records_extracted": self.total_records_extracted,
            "total_records_validated": self.total_records_validated,
            "total_records_written": self.total_records_written,
            "file_results": self.file_results,
            "errors": self.errors,
        }

    def save_report(self, path: Path | None = None) -> Path:
        """Save the pipeline report to a JSON file."""
        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = PROJECT_ROOT / "logs" / f"pipeline_report_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path


# ── Orchestrator ────────────────────────────────────────────────────────────


class PipelineOrchestrator:
    """
    Orchestrates the full data extraction pipeline.

    Usage:
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run()
    """

    def __init__(
        self,
        dry_run: bool | None = None,
        verbose: bool = False,
        enable_vision: bool | None = None,
    ):
        self.dry_run = dry_run if dry_run is not None else settings.dry_run
        self.verbose = verbose
        self.enable_vision = (
            enable_vision if enable_vision is not None else settings.enable_vision
        )

        # Initialize components
        self.file_manager = FileManager()
        self.parser = PPTXParser()
        self.validator = RecordValidator()

        # Claude client and Airtable writer are initialized lazily
        # to avoid API key errors during dry-run or testing
        self._claude_client: ClaudeClient | None = None
        self._airtable_writer: AirtableWriter | None = None

    @property
    def claude_client(self) -> ClaudeClient:
        if self._claude_client is None:
            self._claude_client = ClaudeClient()
        return self._claude_client

    @property
    def airtable_writer(self) -> AirtableWriter:
        if self._airtable_writer is None:
            self._airtable_writer = AirtableWriter(dry_run=self.dry_run)
        return self._airtable_writer

    # ── Public API ──────────────────────────────────────────────────────

    def run(self, file_path: str | None = None) -> PipelineResult:
        """
        Run the full extraction pipeline.

        Args:
            file_path: Optional path to a specific .pptx file.
                       If None, discovers all files in the input directory.

        Returns:
            PipelineResult with complete execution summary.
        """
        result = PipelineResult(
            started_at=datetime.now(timezone.utc).isoformat()
        )

        self._print_header()

        try:
            # Step 1: Discover files
            if file_path:
                files = self._single_file(file_path)
            else:
                files = self.file_manager.discover_files()

            result.files_discovered = len(files)

            if not files:
                console.print("[yellow]No files to process.[/yellow]")
                result.completed_at = datetime.now(timezone.utc).isoformat()
                return result

            console.print(f"[green]Found {len(files)} file(s) to process[/green]\n")

            # Step 2–5: Process each file
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task = progress.add_task("Processing files...", total=len(files))

                for file_record in files:
                    file_result = self._process_file(file_record)
                    result.file_results.append(file_result)

                    if file_result["status"] == "completed":
                        result.files_processed += 1
                        result.total_records_extracted += file_result["records_extracted"]
                        result.total_records_validated += file_result["records_validated"]
                        result.total_records_written += file_result["records_written"]
                    else:
                        result.files_failed += 1
                        if file_result.get("error"):
                            result.errors.append(
                                f"{file_record.file_name}: {file_result['error']}"
                            )

                    progress.update(task, advance=1)

        except Exception as e:
            logger.error("Pipeline failed: %s", e, exc_info=True)
            result.errors.append(f"Pipeline error: {e}")

        result.completed_at = datetime.now(timezone.utc).isoformat()

        # Print summary
        self._print_summary(result)

        # Save report
        report_path = result.save_report()
        console.print(f"\n[dim]Report saved to: {report_path}[/dim]")

        return result

    # ── Private: File Processing ────────────────────────────────────────

    def _process_file(self, file_record: FileRecord) -> dict[str, Any]:
        """Process a single file through the full pipeline."""
        file_result: dict[str, Any] = {
            "file_name": file_record.file_name,
            "status": "failed",
            "records_extracted": 0,
            "records_validated": 0,
            "records_written": 0,
            "error": None,
        }

        try:
            self.file_manager.mark_processing(file_record)

            # Step 2: Parse PPTX
            console.print(f"  📄 Parsing: [cyan]{file_record.file_name}[/cyan]")
            presentation = self.parser.parse(file_record.file_path)
            console.print(
                f"     → {presentation.total_slides} slides, "
                f"{len(presentation.content_slides)} with content"
            )

            if not presentation.content_slides:
                console.print("     → [yellow]No content slides found, skipping[/yellow]")
                self.file_manager.mark_completed(file_record, records_extracted=0)
                file_result["status"] = "completed"
                return file_result

            # Step 3: Extract via Claude
            console.print("  🤖 Extracting insights via Claude...")
            cost_est = self.claude_client.estimate_cost(presentation)
            console.print(
                f"     → Estimated cost: ${cost_est['estimated_cost_usd']:.4f}"
            )

            records = self.claude_client.extract(
                presentation, enable_vision=self.enable_vision
            )
            file_result["records_extracted"] = len(records)
            console.print(f"     → Extracted {len(records)} record(s)")

            if not records:
                console.print("     → [yellow]No records extracted[/yellow]")
                self.file_manager.mark_completed(file_record, records_extracted=0)
                file_result["status"] = "completed"
                return file_result

            # Step 4: Validate
            console.print("  ✅ Validating records...")
            validation = self.validator.validate_batch(records)
            valid_records = validation.valid_records
            file_result["records_validated"] = len(valid_records)

            summary = validation.summary()
            console.print(
                f"     → {summary['valid']} valid, "
                f"{summary['invalid']} invalid, "
                f"{summary['duplicates_removed']} duplicates"
            )

            if not valid_records:
                console.print("     → [yellow]No valid records after validation[/yellow]")
                self.file_manager.mark_completed(file_record, records_extracted=0)
                file_result["status"] = "completed"
                return file_result

            # Step 5: Write to Airtable
            mode = "DRY RUN" if self.dry_run else "Writing"
            console.print(f"  📊 {mode}: {len(valid_records)} record(s) to Airtable...")

            # Delete existing records for this file (upsert behavior)
            if not self.dry_run:
                deleted = self.airtable_writer.delete_existing(file_record.file_name)
                if deleted:
                    console.print(f"     → Replaced {deleted} existing record(s)")

            write_result = self.airtable_writer.write_records(valid_records)
            file_result["records_written"] = write_result.written
            console.print(f"     → Wrote {write_result.written} record(s)")

            # Mark completed
            self.file_manager.mark_completed(
                file_record, records_extracted=len(valid_records)
            )
            if not self.dry_run:
                self.file_manager.move_to_processed(file_record)

            file_result["status"] = "completed"

        except Exception as e:
            logger.error(
                "Failed processing %s: %s", file_record.file_name, e, exc_info=True
            )
            file_result["error"] = str(e)
            self.file_manager.mark_failed(file_record, str(e))
            if not self.dry_run:
                self.file_manager.move_to_failed(file_record)

        return file_result

    def _single_file(self, file_path: str) -> list[FileRecord]:
        """Create a FileRecord for a single file path."""
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        import hashlib

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        return [
            FileRecord(
                file_name=path.name,
                file_path=str(path),
                sha256=hasher.hexdigest(),
            )
        ]

    # ── Private: Display ────────────────────────────────────────────────

    def _print_header(self) -> None:
        mode = "[bold red]DRY RUN[/bold red]" if self.dry_run else "[bold green]LIVE[/bold green]"
        console.print(
            Panel(
                f"[bold]AI Pharma Data Extraction Pipeline[/bold]\n"
                f"Mode: {mode}  |  Model: [cyan]{settings.claude_model}[/cyan]\n"
                f"Vision: {'✅' if self.enable_vision else '❌'}  |  "
                f"Confidence threshold: {settings.confidence_threshold}",
                title="🧬 Pipeline Runner",
                border_style="bright_blue",
            )
        )

    def _print_summary(self, result: PipelineResult) -> None:
        table = RichTable(
            title="📋 Pipeline Summary",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", justify="right", style="green")

        table.add_row("Files Discovered", str(result.files_discovered))
        table.add_row("Files Processed", str(result.files_processed))
        table.add_row("Files Failed", str(result.files_failed))
        table.add_row("─" * 28, "─" * 8)
        table.add_row("Records Extracted", str(result.total_records_extracted))
        table.add_row("Records Validated", str(result.total_records_validated))
        table.add_row("Records Written", str(result.total_records_written))

        if result.errors:
            table.add_row("─" * 28, "─" * 8)
            table.add_row("Errors", str(len(result.errors)))

        console.print(table)


# ── CLI Interface ───────────────────────────────────────────────────────────


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging with Rich."""
    level = logging.DEBUG if verbose else getattr(logging, settings.log_level, logging.INFO)

    # Console handler (Rich)
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=True,
        show_path=verbose,
    )

    # File handler
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / "pipeline.log", encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(rich_handler)
    root_logger.addHandler(file_handler)


@click.command()
@click.option(
    "--file", "-f",
    type=click.Path(exists=True),
    help="Process a specific .pptx file instead of scanning the input directory.",
)
@click.option(
    "--dry-run", "-d",
    is_flag=True,
    default=False,
    help="Run without writing to Airtable (outputs to console/log).",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) logging.",
)
@click.option(
    "--vision/--no-vision",
    default=None,
    help="Enable/disable vision-based image analysis.",
)
def main(
    file: str | None,
    dry_run: bool,
    verbose: bool,
    vision: bool | None,
):
    """
    🧬 AI Pharma Data Extraction Pipeline

    Extracts structured pharmaceutical insights from PowerPoint decks
    using Claude AI, validates the output, and writes to Airtable.
    """
    setup_logging(verbose)

    orchestrator = PipelineOrchestrator(
        dry_run=dry_run,
        verbose=verbose,
        enable_vision=vision,
    )

    result = orchestrator.run(file_path=file)

    # Exit code
    if result.errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
