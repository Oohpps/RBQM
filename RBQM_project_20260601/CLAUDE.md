# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RBQM (Risk-Based Quality Management) platform for clinical trial site risk monitoring. Users upload clinical study data (CSV/XLSX/XLS), map fields to domains, compute Key Risk Indicators (KRIs), identify risk signals, rank sites, and export review packages.

Tech stack: FastAPI backend + Vue 3 / TypeScript / Vite frontend. The backend serves both API endpoints and the built frontend static files from `frontend/dist/`.

## Commands

**Backend:**
```powershell
# Install dependencies (from project root)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Start server
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Syntax check
.\.venv\Scripts\python.exe -m py_compile app.py backend\main.py

# Run tests
.\.venv\Scripts\python.exe -m unittest tests.test_field_mapping tests.test_kri_switches
```

**Frontend:**
```powershell
cd frontend
npm.cmd install
npm.cmd run dev       # dev server at http://127.0.0.1:5173
npm.cmd run build     # type-check + build to frontend/dist/
```

The app is served at `http://127.0.0.1:8000` in production (backend hosts `frontend/dist/`).

## Architecture

### Backend (`backend/main.py`)

Single-file FastAPI app (~2300 lines) that handles all API routes, upload processing, state management, and static file serving. Key patterns:

- **Session-based state**: Each browser session gets a UUID. Uploaded data and computed state are held in memory (`SESSIONS` dict). No database.
- **KRI config persistence**: `KriConfigStore` saves versioned KRI threshold configs to `data/config/kri_config_versions.json`.
- **Thresholds model**: `rbqm.models.Thresholds` is a frozen dataclass with all 20 KRI metric thresholds, `kri_enabled` toggle, and `enabled_metrics` tuple. New metrics must be added to `KRI_METRIC_KEYS` tuple, `Thresholds` dataclass, `KRI_CATALOG` in main.py, and the frontend `thresholds` array in `config.ts`.
- **API endpoints**: `/api/state`, `/api/upload/preview`, `/api/upload/commit`, `/api/reset`, `/api/export`, `/api/kri/catalog`, `/api/config` (GET/POST).

### RBQM package (`rbqm/`)

Core domain logic, independent of the web framework:

| Module | Purpose |
|---|---|
| `config.py` | Domain definitions, field lists, Chinese/English labels, column name aliases |
| `models.py` | `Thresholds` dataclass and `KRI_METRIC_KEYS` tuple |
| `ingestion.py` | File reading (CSV/XLSX/XLS), sheet parsing, column normalization, domain inference, field mapping |
| `metrics.py` | KRI computation, site scoring, signal detection, component scoring |
| `enrichment.py` | Post-processing enriches tables with computed columns |
| `export.py` | Excel export helpers |
| `demo.py` | Built-in demo data generation |
| `settings_store.py` | Versioned KRI config file I/O |
| `utils.py` | Shared helpers: `find_col`, `snake_case`, `standardize_columns`, `numeric_series`, `datetime_series`, `truthy_series`, `grade_series`, `safe_div` |

**Data flow**: Upload → `read_uploaded_files` → field mapping via `MappingConfig` → `enrich_tables` → `compute_metrics` → signals + scoring → export.

Column normalization adds `__` prefixed internal columns (e.g., `__site_id`, `__subject_id`) after standardization. Use these prefixed columns for all internal lookups.

### Frontend (`frontend/src/`)

Single-page Vue 3 app. Key files:

- `App.vue` — Main application (~3000 lines). Contains all tab views, upload flow, KRI table, ranking, signals, and action tracking.
- `api.ts` — All backend API calls.
- `config.ts` — KRI threshold definitions (must stay in sync with backend `KRI_CATALOG`) and `scoreColumnsByMetric` mapping.
- `types.ts` — TypeScript interfaces for all API data shapes.
- `i18n.ts` — Chinese/English localization strings.
- `components/` — Extracted components: `DataTable.vue`, `MappingWizard.vue`, `ThresholdPanel.vue`, `Sidebar.vue`, `Topbar.vue`, `AppSelect.vue`.

Frontend API calls use relative paths (e.g., `/api/state`) — same-origin, no CORS issues.

### Data domains

Supported domains (defined in `rbqm/config.py`): subjects, visits, queries, critical_points, ae, dosing, pk, tumor, labs, deviations. Each domain has required fields (`subject_id`, `site_id`) and optional fields. The system uses flexible column matching via `SITE_ALIASES` and `SUBJECT_ALIASES` to accommodate varied source data naming.

## Conventions

- Python: 4-space indent, type hints, `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. `from __future__ import annotations` at top of every module.
- Frontend: Vue 3 Composition API, `PascalCase` components, `camelCase` composables. CSS classes are descriptive and domain-specific.
- Labels and UI text are bilingual (Chinese/English) — see `i18n.ts` and `rbqm/config.py`.
- When adding a new KRI metric: update `KRI_METRIC_KEYS`, `Thresholds`, `KRI_CATALOG` in `backend/main.py`, label dicts in `rbqm/config.py`, and the `thresholds` array + `scoreColumnsByMetric` in `frontend/src/config.ts`.
- Clinical study data is sensitive — never commit real data files. Demo data in `rbqm/demo.py` is synthetic.
- `frontend/dist/` is rebuilt by developers before packaging. End users only need Python.
