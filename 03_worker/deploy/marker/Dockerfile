# Marker (Surya OCR) Formatted Text Extraction Worker (GPU)
# Engine: marker | Method: ocr_marker | GPU: Yes (VRAM peak ~5GB, batch=8)
#
# Build base first:
#   docker build -f Dockerfile.base-gpu -t ocr-worker-base-gpu:latest .
# Then build this:
#   docker build -f deploy/marker/Dockerfile -t ocr-worker-marker:latest .

FROM ocr-worker-base-gpu:latest

# Install Marker engine-specific dependencies
COPY deploy/marker/requirements.txt /tmp/engine-requirements.txt
RUN pip install --no-cache-dir -r /tmp/engine-requirements.txt && rm /tmp/engine-requirements.txt

# Batch size env vars MUST be set before importing marker/surya
ENV OCR_ENGINE=marker
ENV USE_GPU=true
ENV MARKER_BATCH_SIZE=8
ENV INFERENCE_RAM=8
