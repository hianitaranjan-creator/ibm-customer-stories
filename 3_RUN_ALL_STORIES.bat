@echo off
title IBM Customer Stories — FULL RUN (all stories)
color 1F
echo.
echo ============================================================
echo   IBM Customer Stories — Full Run (ALL stories)
echo ============================================================
echo.
echo This will download ALL case studies from www.ibm.com/case-studies.
echo.
echo   - Pages already in the cache will NOT be re-downloaded.
echo   - New pages are fetched slowly (1.5 seconds apart).
echo   - Depending on how many stories exist, this may take
echo     15-60 minutes for a first run.
echo   - Output:  output\IBM_Customer_Stories.xlsx
echo.
echo Please do NOT close this window while it is running.
echo.

REM ── Check setup has been run ─────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    color 4F
    echo ERROR: Setup has not been run yet.
    echo Please double-click  1_SETUP.bat  first.
    echo.
    pause
    exit /b 1
)

echo Starting full collection...
echo.
.venv\Scripts\python.exe run.py --mode full
if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo.
    echo Something went wrong. Please check the messages above.
    echo The full log is in:  logs\run_log.txt
    pause
    exit /b 1
)

echo.
echo Opening dashboard in your browser...
start "" "output\dashboard\index.html"

echo.
color 2F
echo ============================================================
echo   FULL RUN COMPLETE
echo.
echo   Excel file:  output\IBM_Customer_Stories.xlsx
echo   Dashboard:   output\dashboard\index.html
echo   Log file:    logs\run_log.txt
echo ============================================================
echo.
pause
