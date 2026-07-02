@echo off
setlocal

cd /d "%~dp0"

set "ID_VENV=%CD%\id_venv"
set "VALIDATOR_DIR=%CD%\indian-id-validator"
set "VALIDATOR_REQUIREMENTS=%VALIDATOR_DIR%\requirements.txt"
set "VALIDATOR_INFERENCE=%VALIDATOR_DIR%\inference.py"

echo.
echo [Indian ID] Creating clean Python 3.11 environment...

if exist "%ID_VENV%" (
    rmdir /s /q "%ID_VENV%"
)

py -3.11 -m venv "%ID_VENV%"
if errorlevel 1 (
    echo [Indian ID] Failed to create id_venv. Install Python 3.11 and retry.
    exit /b 1
)

call "%ID_VENV%\Scripts\activate.bat"
if errorlevel 1 exit /b 1

echo.
echo [Indian ID] Upgrading packaging tools...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1

echo.
echo [Indian ID] Installing validator dependencies from:
echo %VALIDATOR_REQUIREMENTS%
python -m pip install -r "%VALIDATOR_REQUIREMENTS%"
if errorlevel 1 exit /b 1

echo.
echo [Indian ID] Re-locking NumPy/OpenCV stack for PaddleOCR compatibility...
python -m pip install --force-reinstall numpy==1.26.4 opencv-python==4.6.0.66 opencv-contrib-python==4.6.0.66 opencv-python-headless==4.6.0.66
if errorlevel 1 exit /b 1

echo.
echo [Indian ID] Verifying Python packages...
python -c "import numpy; print('numpy', numpy.__version__)"
if errorlevel 1 exit /b 1

python -c "import cv2; print('cv2', cv2.__version__)"
if errorlevel 1 exit /b 1

python -c "from paddleocr import PaddleOCR; print('paddleocr ok')"
if errorlevel 1 exit /b 1

python -c "from ultralytics import YOLO; print('ultralytics yolo ok')"
if errorlevel 1 exit /b 1

python -c "from huggingface_hub import hf_hub_download; print('huggingface_hub ok')"
if errorlevel 1 exit /b 1

echo.
echo [Indian ID] Verifying config and model files...
python -c "import json; from pathlib import Path; root=Path(r'%VALIDATOR_DIR%'); cfg=json.loads((root/'config.json').read_text(encoding='utf-8')); missing=[data['path'] for data in cfg['models'].values() if not (root/data['path']).exists()]; print('configured models:', ', '.join(cfg['models'].keys())); print('missing local models:', ', '.join(missing) if missing else 'none')"
if errorlevel 1 exit /b 1

echo.
echo [Indian ID] Preparing Hugging Face model cache for any missing local models...
pushd "%VALIDATOR_DIR%"
python -c "from pathlib import Path; import inference; cfg=inference.get_config(); missing=[data['path'] for data in cfg['models'].values() if not (Path.cwd()/data['path']).exists()]; [inference.hf_hub_download(repo_id=inference.REPO_ID, filename=path) for path in missing]; print('model cache ready:', ', '.join(missing) if missing else 'local model bundle complete')"
if errorlevel 1 (
    popd
    exit /b 1
)
popd

echo.
echo [Indian ID] Verifying inference.py can load the classifier model...
pushd "%VALIDATOR_DIR%"
python -c "import inference; inference.load_model('Id_Classifier'); print('Id_Classifier model load ok')"
if errorlevel 1 (
    popd
    exit /b 1
)
popd

echo.
echo Indian ID validator environment is ready.
echo.
echo Backend environment values:
echo INDIAN_ID_PYTHON=%ID_VENV%\Scripts\python.exe
echo INDIAN_ID_INFERENCE=%VALIDATOR_INFERENCE%
echo.
echo Optional smoke test:
echo test_id_validator.bat "C:\path\to\aadhaar.png"
