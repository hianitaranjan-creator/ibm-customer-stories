@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM  6_REBUILD_DASHBOARD.bat
REM  Step 1: Run the Crawlee crawler to collect IBM case study data
REM  Step 2: Map the crawler JSON to the dashboard schema
REM  Step 3: Open the rebuilt dashboard
REM
REM  Prerequisite: Node.js installed, npm install already run (1_SETUP.bat)
REM  Usage: Double-click this file
REM ═══════════════════════════════════════════════════════════════════════════

setlocal
set NODE="C:\Program Files\nodejs\node.exe"
set TSNODE=node_modules\ts-node\dist\bin.js
set PYTHON=.venv\Scripts\python.exe
set CRAWLER=scripts\crawl-ibm-case-studies.ts
set BRIDGE=scripts\json-to-dashboard.py
set DASHBOARD=output\dashboard\index.html

echo.
echo ══════════════════════════════════════════════════════════
echo   IBM Customer Stories — Dashboard Rebuild
echo ══════════════════════════════════════════════════════════
echo.

REM ── Step 1: Crawl ──────────────────────────────────────────────────────────
echo [1/3] Running crawler (--all mode)...
echo       This may take several minutes for the full catalogue.
echo.
%NODE% %TSNODE% %CRAWLER% --all
if ERRORLEVEL 1 (
    echo.
    echo  ERROR: Crawler failed. Check the output above.
    echo  TIP: Run "1_SETUP.bat" first if node_modules is missing.
    pause
    exit /b 1
)

echo.
echo [2/3] Mapping crawler data to dashboard schema...
%PYTHON% %BRIDGE%
if ERRORLEVEL 1 (
    echo.
    echo  ERROR: Bridge script failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo [3/3] Opening dashboard...
start "" "%DASHBOARD%"

echo.
echo ══════════════════════════════════════════════════════════
echo   DONE — Dashboard rebuilt and opened.
echo ══════════════════════════════════════════════════════════
echo.
pause
