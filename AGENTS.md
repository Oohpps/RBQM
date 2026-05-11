# Repository Guidelines

## Project Structure & Module Organization

This repository contains a compact RBQM web application.

- `backend/main.py` defines the FastAPI application, API routes, upload handling, export responses, and static frontend mounting.
- `app.py` contains the shared RBQM data-processing logic, demo data generation, metric calculation, thresholds, labels, and Excel export helpers. Keep this file importable by the backend.
- `frontend/index.html`, `frontend/app.js`, and `frontend/styles.css` implement the static browser UI.
- `frontend/assets/` stores UI assets such as `rbqm-logo.png`.
- `requirements.txt` lists Python runtime dependencies.

There is currently no dedicated `tests/` directory.

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

Open `http://127.0.0.1:8000` to use the app. For a quick syntax check, run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py backend\main.py
```

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation, type hints where practical, and small functions for data transformations. Preserve the existing naming pattern: constants in `UPPER_SNAKE_CASE`, classes in `PascalCase`, and functions/variables in `snake_case`.

Frontend code is plain HTML, CSS, and JavaScript. Keep DOM IDs/classes descriptive and aligned with the RBQM domain. Avoid adding build tooling unless the project explicitly needs it.

## Testing Guidelines

No automated test suite is currently configured. For backend changes, add focused tests under a new `tests/` directory, preferably using `pytest` and FastAPI `TestClient`. Name files `test_<feature>.py` and test functions `test_<behavior>()`.

At minimum, verify changed code with `py_compile` and a manual run through the upload, demo-data, metrics, and export flows.

## Commit & Pull Request Guidelines

This checkout does not include Git metadata, so no repository-specific commit convention could be inferred. Use concise, imperative commit messages such as `Add RBQM export validation` or `Fix upload error handling`.

Pull requests should include a short summary, affected files or flows, validation steps, and screenshots or exported files when UI or report output changes.

## Security & Configuration Tips

Do not commit `.venv/`, local IDE files, uploaded study data, or generated exports. Treat clinical study files as sensitive and keep sample data anonymized.
