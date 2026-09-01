"""
scraper.py
----------
Fetches pages from the IBM case-studies website.

Discovery strategy (in priority order):
  1. TAVILY (if TAVILY_API_KEY is set in .env)
     - Searches Tavily for site:ibm.com/case-studies to discover ALL story URLs.
     - Then uses Tavily Extract to pull clean page content for each story
       (no HTML parsing needed — Tavily returns just the text).
     - Typically finds 100-300+ stories vs the ~33 visible in plain HTML.

  2. REQUESTS FALLBACK (if no Tavily key)
     - Fetches the IBM listing page(s) with plain HTTP requests.
     - Only sees the ~33 stories pre-rendered in the initial HTML.
     - Still useful as a baseline or for testing.

Rules followed in both modes:
  - Waits at least REQUEST_DELAY_SEC between every HTTP request.
  - Retries failed pages up to MAX_RETRIES times.
  - Uses the local cache: already-downloaded pages are NOT re-fetched.
  - Never logs in, never sends credentials, only reads public pages.
"""

import os
import time
import urllib.robotparser
import requests

from src import cache, logger
from src.config import (
    IBM_BASE, CASE_STUDIES_URL, ROBOTS_URL,
    REQUEST_DELAY_SEC, MAX_RETRIES, RETRY_DELAY_SEC,
    REQUEST_TIMEOUT, REQUEST_HEADERS, TEST_STORY_LIMIT,
)

# ── Load .env (TAVILY_API_KEY lives here) ─────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — key must be in the system environment

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Tavily-based discovery and extraction
# ─────────────────────────────────────────────────────────────────────────────

def _tavily_discover_urls(test_mode: bool = False) -> list[str]:
    """
    Use Tavily's search API to find IBM case-study URLs.

    Tavily searches the live web index for pages at ibm.com/case-studies,
    returning far more results than the IBM listing page shows directly.
    We run multiple targeted queries to maximise coverage.
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        logger.warn("tavily-python not installed. Run 1_SETUP.bat again.")
        return []

    client = TavilyClient(api_key=TAVILY_API_KEY)
    found: list[str] = []
    seen: set[str] = set()

    # Multiple search queries to maximise coverage across different story types.
    # Tavily returns up to 20 results per query; varied queries surface different stories.
    queries = [
        "site:ibm.com/case-studies customer story",
        "site:ibm.com/case-studies AI watsonx",
        "site:ibm.com/case-studies data modernization",
        "site:ibm.com/case-studies cloud transformation",
        "site:ibm.com/case-studies financial services",
        "site:ibm.com/case-studies healthcare",
        "site:ibm.com/case-studies manufacturing",
        "site:ibm.com/case-studies government",
        "site:ibm.com/case-studies retail",
        "site:ibm.com/case-studies energy utilities",
        "site:ibm.com/case-studies IBM Power",
        "site:ibm.com/case-studies IBM Z mainframe",
        "site:ibm.com/case-studies Red Hat OpenShift",
        "site:ibm.com/case-studies IBM Consulting",
        "site:ibm.com/case-studies cost optimization",
    ]

    # In test mode only run the first 2 queries (enough to find 10 stories).
    if test_mode:
        queries = queries[:2]

    logger.info(f"Tavily discovery: running {len(queries)} search queries…")

    for i, query in enumerate(queries, 1):
        if test_mode and len(found) >= TEST_STORY_LIMIT:
            break
        try:
            logger.info(f"  Tavily query {i}/{len(queries)}: {query}")
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=20,
                include_domains=["ibm.com"],
            )
            new_this_query = 0
            for result in response.get("results", []):
                url = result.get("url", "").split("?")[0].split("#")[0].rstrip("/")
                if "/case-studies/" not in url:
                    continue
                slug = url.split("/case-studies/")[-1]
                if not slug or slug in ("", "all"):
                    continue
                if url not in seen:
                    seen.add(url)
                    found.append(url)
                    new_this_query += 1
                    logger.info(f"    Found: {url}")
            logger.info(f"    {new_this_query} new URLs this query (total: {len(found)})")
            # Be polite — small delay between Tavily API calls.
            time.sleep(0.5)
        except Exception as exc:
            logger.warn(f"  Tavily query failed: {exc}")

    logger.info(f"Tavily discovery complete: {len(found)} unique story URLs found.")
    return found[:TEST_STORY_LIMIT] if test_mode else found


def _tavily_extract_content(url: str) -> str | None:
    """
    Use Tavily's Extract API to get clean page text for a story URL.
    Returns the extracted text, or None if extraction fails.
    The result is saved to the local cache so it is not re-fetched.
    """
    # Check cache first (same cache used by plain requests).
    cached = cache.load(url)
    if cached is not None:
        logger.info(f"Cache hit: {url}")
        return cached

    try:
        from tavily import TavilyClient
    except ImportError:
        return None

    client = TavilyClient(api_key=TAVILY_API_KEY)
    try:
        logger.info(f"Tavily extract: {url}")
        logger.increment("pages_attempted")
        time.sleep(REQUEST_DELAY_SEC)
        response = client.extract(urls=[url])
        results = response.get("results", [])
        if results:
            raw_content = results[0].get("raw_content", "")
            if raw_content:
                # Wrap in minimal HTML so the existing parser (BeautifulSoup) works.
                # Tavily returns clean text; we wrap it so the parser doesn't need
                # to handle a completely different format.
                html = (
                    f"<html><head><title>{url}</title></head>"
                    f"<body><article>{raw_content}</article></body></html>"
                )
                cache.save(url, html)
                logger.increment("pages_succeeded")
                return html
    except Exception as exc:
        logger.warn(f"Tavily extract failed for {url}: {exc}")

    logger.increment("pages_failed")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# robots.txt (used by the requests fallback path)
# ─────────────────────────────────────────────────────────────────────────────

_robots_checked = False
_rp = urllib.robotparser.RobotFileParser()


def check_robots() -> None:
    """Download and parse IBM's robots.txt once per session."""
    global _robots_checked
    if _robots_checked:
        return
    logger.info(f"Fetching robots.txt from {ROBOTS_URL}")
    _rp.set_url(ROBOTS_URL)
    try:
        _rp.read()
        _robots_checked = True
        logger.info("robots.txt loaded successfully.")
    except Exception as exc:
        logger.warn(f"Could not read robots.txt ({exc}). Proceeding carefully.")
        _robots_checked = True


def is_allowed(url: str) -> bool:
    """Return True if robots.txt permits fetching this URL."""
    if not _robots_checked:
        check_robots()
    allowed = _rp.can_fetch(REQUEST_HEADERS["User-Agent"], url)
    if not allowed:
        logger.warn(f"robots.txt disallows: {url}")
    return allowed


# ─────────────────────────────────────────────────────────────────────────────
# Core requests-based fetch (fallback when no Tavily key)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_url(url: str) -> str | None:
    """
    Download a single URL using plain requests, with retry logic.
    Returns the HTML text, or None on persistent failure.
    """
    cached = cache.load(url)
    if cached is not None:
        logger.info(f"Cache hit: {url}")
        return cached

    if not is_allowed(url):
        logger.warn(f"Skipping (disallowed by robots.txt): {url}")
        return None

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Fetching (attempt {attempt}/{MAX_RETRIES}): {url}")
            logger.increment("pages_attempted")
            time.sleep(REQUEST_DELAY_SEC)
            resp = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text
            cache.save(url, html)
            logger.increment("pages_succeeded")
            return html
        except requests.RequestException as exc:
            last_error = exc
            logger.warn(f"Request failed (attempt {attempt}): {exc}")
            if attempt < MAX_RETRIES:
                logger.info(f"Waiting {RETRY_DELAY_SEC}s before retry…")
                time.sleep(RETRY_DELAY_SEC)

    logger.error(f"All {MAX_RETRIES} attempts failed for: {url}  Reason: {last_error}")
    logger.increment("pages_failed")
    return None


def _requests_discover_urls(test_mode: bool = False) -> list[str]:
    """
    Fallback discovery: fetch the IBM listing page(s) with plain requests.
    Only sees ~33 stories pre-rendered in the initial HTML.
    """
    check_robots()
    logger.info("Requests-based discovery (fallback — no Tavily key configured)…")

    found: list[str] = []
    seen: set[str] = set()

    pages_to_try = [CASE_STUDIES_URL]
    for p in range(2, 31):
        pages_to_try.append(f"{CASE_STUDIES_URL}?page={p}")

    from bs4 import BeautifulSoup

    for listing_url in pages_to_try:
        if test_mode and len(found) >= TEST_STORY_LIMIT:
            break

        html = _fetch_url(listing_url)
        if not html:
            logger.warn(f"Could not fetch listing page: {listing_url}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        new_on_this_page = 0

        for a_tag in soup.find_all("a", href=True):
            href: str = a_tag["href"]
            if href.startswith("/"):
                href = IBM_BASE + href
            if not href.startswith("http"):
                continue
            if "/case-studies/" not in href:
                continue
            path_part = href.split("?")[0].split("#")[0]
            if path_part.rstrip("/") == CASE_STUDIES_URL.rstrip("/"):
                continue
            slug = path_part.rstrip("/").split("/case-studies/")[-1]
            if not slug or slug in ("", "all"):
                continue
            if path_part not in seen:
                seen.add(path_part)
                found.append(path_part)
                new_on_this_page += 1
                logger.info(f"Found story URL: {path_part}")
            if test_mode and len(found) >= TEST_STORY_LIMIT:
                break

        logger.info(f"Listing page {listing_url}: {new_on_this_page} new URLs (total: {len(found)})")
        if new_on_this_page == 0:
            logger.info("No new URLs on this page — stopping pagination.")
            break

    logger.info(f"Total story URLs discovered: {len(found)}")
    return found[:TEST_STORY_LIMIT] if test_mode else found


# ─────────────────────────────────────────────────────────────────────────────
# Public API — called by run.py
# ─────────────────────────────────────────────────────────────────────────────

def discover_story_urls(test_mode: bool = False) -> list[str]:
    """
    Discover all IBM case-study URLs.

    Uses Tavily if TAVILY_API_KEY is set in .env, otherwise falls back
    to plain requests (which only sees ~33 stories).
    """
    if TAVILY_API_KEY and TAVILY_API_KEY.startswith("tvly-"):
        logger.info("Tavily API key found — using Tavily for discovery (finds more stories).")
        urls = _tavily_discover_urls(test_mode=test_mode)
        if urls:
            return urls
        logger.warn("Tavily discovery returned no results — falling back to requests.")
    else:
        logger.info(
            "No Tavily API key configured. "
            "Tip: run 1_SETUP.bat and enter your free key to find more stories."
        )

    return _requests_discover_urls(test_mode=test_mode)


def fetch_story(url: str) -> str | None:
    """
    Download (or load from cache) a single story page.

    Uses Tavily Extract if a key is configured (returns cleaner text),
    otherwise falls back to plain requests.
    """
    if TAVILY_API_KEY and TAVILY_API_KEY.startswith("tvly-"):
        result = _tavily_extract_content(url)
        if result:
            return result
        logger.warn(f"Tavily extract failed for {url} — trying plain requests.")

    return _fetch_url(url)
