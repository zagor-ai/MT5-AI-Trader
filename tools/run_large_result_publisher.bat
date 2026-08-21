@echo off
setlocal
cd /d "%~dp0.."

set PYTHON=C:\Program Files\Python312\python.exe
if not exist "%PYTHON%" set PYTHON=py

"%PYTHON%" tools\large_result_publisher.py --once
if errorlevel 1 (
    echo.
    echo [ERROR] Large-result publisher failed.
    exit /b 1
)

echo.
echo [OK] Large-result audit publish completed.
