param([string]$Python = 'py')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($Python -eq 'py') { & py -3.12 -m venv .venv } else { & $Python -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw 'Install 64-bit Python 3.12, or supply -Python with its executable path.' }
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend installation failed.' }
Push-Location frontend
try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed.' } } finally { Pop-Location }
& .\.venv\Scripts\python.exe scripts/cache_models.py
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
& .\.venv\Scripts\python.exe scripts/verify_ocr.py
if ($LASTEXITCODE -ne 0) { throw 'Real OCR verification failed.' }
