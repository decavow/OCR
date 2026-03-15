#!/usr/bin/env bash
# PaddleOCR-VL Worker — Run locally with conda env ocr-gpu
# Usage: bash run-local.sh  or  ./run-local.sh

eval "$(conda shell.bash hook)"
conda activate ocr-gpu
export PYTHONNOUSERSITE=1

export WORKER_SERVICE_TYPE=ocr-paddle-vl
export WORKER_DISPLAY_NAME="PaddleOCR-VL (GPU)"
export WORKER_DESCRIPTION="PaddleOCR Vision-Language structured extraction with GPU acceleration"
export WORKER_ACCESS_KEY=sk_local_paddle_vl
export WORKER_FILTER_SUBJECT=ocr.structured_extract.tier0
export WORKER_ALLOWED_METHODS=structured_extract
export WORKER_ALLOWED_TIERS=0
export WORKER_SUPPORTED_FORMATS=json,md,html,txt
export OCR_ENGINE=paddle_vl
export USE_GPU=true
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export OCR_LANG=en
export NATS_URL=nats://localhost:4222
export FILE_PROXY_URL=http://localhost:8080/api/v1/internal/file-proxy
export ORCHESTRATOR_URL=http://localhost:8080/api/v1/internal
export TEMP_DIR=/tmp/ocr_worker

cd "$(dirname "$0")/../.."
python -m app.main
