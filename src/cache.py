"""
cache.py
--------
Saves downloaded web pages to the 'cache/' folder so they never need to
be downloaded again.  Each page is stored as a plain HTML file whose
name is derived from the page URL.
"""

import os
import hashlib
import re
from src.config import CACHE_DIR
from src import logger


def _url_to_filename(url: str) -> str:
    """
    Turn a URL into a safe filename.
    e.g. https://www.ibm.com/case-studies/acme  →  ibm_case-studies_acme.html
    We append an MD5 hash of the full URL to avoid collisions between
    pages whose slugs happen to be identical.
    """
    # Remove protocol and www.
    clean = re.sub(r"^https?://(www\.)?", "", url)
    # Replace path separators and special chars with underscores.
    clean = re.sub(r"[^a-zA-Z0-9\-]", "_", clean)
    # Trim long names, then append a short hash for uniqueness.
    short = clean[:80].strip("_")
    digest = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{short}_{digest}.html"


def exists(url: str) -> bool:
    """Return True if this URL is already cached on disk."""
    path = get_path(url)
    return os.path.isfile(path)


def get_path(url: str) -> str:
    """Return the full file path where this URL's HTML would be stored."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, _url_to_filename(url))


def save(url: str, html: str) -> None:
    """Write the HTML content for a URL to the cache."""
    path = get_path(url)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Cached: {url}  →  {os.path.basename(path)}")


def load(url: str) -> str | None:
    """
    Load the HTML for a URL from the cache.
    Returns None if the page is not cached yet.
    """
    path = get_path(url)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def cache_size() -> int:
    """Return the number of pages currently in the cache."""
    if not os.path.isdir(CACHE_DIR):
        return 0
    return len([f for f in os.listdir(CACHE_DIR) if f.endswith(".html")])
