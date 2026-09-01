@echo off
title IBM Customer Stories — SETUP
color 1F
echo.
echo ============================================================
echo   IBM Customer Stories — One-Time Setup
echo ============================================================
echo.
echo This will:
echo   1. Check that Node.js is installed (needed for the Crawlee crawler)
echo   2. Create a private Python environment inside this folder
echo   3. Install the required packages (requests, openpyxl, Tavily, etc.)
echo   4. Install Node.js packages (Crawlee, TypeScript)
echo   5. Save your Tavily API key so the scraper can find more stories
echo.
echo Nothing will be installed on the rest of your computer.
echo This takes about 2-3 minutes. Please wait...
echo.

REM ── Check Node.js is available ───────────────────────────────────────────
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 6F
    echo WARNING: Node.js was not found on your computer.
    echo.
    echo The Crawlee crawler needs Node.js to find all IBM stories.
    echo Please install it from: https://nodejs.org/en/download/prebuilt-installer
    echo Choose the LTS version for Windows x64, run the .msi installer,
    echo keep all defaults, then run this setup file again.
    echo.
    echo (You can still use the Python tools without Node.js)
    echo.
    pause
    color 1F
) else (
    echo Node.js found:
    node --version
    echo.
    echo Installing Node.js packages (Crawlee, TypeScript^) ...
    node node_modules\npm\bin\npm-cli.js install --quiet 2>nul
    if exist package.json (
        node node_modules\..\npm\bin\npm-cli.js install 2>nul
    )
    echo Node.js packages ready.
    echo.
)

REM ── Check Python is available ────────────────────────────────────────────
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo ERROR: Python was not found on your computer.
    echo.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to tick "Add Python to PATH" during installation.
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM ── Create virtual environment ───────────────────────────────────────────
echo Creating private Python environment (.venv) ...
python -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo ERROR: Could not create the virtual environment.
    echo Please check that Python is installed correctly.
    pause
    exit /b 1
)
echo Done.
echo.

REM ── Install packages ─────────────────────────────────────────────────────
echo Installing required packages (including Tavily) ...
echo (This may take 1-2 minutes on a slow connection)
echo.
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\pip.exe install -r requirements.txt --quiet --only-binary :all:
if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo ERROR: Package installation failed.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)
echo Packages installed.
echo.

REM ── Tavily API key setup ─────────────────────────────────────────────────
echo ============================================================
echo   TAVILY API KEY SETUP
echo ============================================================
echo.
echo Tavily is a free search service that finds MORE IBM customer
echo stories than the website alone shows.
echo.
echo To get your free key (takes 2 minutes):
echo   1. Go to https://app.tavily.com/sign-up
echo   2. Sign up with your email
echo   3. Copy the API key shown on your dashboard
echo      (it starts with  tvly-  )
echo.

REM Check if .env already has a key
if exist .env (
    findstr /C:"TAVILY_API_KEY=tvly-" .env >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo A Tavily API key is already saved in .env
        echo If you want to change it, delete the .env file and run setup again.
        goto :setup_done
    )
)

echo Please paste your Tavily API key below and press Enter.
echo (If you want to skip this for now, just press Enter with nothing typed)
echo.
set /p TAVILY_KEY="Paste your key here: "

if "%TAVILY_KEY%"=="" (
    echo.
    echo No key entered. The scraper will still work but will only find
    echo the stories visible on the IBM website directly (~33 stories).
    echo Run setup again any time to add your key.
    echo.
    REM Write a placeholder .env so the app doesn't crash
    echo TAVILY_API_KEY=> .env
) else (
    echo TAVILY_API_KEY=%TAVILY_KEY%> .env
    echo.
    echo Key saved to .env  — Tavily is ready to use!
    echo.
    REM Quick validation
    .venv\Scripts\python.exe -c "from tavily import TavilyClient; c = TavilyClient('%TAVILY_KEY%'); print('Tavily connection: OK')" 2>nul
    if %ERRORLEVEL% NEQ 0 (
        color 6F
        echo WARNING: Could not connect to Tavily with that key.
        echo Please check the key is correct and try setup again.
        color 1F
    )
)

:setup_done
echo.
echo ============================================================
color 2F
echo   SETUP COMPLETE — You are ready to go!
echo.
echo   Next step: Double-click  2_TEST_10_STORIES.bat
echo ============================================================
echo.
pause
