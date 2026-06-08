# Repository Guidelines

## Project Structure & Module Organization

This repository contains a compact RBQM web application.

- `backend/main.py` defines the FastAPI application, API routes, upload handling, export responses, and static frontend mounting.
- `app.py` contains the shared RBQM data-processing logic, demo data generation, metric calculation, thresholds, labels, and Excel export helpers. Keep this file importable by the backend.
- `frontend/` contains the Vue 3 + TypeScript source, Vite config, shared stylesheet, and UI assets.
- `frontend/src/` contains Vue application code and components. Keep generated production files out of source modules.
- `frontend/dist/` is the generated static frontend served by FastAPI. Rebuild it before packaging for users.
- `frontend/assets/` stores UI assets such as `rbqm-logo.png`.
- `requirements.txt` lists Python runtime dependencies.

Backend-focused regression tests live under `tests/`.

## Build, Test, and Development Commands

Create and install the local environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the FastAPI app and static frontend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Build the Vue frontend before packaging or serving the production UI:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
```

Open `http://127.0.0.1:8000` to use the app. For a quick backend syntax check, run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py backend\main.py
```

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation, type hints where practical, and small functions for data transformations. Preserve the existing naming pattern: constants in `UPPER_SNAKE_CASE`, classes in `PascalCase`, and functions/variables in `snake_case`.

Frontend code uses Vue 3, TypeScript, and Vite. Keep component names in `PascalCase`, composable/helper functions in `camelCase`, and CSS class names descriptive and aligned with the RBQM domain. Preserve the existing class names when changing layout so the shared stylesheet remains effective.

## Testing Guidelines

For backend changes, add focused tests under `tests/`, preferably using `pytest` or the existing `unittest` style. Name files `test_<feature>.py` and test functions `test_<behavior>()`.

At minimum, verify changed backend code with `py_compile`, run existing tests, build the Vue frontend, and manually run through upload preview/commit, demo-data reset, metrics, threshold changes, and export flows.

## Commit & Pull Request Guidelines

This checkout does not include Git metadata, so no repository-specific commit convention could be inferred. Use concise, imperative commit messages such as `Add RBQM export validation` or `Fix upload error handling`.

Pull requests should include a short summary, affected files or flows, validation steps, and screenshots or exported files when UI or report output changes.

## Security & Configuration Tips

Do not commit `.venv/`, `frontend/node_modules/`, `frontend/dist/`, local IDE files, uploaded study data, or generated exports. Treat clinical study files as sensitive and keep sample data anonymized.
