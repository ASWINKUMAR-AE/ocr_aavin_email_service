# Checkpoints A and B — 19 October 2026

## Update: row reading order and editable tables

The later table-view request is implemented. `services/layout.py` groups visual rows before reading left to right, including existing documents, preserving region IDs and correction history. Full text/TXT now joins same-row regions with tabs.

`services/table_parser.py` suggests column boundaries from long image rules and data rows from a populated column. `app/tables.py` provides grid persistence, cell corrections, history, revision-conflict checks, numeric warnings and separate XLSX/CSV/JSON/TXT table exports. `frontend/src/TableWorkspace.jsx` and `table.css` add the source grid, adjustable boundaries, custom column names/types, cell editor and responsive table. Empty merged cells and ditto marks are never automatically expanded.

The supplied image was processed locally using its existing OCR regions: 8 columns, 14 data rows and multiline addresses assigned to individual cells. The latest uploaded copy has its suggested table layout saved; all cells remain unreviewed and no recognized text was changed. Private images, outputs and browser screenshots remain under ignored runtime/cache folders, outside tracked fixtures.

Validation: 23 backend tests and 8 frontend tests passed; production build passed. Headless Chrome verified the real table, source highlighting, multiline address, XLSX download, dark/light layouts and a 390px mobile viewport without page overflow or browser exceptions. This verifies layout behavior, not identifier accuracy. Grid boundaries remain approximations; manual boundary adjustment and number verification are still necessary.

Refresh http://127.0.0.1:5173, open the uploaded document and choose **Table view**. Details are in README.md under “Using Table view”. The original checkpoint report below describes the earlier delivery; its outstanding table/browser work is superseded by this update.

## A — local foundation verified

Created `backend/app/` (FastAPI, SQLite, single OCR worker, decoding and upload limits), `frontend/` (React/Vite studio), Windows scripts, test suites, lockfiles, README and MIT license. No existing project files were present.

Validation:

- Python 3.12.15 x64 installed inside this workspace; Node 24.17.0.
- 14 backend tests passed; one upstream Starlette/AnyIO deprecation warning.
- 4 frontend tests passed; Vite production build passed.
- Live Vite page returned HTTP 200; `/api/health` through Vite's proxy returned the correct detector, recognizer and configured limits. Test servers were stopped afterward.
- Frontend install audit: zero reported vulnerabilities after updating Vite/Vitest.
- Python dependency compatibility check: 94 installed packages compatible. This is not a Python security audit.

Commands from `D:\ocr`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend
npm.cmd test
npm.cmd run build
Set-Location ..
```

## B — actual CPU extraction verified

Implemented `backend/app/services/ocr_engine.py`, explicit local model caching, synthetic fixture generation, `verify_ocr.py`, `verify_api.py` and `benchmark.py`. Inspected the installed constructor/common arguments and actual result objects; no legacy PaddleOCR 2.x API is used.

Verified versions: PaddleOCR 3.3.2, PaddleX 3.3.10, PaddlePaddle CPU 3.2.2, NumPy 2.2.6. OpenCV uses the single contrib wheel required by PaddleX, avoiding overlapping OpenCV distributions. Models are `PP-OCRv5_mobile_det` and `ta_PP-OCRv5_mobile_rec`, stored under `models/`. Local SHA-256 verification passed.

The 1200 × 650 synthetic printed fixture produced five correctly recognized lines:

```text
தமிழ் மொழி
பெயர் : மாதிரி
English sample
0123456789
000000000001
```

Confidence values ranged from about 0.959 to 1.000. Each line included four source-coordinate points, zero-based page index and reading order. The real API upload completed and all four export formats returned nonempty files.

Measured runs on this machine:

| Check | Result |
|---|---|
| First model load + inference after PaddleOCR import | 20.614 s |
| API job, including package/model initialization | 10.740 s |
| Separate benchmark model initialization | 6.474 s |
| Benchmark page processing after initialization | 2.948 s |
| Synthetic CER | 0 errors / 64 characters |
| Synthetic WER | 0 errors / 9 words |
| Exact numeric-token matches | 2 / 2 |

First package import took additional time; the first timing does not include it. These runs have different cache/startup states and are not a stable throughput benchmark. No peak-RAM or handwriting-quality claim is made.

```powershell
.\.venv\Scripts\python.exe scripts\cache_models.py --verify-only
.\.venv\Scripts\python.exe scripts\verify_ocr.py
.\.venv\Scripts\python.exe scripts\verify_api.py
.\.venv\Scripts\python.exe scripts\benchmark.py backend\tests\fixtures\benchmark-labels.json --output data\synthetic-benchmark.json
```

## Run the application

In separate PowerShell terminals at `D:\ocr`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Visit http://127.0.0.1:5173. No system-wide execution-policy change is needed.

## Remaining limitations

This delivers the requested A/B starting checkpoints, plus basic overlay/correction/export functionality to inspect results. C–F remain incomplete: advanced geometric preprocessing, optional English fallback, table row/column mapping and cell validation, full browser visual QA, real handwriting acceptance tests, hard runtime/memory limits, unsaved-navigation protection and production hardening. No user notebook or farmer-register image was supplied. Browser rendering was not inspected; component tests and HTTP/build checks passed.

PaddleX prints a harmless model-host-unavailable warning because runtime outbound Python connections are blocked. The model paths are local and inference succeeds. The missing-ccache warning is upstream and does not prevent CPU inference. Full installation, configuration, privacy boundaries and future checkpoints are documented in README.md.
