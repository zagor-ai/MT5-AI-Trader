@echo off
setlocal EnableExtensions
cd /d "%~dp0..\..\.."

set "REPO=https://github.com/zagor-ai/MT5-AI-Trader.git"
set "BRANCH=feature/tpb-m5-001"
set "PROJECT=%CD%\TPB-M5-001"

echo ============================================================
echo TPB-M5-001 - GitHub installer and research runner
echo ============================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git is not installed or not in PATH.
  echo Install Git for Windows, then run this file again.
  pause
  exit /b 1
)

if not exist "%PROJECT%\.git" (
  echo [1/5] Cloning TPB branch from GitHub...
  git clone --branch "%BRANCH%" --single-branch "%REPO%" "%PROJECT%"
  if errorlevel 1 (
    echo ERROR: Git clone failed.
    pause
    exit /b 1
  )
) else (
  echo [1/5] Existing project found. Updating from GitHub...
  pushd "%PROJECT%"
  git fetch origin "%BRANCH%"
  git checkout "%BRANCH%"
  git pull --ff-only origin "%BRANCH%"
  if errorlevel 1 (
    echo ERROR: Git update failed.
    popd
    pause
    exit /b 1
  )
  popd
)

echo [2/5] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found.
  echo Activate your Anaconda environment or add Python to PATH.
  pause
  exit /b 1
)

echo [3/5] Installing/checking Python packages...
python -m pip install --upgrade pip
python -m pip install MetaTrader5 pandas numpy
if errorlevel 1 (
  echo ERROR: Python package installation failed.
  pause
  exit /b 1
)

echo [4/5] Checking MetaTrader 5...
if not exist "%PROJECT%\research\strategies\TPB_M5_001.py" (
  echo ERROR: TPB_M5_001.py was not found after GitHub download.
  pause
  exit /b 1
)

echo.
echo IMPORTANT:
echo - MetaTrader 5 must be OPEN.
echo - XAUUSD must be available in Market Watch.
echo - This research script sends NO live orders.
echo.
pause

echo [5/5] Running TPB-M5-001...
pushd "%PROJECT%\research\strategies"
python TPB_M5_001.py
set "RC=%ERRORLEVEL%"
popd

echo.
echo ============================================================
if "%RC%"=="0" (
  echo TPB-M5-001 finished successfully.
  echo Evidence is under:
  echo %PROJECT%\research\strategies\research_runs
) else (
  echo TPB-M5-001 FAILED. Exit code: %RC%
)
echo ============================================================
pause
exit /b %RC%
