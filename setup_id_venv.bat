@echo off
setlocal

cd /d "%~dp0"

if exist id_venv (
    rmdir /s /q id_venv
)

py -3.11 -m venv id_venv
if errorlevel 1 exit /b 1

call id_venv\Scripts\activate
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1

python -m pip install numpy==1.26.4
if errorlevel 1 exit /b 1

python -m pip install opencv-python==4.6.0.66
if errorlevel 1 exit /b 1

python -m pip install paddlepaddle==2.6.2
if errorlevel 1 exit /b 1

python -m pip install paddleocr==2.7.3
if errorlevel 1 exit /b 1

python -m pip install ultralytics huggingface_hub matplotlib
if errorlevel 1 exit /b 1

python -m pip install --force-reinstall numpy==1.26.4 opencv-python==4.6.0.66 opencv-contrib-python==4.6.0.66 opencv-python-headless==4.6.0.66
if errorlevel 1 exit /b 1

python -c "import numpy; print('numpy', numpy.__version__)"
if errorlevel 1 exit /b 1

python -c "import cv2; print('cv2', cv2.__version__)"
if errorlevel 1 exit /b 1

python -c "from paddleocr import PaddleOCR; print('paddleocr ok')"
if errorlevel 1 exit /b 1

python -c "from ultralytics import YOLO; print('yolo ok')"
if errorlevel 1 exit /b 1

echo.
echo Indian ID validator environment is ready.
