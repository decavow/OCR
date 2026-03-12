@echo off
REM PaddleOCR-VL Worker — Run locally with conda env ocr-worker
REM Usage: double-click or run from terminal

call conda activate ocr-worker

set WORKER_SERVICE_TYPE=ocr-paddle-vl
set WORKER_DISPLAY_NAME=PaddleOCR-VL (GPU)
set WORKER_DESCRIPTION=PaddleOCR Vision-Language structured extraction with GPU acceleration
set WORKER_ACCESS_KEY=sk_local_paddle_vl
set WORKER_FILTER_SUBJECT=ocr.structured_extract.tier0
set WORKER_ALLOWED_METHODS=structured_extract
set WORKER_ALLOWED_TIERS=0
set WORKER_SUPPORTED_FORMATS=json,md,txt
set OCR_ENGINE=paddle_vl
set USE_GPU=true
set OCR_LANG=en
set NATS_URL=nats://localhost:4222
set FILE_PROXY_URL=http://localhost:8080/api/v1/internal/file-proxy
set ORCHESTRATOR_URL=http://localhost:8080/api/v1/internal
set TEMP_DIR=%TEMP%\ocr_worker

cd /d %~dp0..\..
python -m app.main

@REM run-local.bat
@REM powershell -NoProfile -Command "Get-Process python | ForEach-Object { $cmd = (Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\").CommandLine; '{0,-8} {1}' -f $_.Id, $cmd }"
@REM taskkill /PID 141392 /F
