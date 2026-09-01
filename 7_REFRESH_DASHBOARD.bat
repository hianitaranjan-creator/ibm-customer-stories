@echo off
title IBM Customer Stories — Refresh Dashboard
color 1F
echo.
echo ════════════════════════════════════════════════════════════
echo   IBM Customer Stories — Refresh Dashboard
echo ════════════════════════════════════════════════════════════
echo.
echo This script will:
echo   1. Apply any corrections you exported from the Review Queue
echo   2. Discover any NEW story URLs added to ibm.com/case-studies
echo   3. Scrape only the new stories (already-scraped ones are skipped)
echo   4. Rebuild the dashboard with ALL stories
echo   5. Open the dashboard in your browser
echo.
echo   Already-scraped stories are never re-downloaded.
echo   On a first run this takes ~1 hour for 1183 stories.
echo   On refresh runs it only fetches what is new (usually minutes).
echo.
echo Press any key to start, or close this window to cancel.
pause >nul

echo.
echo ── Step 1 of 4: Apply corrections (if corrections.json exists) ──
echo.
if exist "corrections.json" (
    .venv\Scripts\python.exe scripts\apply-corrections.py
    if ERRORLEVEL 1 (
        color 4F
        echo.
        echo ERROR: apply-corrections.py failed. Check output above.
        pause
        exit /b 1
    )
) else (
    echo   No corrections.json found — skipping.
    echo   Tip: Export corrections from the Review Queue in the dashboard.
)

echo.
echo ── Step 2 of 4: Discover all story URLs ────────────────────
echo.
node scripts\discover-story-urls.js --all
if ERRORLEVEL 1 (
    color 4F
    echo.
    echo ERROR: URL discovery failed. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo ── Step 3 of 4: Scrape story details ───────────────────────
echo   (New stories only — already-scraped ones are skipped)
echo.
node scripts\scrape-story-details.js --all
if ERRORLEVEL 1 (
    color 4F
    echo.
    echo ERROR: Scraping failed. You can run this file again to resume.
    pause
    exit /b 1
)

echo.
echo ── Step 4 of 4: Rebuild dashboard ──────────────────────────
echo.
.venv\Scripts\python.exe scripts\json-to-dashboard.py
if ERRORLEVEL 1 (
    color 4F
    echo.
    echo ERROR: Dashboard build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo ── Step 4 of 4: Sync GitHub Pages (root index.html) ────────
echo.
copy /Y "output\dashboard\index.html" "index.html" >nul
echo   Copied output\dashboard\index.html  →  index.html (GitHub Pages root)

echo.
echo Opening dashboard...
start "" "output\dashboard\index.html"

echo.
color 2F
echo ════════════════════════════════════════════════════════════
echo   DONE — Dashboard refreshed and opened.
echo.
echo   Dashboard:       output\dashboard\index.html
echo   GitHub Pages:    index.html  ← push this to update the live URL
echo   Stories:         public\data\all-case-studies.json
echo.
echo   To publish to GitHub, open Command Prompt here and run:
echo     git add index.html
echo     git commit -m "Daily refresh"
echo     git push
echo.
echo   Tip: Use the Review Queue in the dashboard to fix 'Needs review' fields.
echo        Export corrections.json, place it in this folder, then refresh again.
echo ════════════════════════════════════════════════════════════
echo.
pause
