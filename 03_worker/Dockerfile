# Worker Dockerfile with PaddleOCR GPU support
# Base: NVIDIA CUDA 11.8 with cuDNN 8

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN python -m pip install --upgrade pip

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir paddlepaddle-gpu==2.6.1 paddleocr==2.7.3

# Copy application
COPY . .

# Environment variables (can be overridden)
ENV USE_GPU=true
ENV OCR_LANG=en
ENV LOG_LEVEL=INFO
ENV NATS_URL=nats://ocr-nats:4222
ENV FILE_PROXY_URL=http://ocr-backend:8000/api/v1/internal/file-proxy
ENV ORCHESTRATOR_URL=http://ocr-backend:8000/api/v1/internal

# Run worker
CMD ["python", "-m", "app.main"]
