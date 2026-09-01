"""
dashboard.py
------------
IBM Customer Proof Intelligence dashboard.
Dark Carbon-style shell. Data embedded as inline JS (works from file://).
Tabs: Overview · Explore · Coverage

Template file: output/dashboard/index.html (static preview with empty data).
Data injection: replaces the _RAW sentinel line with real story/proof JSON.
"""

import json
import os
from src.config import DASH_DIR, DASH_DATA, DASH_HTML
from src import logger

# ── Template HTML path (static preview file with empty data sentinel) ─────────
_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "dashboard", "index.html")
# Sentinel that appears in the template; Python replaces it with real data.
_RAW_SENTINEL = 'const _RAW = {"stories":[],"proof_points":[]};'

# Read template once at import time so the output file can be overwritten freely.
def _load_template() -> str:
    path = os.path.normpath(_TEMPLATE_PATH)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Dashboard template not found: {path!r}")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if _RAW_SENTINEL not in content:
        raise ValueError(
            f"Dashboard template at {path!r} is missing the _RAW sentinel.\n"
            f"Expected:  {_RAW_SENTINEL!r}\n"
            "Restore the template file from version control."
        )
    return content

_TEMPLATE_HTML: str = _load_template()


def _slim_stories(stories: list[dict]) -> list[dict]:
    return [{k: v for k, v in s.items() if k not in ("body_text", "proof_points")} for s in (stories or [])]


def _slim_proofs(proof_points: list[dict]) -> list[dict]:
    out = []
    for p in (proof_points or []):
        sp = dict(p)
        if isinstance(sp.get("gtm_motions"), list):
            sp["gtm_motions"] = "; ".join(sp["gtm_motions"])
        out.append(sp)
    return out


def write_dashboard_data(stories: list[dict], proof_points: list[dict]) -> None:
    """Write data.json alongside the HTML (kept as a backup/reference copy)."""
    os.makedirs(DASH_DIR, exist_ok=True)
    slim_s = _slim_stories(stories)
    slim_p = _slim_proofs(proof_points)
    payload = {"stories": slim_s, "proof_points": slim_p}
    with open(DASH_DATA, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"Dashboard data written: {DASH_DATA}")
    return slim_s, slim_p


def write_dashboard_html(stories: list[dict] = None, proof_points: list[dict] = None) -> None:
    """Inject real story data into the dashboard template and write the output HTML."""
    os.makedirs(DASH_DIR, exist_ok=True)
    slim_s = _slim_stories(stories)
    slim_p = _slim_proofs(proof_points)
    data_js = json.dumps({"stories": slim_s, "proof_points": slim_p}, ensure_ascii=False)
    html = _build_html(data_js)
    with open(DASH_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Dashboard HTML written: {DASH_HTML}")
    # Also copy to repo root for GitHub Pages
    root_index = os.path.join(os.path.dirname(__file__), "..", "index.html")
    try:
        with open(root_index, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Dashboard copied to root: {root_index}")
    except OSError as e:
        logger.warn(f"Could not write root index.html: {e}")


def _build_html(data_js: str) -> str:
    """Inject the real _RAW data payload into the cached template HTML."""
    injected = f"const _RAW = {data_js};"
    return _TEMPLATE_HTML.replace(_RAW_SENTINEL, injected, 1)
