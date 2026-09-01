# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Overview

IBM Customer Stories Dashboard — Python + Node.js pipeline that discovers, scrapes, classifies, and visualises IBM case studies. Dual data-collection pipelines feed a single self-contained HTML dashboard.

## ⚠️ Dashboard Preservation Rules (Critical)

- **Do not redesign the dashboard.** The dark "command-centre" aesthetic in `src/dashboard.py` must be kept exactly as-is.
- **Do not change colours, fonts, spacing, cards, or layout.** All CSS design tokens (e.g. `--ink`, `--blue`, `--surface`) are intentional and must not be modified.
- **Do not remove any existing dashboard functionality** (filters, drawer, analytics tab, gap analysis, etc.).
- **We are only replacing the story-collection process and data source** — the dashboard HTML/CSS/JS template is frozen.
- **Do not use an AI model to scrape websites.** No LLM-based extraction.
- **Do not use Crawlee, Firecrawl, or MCP for scraping.** The Crawlee crawler in `scripts/` is legacy — use the Python/Tavily pipeline in `src/` instead.

## Stack

- **Python 3.15** (venv at `.venv/`) — main pipeline
- **Node.js** (optional) — legacy Crawlee crawler only (`scripts/crawl-ibm-case-studies.ts`)
- **Package manager:** pip via `requirements.txt`; npm via `package.json`

## Commands

```
# Run Python pipeline (all user-facing operations use .venv\Scripts\python.exe)
.venv\Scripts\python.exe run.py --mode test   # 10 stories
.venv\Scripts\python.exe run.py --mode full   # all stories

# Alternative data pipeline (Crawlee → bridge)
node node_modules/ts-node/dist/bin.js scripts/crawl-ibm-case-studies.ts --all
.venv\Scripts\python.exe scripts/json-to-dashboard.py

# TypeScript type-check only (no output)
node node_modules/typescript/bin/tsc --noEmit
```

No test framework exists. Validate by running `--mode test` and checking `output/IBM_Customer_Stories_TEST.xlsx` and `output/dashboard/index.html`.

## Critical Architecture

### Two separate data pipelines → one dashboard

1. **Python/Tavily** (`run.py` → `src/`): scraper → parser → classifier → excel_writer → dashboard. Primary pipeline.
2. **Crawlee/Bridge** (`6_REBUILD_DASHBOARD.bat`): TypeScript crawler → `scripts/json-to-dashboard.py` → dashboard. Secondary/legacy.

Both pipelines ultimately call `src/dashboard.write_dashboard_html()` which embeds data as an inline JS variable (`const _RAW = {...}`) so the dashboard works from `file://` without a server.

### Key non-obvious patterns

- **Dashboard data is never loaded via `fetch()`** — data is embedded directly inside `index.html` as `const _RAW = {data_js}` using Python f-string injection. This is intentional; browsers block `fetch()` on `file://` URLs.
- **`body_text` and `proof_points` keys are stripped from slim_stories before injection** — they are large and excluded on purpose in `write_dashboard_data()`.
- **The `write_dashboard_data()` function returns a tuple `(slim_stories, slim_proofs)` but its return type annotation says `None`** — this is a bug; do not rely on the return value.
- **GTM motions are stored as semicolon-separated strings at the story level** (`gtm_motions`) but as `list[str]` inside each proof point — `json-to-dashboard.py` joins them with `"; "` when bridging.
- **`src/config.py` is the single source of truth** for all paths, GTM motion names, geography buckets, and keyword lists. Always read/change settings there, never hardcode elsewhere.
- **Product taxonomy lives in `src/config/product-taxonomy.json`** and is loaded separately by the Crawlee bridge — the Python pipeline uses `IBM_PRODUCT_PATTERNS` in `src/parser.py` instead (these are not yet in sync).
- **Story/Proof IDs are sequential global counters** (`_story_counter`, `_proof_counter` in `parser.py`) — they reset to zero on each `run.py` invocation, not across runs.
- **Cache filenames** are `{url_slug[:80]}_{md5[:8]}.html` — the MD5 suffix prevents collisions but makes manual inspection by URL difficult. Use `cache.get_path(url)` to look up a cached file.
- **`logger.py` writes to both stdout and `logs/run_log.txt`** — every `logger.info/warn/error` call prints to the terminal AND appends to the log file.
- **Tavily key validation:** `scraper.py` checks `TAVILY_API_KEY.startswith("tvly-")` — keys not starting with this prefix are silently ignored and fallback to requests.
- **`_BACKUP` files** (`src/classifier_BACKUP.py`, `src/config_BACKUP.py`, `src/dashboard_BACKUP.py`) are snapshots, not active code.

## Code Style

- Python: no linter configured. Follow the existing pattern: docstrings with `---` underline, section comments with `# ── label ───`.
- TypeScript: `strict: true`, `ES2022`, `CommonJS`. No ESLint configured.
- Field names in story/proof dicts use `snake_case` and must match the dashboard JS field names exactly (JS reads them directly by string key).
- "Needs review" (not `None`, not `""`) is the sentinel value for fields that could not be determined — used in QA exceptions sheet and dashboard filtering.

## Output Locations

| File | Purpose |
|---|---|
| `output/dashboard/index.html` | The dashboard (self-contained, open in browser) |
| `output/IBM_Customer_Stories.xlsx` | Full run Excel workbook |
| `output/IBM_Customer_Stories_TEST.xlsx` | Test run Excel workbook |
| `public/data/all-case-studies.json` | Crawlee output (input to bridge script) |
| `cache/` | Raw HTML pages (keyed by URL hash) |
| `logs/run_log.txt` | Run log appended each execution |
