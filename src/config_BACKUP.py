"""
config.py
---------
All settings for the IBM Customer Stories application live here.
If you ever want to change a behaviour (e.g. wait longer between pages),
you only need to change this one file.
"""

import os

# ── Paths ──────────────────────────────────────────────────────────────────
# BASE_DIR is the root of the project (the IBM_Customer_Stories folder).
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR   = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
DASH_DIR    = os.path.join(OUTPUT_DIR, "dashboard")
LOGS_DIR    = os.path.join(BASE_DIR, "logs")
LOG_FILE    = os.path.join(LOGS_DIR, "run_log.txt")

EXCEL_TEST  = os.path.join(OUTPUT_DIR, "IBM_Customer_Stories_TEST.xlsx")
EXCEL_FULL  = os.path.join(OUTPUT_DIR, "IBM_Customer_Stories.xlsx")
DASH_DATA   = os.path.join(DASH_DIR,   "data.json")
DASH_HTML   = os.path.join(DASH_DIR,   "index.html")

# ── IBM website ────────────────────────────────────────────────────────────
IBM_BASE          = "https://www.ibm.com"
CASE_STUDIES_URL  = "https://www.ibm.com/case-studies"
ROBOTS_URL        = "https://www.ibm.com/robots.txt"

# ── Scraper behaviour ──────────────────────────────────────────────────────
REQUEST_DELAY_SEC = 1.5   # Minimum seconds between HTTP requests
MAX_RETRIES       = 3     # How many times to retry a failed page
RETRY_DELAY_SEC   = 5     # Seconds to wait before each retry
REQUEST_TIMEOUT   = 30    # Seconds before giving up on a single request
TEST_STORY_LIMIT  = 10    # Number of stories to fetch in test mode

# Browser-like headers so the server knows we are a research tool.
# We identify ourselves honestly as a researcher.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; IBMCustomerStoriesResearch/1.0; "
        "+https://www.ibm.com)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── GTM motions ────────────────────────────────────────────────────────────
GTM_MOTIONS = [
    "Real-time data and context",
    "Governed data for AI",
    "Data integration and modernization",
    "Cost and workload optimization",
]

# Keywords that hint at each GTM motion (used by the classifier).
GTM_KEYWORDS = {
    "Real-time data and context": [
        "real-time", "real time", "streaming", "low latency", "low-latency",
        "inference", "event-driven", "live data", "instant", "millisecond",
        "kafka", "eventstreams", "event streams",
    ],
    "Governed data for AI": [
        "governance", "data quality", "lineage", "compliance", "trust",
        "ai readiness", "catalog", "metadata", "data fabric", "watson knowledge",
        "data steward", "master data", "mdm", "regulatory", "gdpr", "audit",
        "ibm knowledge catalog", "datastage", "wkc",
    ],
    "Data integration and modernization": [
        "migration", "modernization", "modernisation", "hybrid cloud",
        "legacy", "integration", "etl", "data pipeline", "cloud pak for data",
        "lift and shift", "data lake", "lakehouse", "data warehouse",
        "db2", "informix", "netezza", "datastage",
    ],
    "Cost and workload optimization": [
        "cost reduction", "cost saving", "savings", "efficiency",
        "workload", "consolidat", "infrastructure", "tco", "total cost",
        "faster", "performance improvement", "throughput", "scalab",
        "resource utilization", "opex", "capex",
    ],
}

# ── Geographies ────────────────────────────────────────────────────────────
GEOGRAPHIES = [
    "North America",
    "EMEA",
    "APAC",
    "Japan",
    "Latin America",
    "Other / Global",
]

# ── Proof-strength labels ──────────────────────────────────────────────────
PROOF_STRENGTHS = ["Strong", "Medium", "Weak", "Restricted"]
