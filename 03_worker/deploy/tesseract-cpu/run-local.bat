@echo off
REM Tesseract OCR Worker — Run locally with conda env ocr-worker
REM Usage: double-click or run from terminal

call conda activate ocr-worker

set WORKER_SERVICE_TYPE=ocr-tesseract
set WORKER_DISPLAY_NAME=Tesseract OCR (CPU)
set WORKER_DESCRIPTION=Tesseract-based text extraction (CPU-only)
set WORKER_ACCESS_KEY=sk_local_tesseract
set WORKER_FILTER_SUBJECT=ocr.ocr_tesseract_text.tier0
set WORKER_ALLOWED_METHODS=ocr_tesseract_text
set WORKER_ALLOWED_TIERS=0
set WORKER_SUPPORTED_FORMATS=txt,json
set OCR_ENGINE=tesseract
set USE_GPU=false
set OCR_LANG=latin
set NATS_URL=nats://localhost:4222
set FILE_PROXY_URL=http://localhost:8080/api/v1/internal/file-proxy
set ORCHESTRATOR_URL=http://localhost:8080/api/v1/internal
set TEMP_DIR=%TEMP%\ocr_worker

cd /d %~dp0..\..
python -m app.main
