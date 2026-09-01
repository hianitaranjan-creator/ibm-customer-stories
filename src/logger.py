"""
logger.py
---------
Handles all log writing for the application.
Writes to a plain-text file (logs/run_log.txt) and keeps an in-memory
list that the Excel writer later puts into the Run Log sheet.
"""

import os
import datetime
from src.config import LOG_FILE, LOGS_DIR

# In-memory log entries for the Run Log Excel sheet.
_log_entries: list[dict] = []

# The current run's statistics (updated as the run progresses).
_run_stats: dict = {
    "run_timestamp": "",
    "mode": "",
    "pages_attempted": 0,
    "pages_succeeded": 0,
    "pages_failed": 0,
    "stories_processed": 0,
    "proof_points_extracted": 0,
    "duration_seconds": 0.0,
    "notes": "",
}


def _now() -> str:
    """Return current date/time as a readable string."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_run(mode: str) -> None:
    """Call at the start of each run to reset statistics."""
    global _run_stats
    _run_stats = {
        "run_timestamp": _now(),
        "mode": mode,
        "pages_attempted": 0,
        "pages_succeeded": 0,
        "pages_failed": 0,
        "stories_processed": 0,
        "proof_points_extracted": 0,
        "duration_seconds": 0.0,
        "notes": "",
    }
    os.makedirs(LOGS_DIR, exist_ok=True)
    info(f"=== Run started | Mode: {mode} ===")


def info(message: str) -> None:
    """Write an informational message."""
    _write("INFO", message)


def warn(message: str) -> None:
    """Write a warning message."""
    _write("WARN", message)


def error(message: str) -> None:
    """Write an error message."""
    _write("ERROR", message)


def _write(level: str, message: str) -> None:
    line = f"[{_now()}] [{level}] {message}"
    print(line)  # also show in the terminal window
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def increment(field: str, amount: int = 1) -> None:
    """Increment a counter in the current run statistics."""
    if field in _run_stats:
        _run_stats[field] += amount


def finalise_run(duration: float, notes: str = "") -> dict:
    """Call at the end of a run to record final stats. Returns the stats dict."""
    _run_stats["duration_seconds"] = round(duration, 1)
    _run_stats["notes"] = notes
    info(f"=== Run finished in {duration:.1f}s | "
         f"Stories: {_run_stats['stories_processed']} | "
         f"Proofs: {_run_stats['proof_points_extracted']} | "
         f"Failures: {_run_stats['pages_failed']} ===")
    return dict(_run_stats)
