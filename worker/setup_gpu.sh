#!/bin/bash
# Setup script for Linux/WSL GPU development
# Requires: Python 3.11+, CUDA 11.8+, cuDNN 8+

set -e

echo "=== OCR Worker GPU Setup ==="
echo

# Check Python version
python3 --version || { echo "ERROR: Python3 not found"; exit 1; }

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install PaddlePaddle GPU
echo "Installing PaddlePaddle GPU..."
pip install paddlepaddle-gpu

# Install other dependencies
echo "Installing other dependencies..."
pip install nats-py>=2.6.0 httpx>=0.25.0 paddleocr>=2.7.0 \
    Pillow>=10.1.0 numpy>=1.24.0 opencv-python-headless>=4.8.0 \
    pdf2image>=1.16.0 python-dotenv>=1.0.0

# Copy env file if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
fi

echo
echo "=== Setup Complete ==="
echo
echo "To run the worker:"
echo "  1. Activate venv: source venv/bin/activate"
echo "  2. Start infrastructure: docker-compose -f docker-compose.infra.yml up -d"
echo "  3. Start backend: cd ../backend && uvicorn app.main:app --port 8000"
echo "  4. Run worker: python -m app.main"
