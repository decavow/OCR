#!/usr/bin/env bash
# PaddleOCR Text Worker — Run locally with conda env ocr-gpu
# Usage: bash run-local.sh  or  ./run-local.sh

eval "$(conda shell.bash hook)"
conda activate ocr-gpu
export PYTHONNOUSERSITE=1

export WORKER_SERVICE_TYPE=ocr-paddle
export WORKER_DISPLAY_NAME="PaddleOCR (GPU)"
export WORKER_DESCRIPTION="PaddleOCR-based text extraction with GPU acceleration"
export WORKER_ACCESS_KEY=sk_local_paddle
export WORKER_FILTER_SUBJECT=ocr.ocr_paddle_text.tier0
export WORKER_ALLOWED_METHODS=ocr_paddle_text
export WORKER_ALLOWED_TIERS=0
export WORKER_SUPPORTED_FORMATS=txt,json
export OCR_ENGINE=paddle
export USE_GPU=true
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export OCR_LANG=en
export NATS_URL=nats://localhost:4222
export FILE_PROXY_URL=http://localhost:8080/api/v1/internal/file-proxy
export ORCHESTRATOR_URL=http://localhost:8080/api/v1/internal
export TEMP_DIR=/tmp/ocr_worker

cd "$(dirname "$0")/../.."
python -m app.main
