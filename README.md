# 🧬 AI Pharma Data Extraction Pipeline

> **AI-powered structured data extraction from pharmaceutical presentation decks.**
> Ingest `.pptx` files → Extract insights via Claude API → Validate → Write to Airtable

---

## Architecture

```
📁 Source Files (.pptx)
    ↓
🔍 Ingestion Engine (python-pptx)
    ↓  text, tables, images, metadata
🤖 Claude API Extraction Layer
    ↓  structured JSON (Pydantic models)
✅ Schema Validator
    ↓  confidence thresholds, dedup, business rules
📊 Airtable Writer (pyairtable)
    ↓
🖥️ Reporting Dashboard (HTML/JS/Chart.js)
```

## Quick Start

### 1. Install Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env
```

Edit `.env` with your credentials:
- `ANTHROPIC_API_KEY` — your Claude API key
- `AIRTABLE_PERSONAL_ACCESS_TOKEN` — Airtable PAT
- `AIRTABLE_BASE_ID` — target Airtable base
- `AIRTABLE_TABLE_NAME` — target table name

### 3. Add Source Files

Drop `.pptx` files into `data/input/`.

### 4. Run the Pipeline

```bash
# Full pipeline (discovers all files in data/input/)
python -m pipeline.orchestrator

# Process a single file
python -m pipeline.orchestrator --file path/to/deck.pptx

# Dry run (no Airtable writes)
python -m pipeline.orchestrator --dry-run

# Verbose logging
python -m pipeline.orchestrator --dry-run --verbose

# Enable vision (analyze charts/images)
python -m pipeline.orchestrator --vision
```

### 5. View the Dashboard

Open `dashboard/index.html` in your browser and load a pipeline report JSON from `logs/`.

---

## Project Structure

```
Project_skeleton/
├── config/settings.py          # Centralized configuration
├── pipeline/
│   ├── ingestion/
│   │   ├── pptx_parser.py      # PowerPoint parsing
│   │   └── file_manager.py     # File discovery & tracking
│   ├── extraction/
│   │   ├── schemas.py           # Pydantic data models
│   │   ├── prompts.py           # Claude prompt templates
│   │   └── claude_client.py     # Claude API wrapper
│   ├── validation/
│   │   └── validator.py         # Post-extraction validation
│   ├── output/
│   │   └── airtable_writer.py   # Airtable batch writer
│   └── orchestrator.py          # End-to-end pipeline runner
├── dashboard/                   # Web reporting interface
├── tests/                       # Pytest test suite
├── data/
│   ├── input/                   # Drop .pptx files here
│   ├── processed/               # Successfully processed files
│   └── failed/                  # Files that failed extraction
└── logs/                        # Pipeline logs & reports
```

## Data Schema

The pipeline extracts records conforming to these Pydantic models:

| Model | Fields |
|-------|--------|
| **DrugAsset** | molecule_name, MoA, drug_class, sponsor, therapy_area, indication, route |
| **ClinicalInsight** | trial_phase, status, identifier, endpoints, population, enrollment, efficacy, safety |
| **CompetitiveIntelligence** | positioning, landscape, differentiators, competitors, market_size, strategy |
| **RegulatoryUpdate** | approval_status, authority, dates, designations, PDUFA |

Each `ExtractedRecord` wraps one or more of these sub-models with source tracking, confidence scoring, key takeaways, and a summary.

## CLI Options

| Flag | Description |
|------|-------------|
| `--file`, `-f` | Process a specific .pptx file |
| `--dry-run`, `-d` | Skip Airtable writes |
| `--verbose`, `-v` | Enable DEBUG logging |
| `--vision` / `--no-vision` | Enable/disable image analysis |

## Running Tests

```bash
pytest tests/ -v
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `CLAUDE_MODEL` | No | claude-sonnet-4-20250514 | Model identifier |
| `AIRTABLE_PERSONAL_ACCESS_TOKEN` | Yes* | — | Airtable PAT |
| `AIRTABLE_BASE_ID` | Yes* | — | Airtable Base ID |
| `AIRTABLE_TABLE_NAME` | No | Extracted Records | Table name |
| `CONFIDENCE_THRESHOLD` | No | 0.6 | Min confidence to accept |
| `DRY_RUN` | No | false | Skip Airtable writes |
| `ENABLE_VISION` | No | false | Analyze slide images |

\* Required unless using `--dry-run` mode.

---

## License

Proprietary — Internal use only.
