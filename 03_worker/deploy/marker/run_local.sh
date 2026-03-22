#!/bin/bash
# Run Marker worker locally (no Docker)
# Usage: cd 03_worker && bash deploy/marker/run_local.sh

# Identity
export WORKER_SERVICE_TYPE=marker
export WORKER_DISPLAY_NAME="ocr_text_formatted(marker)"
export WORKER_DESCRIPTION="Marker (Surya OCR) formatted text extraction with structure preservation"

# Credentials
export WORKER_ACCESS_KEY=sk_local_marker

# Queue routing
export WORKER_FILTER_SUBJECT=ocr.ocr_marker.tier0

# Capabilities
export WORKER_ALLOWED_METHODS=ocr_marker
export WORKER_ALLOWED_TIERS=0
export WORKER_SUPPORTED_FORMATS=md,html,json

# OCR Settings
export OCR_ENGINE=marker
export USE_GPU=true
export OCR_LANG=vi

# Marker-specific
export MARKER_BATCH_SIZE=8
export INFERENCE_RAM=8
export MARKER_USE_LLM=false

# Connections (local services)
export NATS_URL=nats://localhost:4222
export FILE_PROXY_URL=http://localhost:8080/api/v1/internal/file-proxy
export ORCHESTRATOR_URL=http://localhost:8080/api/v1/internal

# Runtime
export LOG_LEVEL=INFO

echo "Starting Marker worker locally..."
echo "  Service Type: $WORKER_SERVICE_TYPE"
echo "  Display Name: $WORKER_DISPLAY_NAME"
echo "  Method: $WORKER_ALLOWED_METHODS"
echo "  GPU: $USE_GPU"
echo "  Lang: $OCR_LANG"
echo ""

python -m app.main
