# aavin-ocr

Bilingual OCR Studio / பதிவு

Free, local-first Tamil + English OCR for Windows. React/Vite UI, FastAPI, SQLite, OpenCV and CPU PaddleOCR. No API key, cloud inference, analytics, external fonts or paid service.

**Local OCR and table-review implementation, not a finished production release.** Real OCR is integrated; recognition quality must be assessed against your own labeled handwriting. Printed synthetic fixtures are smoke tests, not handwriting accuracy evidence.

## Implemented

- PNG/JPEG and multipage PDF uploads, 25 MB / 10 pages / 24 million pixels per page by default.
- Explicit `PP-OCRv5_mobile_det` + `ta_PP-OCRv5_mobile_rec`, CPU, four threads, recognition batch size one. Models load once per server process; one document job at a time.
- Local queued/processing/complete/failed states and restart recovery for interrupted jobs.
- Canonical, EXIF-oriented PNG source pages; bounded inference resizing with coordinates mapped back to source pixels.
- Page selector, zoom, drag-to-pan, clickable/keyboard-selectable polygons linked to editable text, confidence warnings, search, per-page full text, raw text and correction history.
- SQLite persistence of exact raw and corrected Unicode strings; explicit review state. An empty correction stays empty. No digit substitution, translation or transliteration.
- XLSX, UTF-8-BOM CSV, JSON (including optional provenance), UTF-8 TXT. Exports use **saved** corrections. CSV protects formula-like text with a leading apostrophe; JSON/TXT preserve exact text. XLSX uses string cells to preserve zeros and avoid formulas.
- Light/dark themes, responsive layout, accessible labels and visible keyboard focus.
- Row-aware reading order for existing and new uploads: boxes on the same visual row read left to right, with tabs between cells in Full text/TXT.
- Editable **Table view**: suggested ruled columns and data rows, source-image grid, manual boundary editing, column mapping, cell review/history, numeric validation and table-specific exports.
- Synthetic fixtures, unit/API/component tests, real-model smoke command and CER/WER/numeric-token benchmark.

## Install on Windows 11

Use **64-bit Python 3.12** and Node.js 22.12+ (verified here with Python 3.12.15 and Node 24.17). Python 3.14 is not the target for this pinned Paddle runtime. Iris Xe is not used: inference runs on the Intel CPU.

From `D:\ocr`, with Python 3.12 available to `py`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location frontend
npm.cmd ci
Set-Location ..
.\.venv\Scripts\python.exe scripts\cache_models.py
.\.venv\Scripts\python.exe scripts\verify_ocr.py
.\.venv\Scripts\python.exe scripts\verify_api.py
```

The current workspace already has `.venv` backed by a workspace-local `.python` runtime. You can use it directly. On another machine, create a new environment; virtual environments are not portable. If you prefer the installer script:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

`Bypass` applies only to this one PowerShell process, not your system policy. No activation is necessary; scripts use explicit Python and `npm.cmd`, avoiding blocked `npm.ps1`.

Installation needs internet access to download open-source packages and two official model repositories. No key is required. `models/manifest.json` records SHA-256 hashes; `cache_models.py --verify-only` checks the downloaded files. Keep `models/`, `.venv/` and frontend dependencies to run offline. Model revisions are recorded by the download cache but not yet pinned upstream; preserve your model directory for reproducibility.

## Run

### Option 1 — Single Command (Recommended)

From the project root (`D:\ocr_nivas\aavin-ocr`), run:

```powershell
# In PowerShell:
.\project_start.ps1
# or simply:
project_start
```

```cmd
# In Windows Command Prompt:
project_start.cmd
```

This single command starts both the FastAPI backend and Vite frontend concurrently, colorizes and streams logs from both services, and handles graceful shutdown when you press `Ctrl+C`.

### Option 2 — Separate Terminals

Open two terminals at the project root:

```powershell
# Terminal 1 — backend
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

```powershell
# Terminal 2 — frontend
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Open **http://127.0.0.1:5173**. API docs: http://127.0.0.1:8000/docs. Both bind to loopback. Stop each with Ctrl+C. Do not use multiple backend workers or start a second backend against the same database.

Upload `backend/tests/fixtures/synthetic-bilingual.png` after running the fixture/smoke script. The fixture contains artificial Tamil labels and numeric strings; it contains no personal records.

## Using Table view

Open an existing document and choose **Table view** beside Review lines and Full text. Existing uploads work without rerunning OCR.

1. Check the suggested grid against the image. The first row boundary should sit below the headers. Use **Adjust rows, columns & field types** to edit comma-separated pixel boundaries. You can also choose an image action to click and add a row or column boundary.
2. Name your columns or use the eight-column farmer register preset. Select Free text, Phone (10 digits), Aadhaar (12 digits), or Pashu Aadhaar (12 digits) for validation.
3. Choose **Save table layout**. Select a cell to highlight its source area and edit its text. Mark it verified only after checking the image, then choose **Save cell**.
4. Download XLSX, CSV, JSON or TXT from the table toolbar. These exports use saved table cells on the selected page. XLSX preserves identifiers as strings and includes a Review sheet. Import CSV numeric columns as text in spreadsheet software to keep leading zeros. JSON optionally includes source polygons, raw text and table correction history (`?metadata=false` omits provenance).

Multiline addresses are combined within cells. Blank merged cells stay blank; ditto marks are preserved and flagged rather than expanded. No identifier is repaired or fabricated. Validation accepts spaces between digits but does not change the stored string. A successful length check is not an identity/checksum validation.

Suggestions use long image rules and a populated numeric column as a row anchor. They are approximate for perspective, curvature, missed text and irregular layouts. The saved grid can be adjusted manually; warnings identify low-confidence text and boundary ambiguities. Regions outside the grid remain in Review lines. Rebuilding an edited table requires the explicit reset checkbox and archives the prior layout and cell edits in history. Table edits are independent of line edits; they never overwrite raw OCR. Concurrent edits are rejected instead of silently overwritten.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\cache_models.py --verify-only
.\.venv\Scripts\python.exe scripts\verify_ocr.py
Set-Location frontend
npm.cmd test
npm.cmd run build
```

API unit tests use a clearly isolated test recognizer to check storage, upload errors, job completion, corrections and exports. `verify_ocr.py` uses the **actual installed PaddleOCR** and cached models, asserts Tamil and English are present, and writes `data/smoke-result.json`. It inspects the actual constructor and `predict` API. It does not compare a mocked result to itself.

`backend/requirements-lock.txt` pins the runtime dependency set. `requirements.txt` selects PaddleX's official `ocr-core` extra, sufficient for this app's existing detection/recognition pipeline. The broader `ocr` extra adds document-parser/VLM dependencies unused here. `requirements-dev.txt` adds test tools, constrained by `requirements-dev-lock.txt`. The installer accepts `-Development` to include these tools. `frontend/package-lock.json` locks frontend dependencies.

Installing a smaller requirements file with ordinary `pip install` does not uninstall old packages. Use a clean environment for deployment, or an exact environment sync with the appropriate lockfile. Do not delete packages manually from `site-packages`. Retained package/model versions, OCR settings and application code are unchanged by this reduction.

`.vercelignore` files exclude local caches, private data and test fixtures from deployment uploads, including when Vercel's Root Directory is `backend/`. Tests and fixtures remain in the repository. These exclusions and the reduced requirements do not make the local SQLite/background-worker architecture serverless-ready, and do not guarantee a bundle below 500 MB.

See [DEPENDENCY_REDUCTION.md](DEPENDENCY_REDUCTION.md) for measured sizes, exact-output comparisons and timing results.

To compare two installed environments without writing recognized text to a report:

```powershell
# Run with the original environment first, then the candidate environment.
.\.venv\Scripts\python.exe scripts\profile_runtime.py --output .cache\baseline.json
.\candidate\Scripts\python.exe scripts\profile_runtime.py --output .cache\candidate.json --compare .cache\baseline.json
```

Use identical `--images` arguments in both runs to add private test images. The profiler compares hashes of input files, model files, exact OCR results (including confidence and coordinates) and table output; it reports three warmed inference timings per sample. It measures installed package files on the current platform, not the Vercel/Linux deployment bundle. Timings vary with CPU load and thermal state.

## Benchmark your handwriting

Put private images and `labels.json` under `data/benchmark/` (ignored by Git):

```json
[
  {"image": "sample.png", "text": "your exact transcription", "numeric_fields": ["000000000001"]}
]
```

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py data\benchmark\labels.json --output data\benchmark\results.json
```

Reports aggregate character error rate (NFC-normalized Unicode codepoints, including whitespace), word error rate (whitespace tokens), numeric exact-match rate and per-image processing time, with model initialization reported separately. Numeric matching counts exact digit runs with duplicate limits; it does **not** establish correct table-cell assignment. CER/WER can exceed 1.0 for insertion-heavy results. Empty denominators return null. Reports omit recognized/reference personal text and image filenames.

For acceptance, use 10–20 transcribed pages covering Tamil handwriting, English handwriting, mixed text, ruled tables and difficult digits. Check numeric fields and table assignment manually. Recognition confidence is not a calibrated guarantee of correctness.

## Configuration

Set environment variables before starting the backend:

| Variable | Default | Meaning |
|---|---:|---|
| `OCR_MAX_UPLOAD_MB` | 25 | Source file byte limit |
| `OCR_MAX_PAGES` | 10 | PDF page limit |
| `OCR_MAX_PIXELS` | 24000000 | Decoded page pixel cap |
| `OCR_MAX_SIDE` | 2000 | Max inference image side |
| `OCR_PDF_DPI` | 150 | PDF raster resolution |
| `OCR_CPU_THREADS` | 4 | Paddle CPU threads |
| `OCR_DATA_DIR` | `data/` | Local documents and SQLite |
| `OCR_MODEL_DIR` | `models/` | Explicit local models |

These bounds reduce peak memory; they are **not an OS-enforced RAM limit**. PDF pages decode sequentially and inference uses one page at a time. Large pages are rejected before rasterization. Keep enough disk space for normalized PNGs; no automatic retention policy exists yet.

## Coordinates, recognition and privacy

`page_index`, `reading_order` and `row_index` are zero-based. A polygon is four `[x,y]` source-pixel points. Source means the displayed EXIF-oriented image, or the PDF raster at the configured DPI, not PDF points or pre-EXIF bytes. For inference resize, `x_source = x_inference * original_width / inference_width`, likewise for y. Visual rows group nearby box centers using the median text height, then sort left to right. Existing region IDs and correction histories are preserved when reading order is recomputed. Table view separately assigns regions to user-adjustable cells by their centers; it preserves source IDs and raw text.

The Tamil recognizer supports mixed Tamil/English/digits. No English fallback is currently applied; raw results come solely from that model. Scores down to zero are retained for review. Automatic document orientation, unwarping and textline orientation models are disabled so no hidden preprocessing changes coordinates or triggers extra downloads.

The installed PaddleX 3.3.10 performs host probes during import and does not implement the newer `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` setting. `app/runtime.py` configures local caches and a Python audit hook rejecting outbound socket connections except loopback before model import. This blocks Python-level host probes and downloads during inference. This is not an OS firewall or a sandbox for untrusted native code. Downloads occur only in the separate installation script. No uploaded images are sent to a model service. Access logging is disabled by launch scripts; application errors store generic diagnostics, not OCR text. Local files are not encrypted; protect your Windows account and backups.

## Remaining checkpoints

| Checkpoint | Status |
|---|---|
| A: scaffold and backend/frontend verification | Implemented; tests and production build |
| B: real Tamil/English extraction | Adapter, cached models, synthetic smoke and benchmark scripts |
| C: preprocessing | Resize/EXIF coordinate handling only; rotation, deskew, crop, perspective correction, denoise and split-page transforms still required |
| D: review | Basic line review/history implemented; unsaved edit navigation protection and richer side-by-side review still required |
| E: tables/exports | Line/table exports, editable cell grid, row/column mapping, 10/12-digit warnings, history and ruled-column suggestions implemented; merged-cell spans and semantic layout inference remain future work |
| F: acceptance/optimization | Unit/component tests and browser table smoke checks implemented; full handwriting corpus, comprehensive accessibility QA, peak RAM profiling and hard job timeouts still required |

Optional English-crop fallback and PP-StructureV3 are not enabled. The subsequently supplied farmer-register image was checked locally: the grid suggestion found 8 columns and 14 data rows. No user image or personal OCR text is included in test fixtures. This does not establish recognition accuracy or production readiness.

## Aavin Production Abstract & Automated Email Reporting

Automated data extraction, validation, SQLite storage, and responsive HTML email reporting for Aavin Milk Production Abstract reports.

### Features

- **Live OCR Extraction**: Detects union code, organization name, report date (parsed into ISO `YYYY-MM-DD`), shift (`EVENING`, `MORNING`), product line items (litres, packets, trays), subtotal rows (`MILK TOTAL`, `CURD & BUTTERMILK TOTAL`), and `GRAND TOTAL`.
- **Conservative Normalization**: Handles comma-as-decimal separators and cleans attached vertical column border artifacts (`|`, `1`) only when mathematically validated against product unit volumes and subtotals.
- **Strict Data Validation**: Validates date validity, numeric formats, and compares line-item sums against extracted subtotals and grand totals. Any arithmetic discrepancy flags an explicit warning and marks the report as `NEEDS_REVIEW`.
- **Transactional SQLite Storage**: Reports are stored in `reports`, `report_items`, and `report_audit_logs` inside immediate transactions. Enforces unique business identity `(union_code, report_date, shift)` to prevent duplicate records.
- **Idempotent Email Dispatch**: Reports marked `VALIDATED` are automatically emailed via SMTP if enabled. Dispatches use an official Aavin-styled responsive HTML table layout with a plain-text alternative. Reports already marked `SENT` are never re-emailed automatically upon reprocessing.
- **Human-in-the-Loop Review**: Reports with flagged warnings require supervisor approval before email dispatch (`POST /api/reports/:id/approve` or through the UI).
- **Audit Logging**: Every creation, reconciliation, approval, and email attempt is persisted in `report_audit_logs`.

### Configuration (`.env`)

Copy `.env.example` to `.env` to configure email credentials and settings:

```env
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_user@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_user@gmail.com
SMTP_FROM_NAME=Aavin OCR Reports
SMTP_USE_TLS=true
SMTP_USE_SSL=false

# Recipients (comma-separated for multiples)
REPORT_EMAIL_TO=operations@aavin.local
REPORT_EMAIL_CC=
REPORT_EMAIL_BCC=

# Feature flags & Timezone
REPORT_EMAIL_ENABLED=false   # Keep false for dry-run simulation mode
REPORT_TIMEZONE=Asia/Kolkata
```

> [!NOTE]
> When `REPORT_EMAIL_ENABLED=false`, the email service operates in safe dry-run mode, simulating delivery, updating status to `DISABLED`, and logging actions without connecting to an external mail server.

### Report API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/reports/ocr` | Parse and save report from raw OCR text or completed `document_id`. |
| `GET` | `/api/reports` | List reports with optional `report_date`, `shift`, `validation_status`, and `email_status` filters. |
| `GET` | `/api/reports/{id}` | Retrieve report details, product items, and audit trail. |
| `GET` | `/api/reports/{id}/email-preview` | Preview email subject, plain text, and HTML table (`?html_only=true` returns raw HTML). |
| `POST` | `/api/reports/{id}/send-email` | Manually dispatch or resend an approved report email. |
| `POST` | `/api/reports/{id}/approve` | Approve a report in `NEEDS_REVIEW` state and optionally dispatch email. |
| `GET` | `/api/reports/{id}/email-status` | Check email delivery submission status, sent timestamp, and logs. |
| `GET` | `/api/health` | System health check including reports subsystem and sanitized SMTP configuration. |

### Running Tests

```powershell
# Run all backend unit, integration, and acceptance tests
.\.venv\Scripts\python.exe -m pytest -q

# Run frontend tests
Set-Location frontend
npm.cmd test
```

## Source layout

`backend/app/main.py` owns HTTP/job lifecycle, `store.py` owns SQLite document persistence, `reports_store.py` owns Aavin reports database persistence, `services/aavin_parser.py` extracts and validates abstract reports, `services/email_service.py` handles HTML templating and SMTP dispatch, `services/documents.py` handles decoding/resizing, and `services/ocr_engine.py` owns the Paddle adapter. `frontend/src/` contains the UI, table workspace, and Aavin report workspace. `scripts/` contains Windows launch/install commands, model caching, synthetic fixture generation and benchmarking. Private runtime data and model weights are ignored.

## Verified upstream references

- [PaddleOCR v3.3.2 constructor and predict API](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.3.2/paddleocr/_pipelines/ocr.py)
- [Official Tamil model repository](https://huggingface.co/PaddlePaddle/ta_PP-OCRv5_mobile_rec)
- [Windows CPU installation requirements](https://www.paddlepaddle.org.cn/documentation/docs/en/install/pip/windows-pip_en.html)

Application source is MIT licensed; dependencies and official model files retain their own licenses.
