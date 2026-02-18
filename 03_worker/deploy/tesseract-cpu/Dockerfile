# Tesseract OCR Worker (CPU-only)
# Extends: ocr-worker-base-cpu
#
# Build base first:
#   docker build -f Dockerfile.base-cpu -t ocr-worker-base-cpu:latest .
# Then build this:
#   docker build -f deploy/tesseract-cpu/Dockerfile -t ocr-worker-tesseract:latest .

FROM ocr-worker-base-cpu:latest

# Install Tesseract and language packs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-vie \
    tesseract-ocr-chi-sim \
    tesseract-ocr-jpn \
    tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*

# Install Tesseract engine-specific Python dependencies
COPY deploy/tesseract-cpu/requirements.txt /tmp/engine-requirements.txt
RUN pip install --no-cache-dir -r /tmp/engine-requirements.txt && rm /tmp/engine-requirements.txt

ENV OCR_ENGINE=tesseract
ENV USE_GPU=false
