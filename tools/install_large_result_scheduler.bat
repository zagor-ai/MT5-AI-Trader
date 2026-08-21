@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "TASK_NAME=XAU Strategy Research - Large Result Audit"
set "SCRIPT=%CD%\tools\run_large_result_publisher.bat"

where schtasks >nul 2>&1 || (
    echo [ERROR] schtasks.exe was not found.
    exit /b 1
)

rem Run every 5 minutes. The publisher is idempotent, so unchanged data creates no commit.
schtasks /Create /SC MINUTE /MO 5 /TN "%TASK_NAME%" /TR "\"%SCRIPT%\"" /F
if errorlevel 1 (
    echo.
    echo [ERROR] Could not create the scheduled task.
    echo Try running this BAT as Administrator if Windows denies task creation.
    exit /b 1
)

echo.
echo [OK] Scheduled task installed:
echo      %TASK_NAME%
echo [OK] It checks results\ranked_strategies.json every 5 minutes.
echo [OK] No upload occurs unless the large file SHA-256 changed.
echo [OK] Only compact audit files are committed and pushed.
