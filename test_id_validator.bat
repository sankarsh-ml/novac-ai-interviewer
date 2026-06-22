@echo off
setlocal

cd /d "%~dp0"

if "%~1"=="" (
    echo Usage: test_id_validator.bat "C:\path\to\aadhaar.png"
    exit /b 1
)

call id_venv\Scripts\activate
cd indian-id-validator
python inference.py "%~1" --model Aadhaar --no-save-json
