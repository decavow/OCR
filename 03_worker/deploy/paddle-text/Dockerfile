# PaddleOCR Text Worker (GPU)
# Extends: ocr-worker-base-gpu
#
# Build base first:
#   docker build -f Dockerfile.base-gpu -t ocr-worker-base-gpu:latest .
# Then build this:
#   docker build -f deploy/paddle-text/Dockerfile -t ocr-worker-paddle:latest .

FROM ocr-worker-base-gpu:latest

# Install PaddleOCR engine-specific dependencies
COPY deploy/paddle-text/requirements.txt /tmp/engine-requirements.txt
RUN pip install --no-cache-dir -r /tmp/engine-requirements.txt && rm /tmp/engine-requirements.txt

ENV USE_GPU=true
