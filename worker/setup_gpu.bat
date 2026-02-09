@echo off
REM Setup script for Windows GPU development
REM Requires: Python 3.11+, CUDA 11.8+, cuDNN 8+

echo === OCR Worker GPU Setup ===
echo.

REM Check Python version
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    exit /b 1
)

REM Create virtual environment if not exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install PaddlePaddle GPU (use Tsinghua mirror for faster download in China)
echo Installing PaddlePaddle GPU...
pip install paddlepaddle-gpu -i https://pypi.tuna.tsinghua.edu.cn/simple

REM Install other dependencies
echo Installing other dependencies...
pip install nats-py>=2.6.0 httpx>=0.25.0 paddleocr>=2.7.0 Pillow>=10.1.0 numpy>=1.24.0 opencv-python-headless>=4.8.0 pdf2image>=1.16.0 python-dotenv>=1.0.0

REM Copy env file if not exists
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
)

echo.
echo === Setup Complete ===
echo.
echo To run the worker:
echo   1. Activate venv: venv\Scripts\activate
echo   2. Start infrastructure: docker-compose -f docker-compose.infra.yml up -d
echo   3. Start backend: cd ..\backend ^&^& uvicorn app.main:app --port 8000
echo   4. Run worker: python -m app.main
echo.
pause
