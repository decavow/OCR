#!/usr/bin/env bash
# Tesseract OCR Worker — Run locally with conda env base
# Usage: bash run-local.sh  or  ./run-local.sh

eval "$(conda shell.bash hook)"
conda activate base

export WORKER_SERVICE_TYPE=ocr-tesseract
export WORKER_DISPLAY_NAME="Tesseract OCR (CPU)"
export WORKER_DESCRIPTION="Tesseract-based text extraction (CPU-only)"
export WORKER_ACCESS_KEY=sk_local_tesseract
export WORKER_FILTER_SUBJECT=ocr.ocr_tesseract_text.tier0
export WORKER_ALLOWED_METHODS=ocr_tesseract_text
export WORKER_ALLOWED_TIERS=0
export WORKER_SUPPORTED_FORMATS=txt,json
export OCR_ENGINE=tesseract
export USE_GPU=false
export OCR_LANG=en
export TESSERACT_CMD=/home/decavow1/miniconda3/envs/tesseract/bin/tesseract
export NATS_URL=nats://localhost:4222
export FILE_PROXY_URL=http://localhost:8080/api/v1/internal/file-proxy
export ORCHESTRATOR_URL=http://localhost:8080/api/v1/internal
export TEMP_DIR=/tmp/ocr_worker

cd "$(dirname "$0")/../.."
python -m app.main
