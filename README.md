# SeismoSearch

> A tool-augmented RAG system for earthquake catalog search, seismology QA, evidence-grounded answers, and safety-bounded risk communication.

SeismoSearch combines structured event tools with document retrieval. It is designed for questions where a language model alone is not reliable enough: exact filtering belongs to DuckDB, domain explanations belong to the document retriever, and every generated answer is constrained by an auditable Evidence Pack.

## What it does

| Query type | Example | Execution path |
|---|---|---|
| `catalog` | List M6.5+ events in a time range | Planner → DuckDB event tools |
| `concept` | Explain magnitude, intensity, depth, or catalog fields | Planner → document retrieval |
| `mixed` | List events and explain their possible impact | Event tools + document retrieval |
| `safety` | Ask for a future earthquake prediction | Safety gate → bounded refusal |

The system does not predict future earthquakes and does not replace official monitoring or emergency guidance.

## Architecture

```text
User query
    │
    ▼
Safety Gate
    │
    ▼
Deterministic Planner
    │
    ├── Event tools ─────── DuckDB search and statistics
    ├── Document tools ──── keyword / BM25 / dense / hybrid / rerank
    └── Safety tool ─────── prediction and pseudoscience boundary
    │
    ▼
Evidence Pack
    │
    ├── Deterministic generator
    └── OpenAI-compatible LLM generator
    │
    ▼
Citation and contract evaluation
```

## Core design

### Deterministic planning

`src/seismosearch/planner.py` parses query type, time ranges, magnitude thresholds, document query rewrites, and tool parameters without handing routing control to an LLM.

### Structured event tools

`event_search` and `event_statistics` query normalized historical events by time, magnitude, depth, geographic bounds, event type, review status, and ordering. DuckDB is used for exact filtering and aggregation rather than semantic retrieval.

### Hybrid document retrieval

The document layer supports keyword matching, BM25, dense embeddings, reciprocal-rank fusion, and CrossEncoder reranking. The default corpus is limited to `data/processed/docs/` to avoid contaminating answers with project notes or evaluation artifacts.

### Evidence-constrained generation

`Evidence Pack` separates planner output, tool calls, event evidence, computed statistics, document evidence, safety labels, and answer constraints. The LLM generator receives only a controlled evidence context, must return strict JSON, and can cite only existing evidence IDs. Validation failures fall back to deterministic generation.

### Safety boundary

The unified safety gate runs before downstream retrieval. Prediction-inducing and pseudoscientific queries are short-circuited and receive bounded alternatives instead of event searches or unsupported forecasts.

## Data

The repository includes a small default sample for local execution:

```text
data/processed/events_sample_1000.jsonl
data/processed/docs/
```

An optional reproducible expansion is available through the USGS FDSN Event Web Service:

- 39,320 global earthquake events from 2021–2025;
- M4.5+ with `eventtype=earthquake`;
- duplicate, invalid, and missing-magnitude checks;
- 8 additional USGS/FEMA reference documents;
- provenance and SHA-256 recorded in `data/processed/events_catalog_2021_2025_m45.manifest.json`.

The large JSONL snapshot and DuckDB runtime file are generated artifacts and are intentionally not committed. See [`data_card.md`](data_card.md) and [`docs/data_expansion_v1.md`](docs/data_expansion_v1.md).

## Quick start

Windows PowerShell:

```powershell
git clone https://github.com/FrankXIAO0108/SeismoSearch.git
cd SeismoSearch

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install duckdb numpy pytest

$env:PYTHONPATH="$PWD\src"
$env:PYTHONIOENCODING="utf-8"
python .\scripts\build_event_db.py
python -m pytest -q
```

Run a deterministic example without an LLM:

```powershell
python -c "import json; from seismosearch.pipeline import run_pipeline; result=run_pipeline('震级和烈度有什么区别？', generator_mode='deterministic', doc_retriever_mode='keyword'); print(json.dumps(result, ensure_ascii=False, indent=2))"
```

To use dense or CrossEncoder retrieval, install `sentence-transformers`. The first run downloads the configured models; subsequent runs can resolve local cached snapshots.

## Optional catalog expansion

```powershell
python .\scripts\build_event_catalog_snapshot.py `
  --starttime 2021-01-01 `
  --endtime 2026-01-01 `
  --min-magnitude 4.5 `
  --event-type earthquake `
  --processed-output data\processed\events_catalog_2021_2025_m45.jsonl `
  --manifest-output data\processed\events_catalog_2021_2025_m45.manifest.json `
  --raw-output-dir data\raw\events\catalog_2021_2025_m45

python .\scripts\build_event_db.py `
  --input data\processed\events_catalog_2021_2025_m45.jsonl `
  --db data\duckdb\seismosearch_catalog_2021_2025_m45.duckdb
```

The expanded database is not automatically used by the default pipeline; this prevents a data update from silently changing the baseline evaluation environment.

## Evaluation

The project evaluates both individual retrieval and the full pipeline:

- retrieval source, term, requirement, and reciprocal-rank metrics;
- query type and tool selection;
- event and document evidence support;
- citation validity and citation support;
- safety refusal behavior;
- deterministic versus LLM generation with fallback behavior.

The current local test suite passes 167 tests. The expansion development set reaches Requirement Hit@5 = 1.0 on 16 queries; this is an iteration set, not an independent blind benchmark. Historical holdout artifacts are retained under `eval/` for reproducibility and failure analysis.

## Repository layout

```text
src/seismosearch/      Runtime modules: planner, tools, retrieval, evidence, generation
schemas/               Event, document, evaluation, and evidence contracts
data/processed/        Default event sample and user-facing knowledge corpus
scripts/               Data ingestion, database construction, and evaluation entry points
eval/                  Frozen inputs and evaluation results
tests/                 Unit, integration, safety, citation, and pipeline tests
docs/                  Focused data and holdout references
```

## Scope and limitations

This repository is a research-oriented, reproducible RAG prototype. It does not provide multi-tenant permissions, high availability, production monitoring, online freshness guarantees, or a complete global earthquake catalog. Its value is the explicit separation of routing, tools, retrieval, evidence, generation, safety, and evaluation so that each failure mode can be inspected independently.
