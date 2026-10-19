# Runtime dependency reduction — 19 October 2026

The application uses the same PaddleOCR 3.3.2, PaddleX 3.3.10, PaddlePaddle CPU 3.2.2, OpenCV, detector and Tamil recognizer. No application inference, preprocessing, table, correction, validation or export logic was changed.

## What was removed

The direct PaddleX requirement changed from `paddlex[ocr]` to `paddlex[ocr-core]`. This is the official extra required by the installed PaddleOCR 3.3.2 package itself. The broader extra installs document-parser/VLM utilities that this application does not use.

This eliminates these 21 packages from the runtime dependency closure:

`cachetools`, `cloudpickle`, `cssselect`, `cssutils`, `einops`, `encutils`, `ftfy`, `jinja2`, `joblib`, `lxml`, `markupsafe`, `more-itertools`, `narwhals`, `premailer`, `regex`, `scikit-learn`, `scipy`, `sentencepiece`, `threadpoolctl`, `tiktoken`, `tokenizers`.

`pytest`, `pluggy` and `iniconfig` are now development-only. Test source files and fixtures are retained. The installer defaults to runtime dependencies and supports `-Development` for test tools. Runtime and development lockfiles are separate; every retained package version matches the previous installation. Dependencies still required by upstream package metadata were not forcibly removed.

Root and backend `.vercelignore` files omit private local data, caches, bytecode and test fixtures from deployment uploads. They do not remove repository files or change model caching.

## Measured size

Sizes are sums of installed distribution-file bytes on Windows 11 / Python 3.12.15, before optional test tools were added to the candidate environment:

| Environment | Packages | Size |
|---|---:|---:|
| Original local development environment | 94 | 820.54 MiB |
| Reduced runtime environment | 70 | 662.53 MiB |
| Difference | 24 | **158.01 MiB (19.3%)** |

The reduced development environment has 73 packages, retaining the three test packages. The original Vercel runtime did not explicitly request pytest, so the Windows development-to-runtime measurement includes a small test-tool saving that may not apply to that deployment.

These are **not Linux/Vercel bundle measurements**. The reduced runtime still exceeds 500 MiB locally. This change does not promise to fix Vercel's 500 MB limit or the separate persistent-storage/background-job requirements. Paddle's native runtime and OpenCV were kept intact to preserve behavior and inference settings.

## Output and performance comparison

Both environments used identical model files and input images. SHA-256 comparisons matched the entire normalized OCR output, including raw text, confidence, quadrilaterals, IDs and reading order, plus the complete suggested/materialized table output. Three warmed inference runs per image also produced identical output hashes within each environment.

| Sample | Detected regions | Before median | After median |
|---|---:|---:|---:|
| Synthetic Tamil/English/numeric fixture | 5 | 2.471 s | 1.990 s |
| User-supplied notebook photo | 96 | 17.817 s | 18.259 s |

Notebook timing differed by +2.5%; synthetic timing differed by -19.5%. These short runs show comparable warm notebook throughput, not a guarantee of identical latency. CPU load, cache state and thermal conditions vary. Model/package initialization was 8.61 s before and 12.35 s in the newly created candidate environment; these are different cache states and are not a controlled cold-start comparison.

All 23 backend tests passed in the reduced environment, covering image/PDF handling, corrections, table mapping, validation, exports and the offline guard. The real-model API upload/export smoke check also passed: five synthetic lines and all four exports. The working `.venv` was then synchronized to the reduced development lock, uninstalling 21 unused packages while retaining test tools. Dependency compatibility and a second real-model API/export check passed after that cleanup.

Private images and report JSON files stay under ignored data/cache paths. The report contains output hashes and timing/package metadata, not recognized personal text. `scripts/profile_runtime.py` provides a repeatable comparison command; see README.md.
