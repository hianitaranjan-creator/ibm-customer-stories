"""
json-to-dashboard.py  (Sub-Task 8)
-----------------------------------
Bridge script: reads the Crawlee-produced JSON from public/data/all-case-studies.json
and maps every story to the Python dashboard schema, then regenerates index.html.

Usage:
    python scripts/json-to-dashboard.py
    python scripts/json-to-dashboard.py --data-platform   # filter to Data Platform stories only

The crawler JSON schema (TypeScript output):
    id, canonicalUrl, clientName, title, description, industry, geography,
    productCategories[], productsMentioned[], topics[], challenge, solution,
    businessOutcomes, quantifiedProof, customerQuote, publicationDate,
    lastUpdatedDate, collectedAt

The dashboard schema (Python pipeline):
    story_id, customer_name, named_unnamed, client_zero, business_partner,
    industry, sub_industry, geography, products (CSV), gtm_motions (semicolon),
    open_governed_hybrid, structured_unstructured, proof_strength,
    publication_date, publication_age_months, source_url, title, qa_flag
"""

import json
import os
import sys
import re
from datetime import datetime, date

# Allow running from root or from scripts/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT       = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _ROOT)

from src.config import GTM_KEYWORDS, GTM_MOTIONS, OUTPUT_DIR, DASH_DIR, DASH_DATA, DASH_HTML

# ── Paths ─────────────────────────────────────────────────────────────────────

CRAWLER_ALL         = os.path.join(_ROOT, "public", "data", "all-case-studies.json")
CRAWLER_DP          = os.path.join(_ROOT, "public", "data", "data-platform-case-studies.json")

DATA_PLATFORM_ONLY = "--data-platform" in sys.argv

SOURCE_FILE = CRAWLER_DP if DATA_PLATFORM_ONLY else CRAWLER_ALL

# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Watson / watsonx full product name resolution ─────────────────────────────
# Maps a search pattern (found anywhere in text) → canonical product name.
# Ordered most-specific first so "watsonx.data intelligence" matches before
# "watsonx.data" which matches before plain "watsonx".
_WATSON_PRODUCT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # watsonx sub-products (most specific first)
    (re.compile(r"watsonx[\s.]?data\s+intelligence",        re.IGNORECASE), "watsonx.data Intelligence"),
    (re.compile(r"watsonx[\s.]?data\s+integration",         re.IGNORECASE), "watsonx.data Integration"),
    (re.compile(r"watsonx[\s.]?data",                       re.IGNORECASE), "watsonx.data"),
    (re.compile(r"watsonx[\s.]?ai",                         re.IGNORECASE), "watsonx.ai"),
    (re.compile(r"watsonx[\s.]?assistant",                  re.IGNORECASE), "watsonx Assistant"),
    (re.compile(r"watsonx[\s.]?orchestrate",                re.IGNORECASE), "watsonx Orchestrate"),
    (re.compile(r"watsonx[\s.]?governance",                 re.IGNORECASE), "watsonx.governance"),
    (re.compile(r"watsonx[\s.]?code\s+assistant",           re.IGNORECASE), "watsonx Code Assistant"),
    (re.compile(r"\bwatsonx\b",                             re.IGNORECASE), "watsonx"),
    # Classic Watson products
    (re.compile(r"watson\s+knowledge\s+catalog",            re.IGNORECASE), "Watson Knowledge Catalog"),
    (re.compile(r"watson\s+studio",                         re.IGNORECASE), "Watson Studio"),
    (re.compile(r"watson\s+discovery",                      re.IGNORECASE), "Watson Discovery"),
    (re.compile(r"watson\s+assistant",                      re.IGNORECASE), "Watson Assistant"),
    (re.compile(r"watson\s+machine\s+learning",             re.IGNORECASE), "Watson Machine Learning"),
    (re.compile(r"watson\s+nlp",                            re.IGNORECASE), "Watson NLP"),
    (re.compile(r"watson\s+openscale|openscale",            re.IGNORECASE), "Watson OpenScale"),
    (re.compile(r"\bwatson\b",                              re.IGNORECASE), "Watson"),
]


def _resolve_watson_products(text: str) -> list[str]:
    """
    Scan free text and return the list of specific Watson/watsonx product names
    found, ordered most-specific first and deduplicated.

    e.g. "uses watsonx.data and watsonx.ai" → ["watsonx.data", "watsonx.ai"]
    """
    found: list[str] = []
    for pattern, canonical in _WATSON_PRODUCT_PATTERNS:
        if pattern.search(text) and canonical not in found:
            found.append(canonical)
    return found


def _extract_products(raw: dict) -> str:
    """
    Build the products CSV for a story.

    Priority:
      1. productsMentioned[] from crawler (authoritative when present)
      2. Watson/watsonx products resolved from full body text
      3. Watson/watsonx products resolved from topics[]
      4. Non-watson topics that look like IBM product names
      5. "Needs review" sentinel
    """
    # 1. Crawler-supplied productsMentioned
    mentioned = [p.strip() for p in (raw.get("productsMentioned") or []) if p and p.strip()]
    if mentioned:
        # Still enrich: resolve any "watsonx" / "Watson" entries to full names
        enriched: list[str] = []
        all_body = " ".join(filter(None, [
            raw.get("description"), raw.get("challenge"),
            raw.get("solution"), raw.get("businessOutcomes"),
            raw.get("quantifiedProof"), raw.get("customerQuote"),
        ]))
        watson_from_body = _resolve_watson_products(all_body)
        for p in mentioned:
            # If it's a generic "watsonx" / "Watson" entry, replace with specifics
            if re.match(r"^watsonx$|^watson$", p, re.IGNORECASE) and watson_from_body:
                for wp in watson_from_body:
                    if wp not in enriched:
                        enriched.append(wp)
            else:
                if p not in enriched:
                    enriched.append(p)
        return ", ".join(enriched)

    # 2 + 3. No productsMentioned — resolve from body text + topics
    all_body = " ".join(filter(None, [
        raw.get("description"), raw.get("challenge"),
        raw.get("solution"), raw.get("businessOutcomes"),
        raw.get("quantifiedProof"), raw.get("customerQuote"),
        " ".join(raw.get("topics") or []),
    ]))
    watson_prods = _resolve_watson_products(all_body)
    if watson_prods:
        return ", ".join(watson_prods)

    # 4. Non-watson topics that look like IBM product names
    IBM_TOPIC_PRODUCTS = {
        "instana", "maximo", "turbonomic", "apptio", "envizi", "openpages",
        "guardium", "verify", "qradar", "db2", "datastage", "databand",
        "cloud pak", "openshift", "red hat", "mq", "app connect", "sterling",
        "aspera", "flashsystem", "spectrum", "granite",
    }
    topic_products = [
        t for t in (raw.get("topics") or [])
        if any(ibm in t.lower() for ibm in IBM_TOPIC_PRODUCTS)
    ]
    if topic_products:
        return ", ".join(topic_products)

    return "Needs review"


_QUANTITY_RE = re.compile(
    r"(\d[\d,.]*\s*(?:[%x×]|times|percent|\$|USD|EUR|GBP|£|€|"
    r"million|billion|thousand|hours?|days?|weeks?|months?|years?|"
    r"minutes?|seconds?|TB|GB|MB|KB))|([£$€]\s*\d[\d,.]*)".encode().decode(),
    re.IGNORECASE,
)
_OUTCOME_VERBS_RE = re.compile(
    r"\b(reduc|increas|improv|cut|sav|achiev|deliver|boost|accelerat|"
    r"eliminat|lower|faster|gain|generat|grow|shrink|optimiz|consolidat|"
    r"deploy|migrat|process|handl|complet|resolv|enabl|transform)\b",
    re.IGNORECASE,
)
_RESTRICTED_RE = re.compile(
    r"\b(project|expect|estimat|anticipat|potential|possibl|could save|"
    r"might|forecast|target|up to|as much as|partner-reported|"
    r"unnamed|undisclosed|confidential client)\b",
    re.IGNORECASE,
)

def _tag_gtm(text: str) -> list[str]:
    """Return matched GTM motion labels from body text."""
    lower = text.lower()
    matched = [m for m, kws in GTM_KEYWORDS.items() if any(kw in lower for kw in kws)]
    return matched if matched else ["Needs review"]


def _proof_strength(quantified: str | None, customer_name: str | None, quote: str | None) -> str:
    """Four-tier proof strength from the crawler fields."""
    named = bool(customer_name and customer_name.strip())
    has_qty = bool(quantified and _QUANTITY_RE.search(quantified))
    has_outcome = bool(quantified and _OUTCOME_VERBS_RE.search(quantified))

    # Restricted: forward-looking language
    if quantified and _RESTRICTED_RE.search(quantified):
        return "Restricted"

    # Strong: named + quantified realized result
    if named and has_qty and has_outcome:
        return "Strong"

    # Medium: named + quote or qualitative outcome text
    if named and (quote or (quantified and not has_qty)):
        return "Medium"

    # Weak: product adoption / aspirational
    return "Weak"


def _open_governed_hybrid(categories: list[str], body: str) -> str:
    """Rough OGH classification from product categories and body text."""
    lower = body.lower()
    has_governed = any(kw in lower for kw in [
        "governance", "catalog", "lineage", "compliance", "data quality",
        "master data", "metadata", "wkc", "ibm knowledge catalog",
    ])
    has_open = any(kw in lower for kw in [
        "open source", "open data", "hadoop", "spark", "kafka",
        "apache", "presto", "iceberg", "delta lake",
    ])
    if has_governed and has_open:
        return "Hybrid"
    if has_governed:
        return "Governed"
    if has_open:
        return "Open"
    return "Hybrid"  # default when unclear


def _structured_unstructured(body: str) -> str:
    lower = body.lower()
    has_unstructured = any(kw in lower for kw in [
        "unstructured", "document", "natural language", "nlp", "text analytics",
        "sentiment", "image", "video", "audio", "email", "pdf",
    ])
    has_structured = any(kw in lower for kw in [
        "structured", "relational", "sql", "database", "table", "row", "column",
        "warehouse", "transactional", "etl",
    ])
    if has_structured and has_unstructured:
        return "Both"
    if has_unstructured:
        return "Unstructured"
    return "Structured"


def _months_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        pub = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        today = date.today()
        return (today.year - pub.year) * 12 + (today.month - pub.month)
    except Exception:
        return None


def _is_client_zero(title: str | None, client_name: str | None, topics: list[str]) -> str:
    combined = " ".join(filter(None, [title, client_name] + topics)).lower()
    return "Yes" if "ibm" in combined and "client zero" in combined else "No"


def _is_business_partner(topics: list[str], categories: list[str]) -> str:
    for t in topics + categories:
        if "partner" in t.lower() or "bp " in t.lower():
            return "Yes"
    return "No"


# ── Geography re-inference ────────────────────────────────────────────────────
# Extended keyword map covering all countries IBM case-study pages use as topics.
# Bucket names match the values the crawler already writes ("Americas", "EMEA", etc.)
# so we stay consistent with existing data.
_GEO_REMAP: list[tuple[str, list[str]]] = [
    ("EMEA", [
        "uk", "united kingdom", "britain", "england",
        "germany", "german", "deutschland",
        "france", "french",
        "spain", "spanish",
        "italy", "italian",
        "netherlands", "dutch",
        "belgium", "belgian",
        "sweden", "swedish",
        "norway", "norwegian",
        "denmark", "danish",
        "finland", "finnish",
        "switzerland", "swiss",
        "austria", "austrian",
        "poland", "polish",
        "czech", "czechia",
        "hungary", "hungarian",
        "croatia", "croatian",
        "greece", "greek",
        "portugal", "portuguese",
        "ireland", "irish",
        "scotland", "wales",
        "russia", "russian",
        "ukraine", "ukrainian",
        "europe", "european",
        "middle east",
        "africa", "african",
        "south africa",
        "nigeria", "nigerian",
        "kenya", "kenyan",
        "ghana",
        "egypt", "egyptian",
        "morocco", "moroccan",
        "ethiopia",
        "saudi", "saudi arabia",
        "emirates", "uae", "united arab emirates",
        "israel", "israeli",
        "turkey", "turkish", "t\u00fcrkiye", "turkiye", "t rkiye",
        "oman", "omani",
        "qatar",
        "bahrain",
        "kuwait",
        "jordan",
        "lebanon",
        "iraq",
        "pakistan", "pakistani",
    ]),
    ("Americas", [
        "united states", "u.s.", "usa",
        "canada", "canadian",
        "american", "north america",
        "brazil", "brazilian",
        "mexico", "mexican",
        "argentina", "argentine",
        "colombia", "colombian",
        "chile", "chilean",
        "peru", "peruvian",
        "venezuela",
        "latin america", "latam",
        "americas",
    ]),
    ("Asia Pacific", [
        "india", "indian",
        "china", "chinese",
        "australia", "australian",
        "new zealand",
        "singapore",
        "hong kong",
        "south korea", "korea", "korean",
        "taiwan",
        "indonesia", "indonesian",
        "malaysia", "malaysian",
        "thailand", "thai",
        "vietnam", "vietnamese",
        "philippines", "filipino",
        "bangladesh",
        "sri lanka",
        "nepal",
        "asia", "asia pacific", "apac",
        "japan", "japanese",
    ]),
]

# Topic strings that explicitly mean "no single geography" — leave as Needs review.
_GLOBAL_TOPICS = {"world", "global", "worldwide", "international", "multinational"}


def _infer_geography_from_topics(topics: list[str], body: str) -> str:
    """
    Re-infer a geography bucket from the topics list and body text.

    Strategy (in priority order):
    1. If any topic signals a genuinely global/worldwide story → "Global".
    2. Scan each topic string against the extended keyword map.
    3. Fall back to scanning the body text.
    4. Return "Global" if nothing matches (no region signal = worldwide).
    """
    # 1. Genuinely global stories.
    for topic in topics:
        if topic.lower() in _GLOBAL_TOPICS:
            return "Global"

    # 2. Topics are often single country names: exact or substring match is fine.
    for topic in topics:
        tl = topic.lower()
        for bucket, keywords in _GEO_REMAP:
            if any(kw in tl for kw in keywords):
                return bucket

    # 3. Body text fallback.
    bl = body.lower()
    for bucket, keywords in _GEO_REMAP:
        if any(kw in bl for kw in keywords):
            return bucket

    return "Global"


def _resolve_geography(raw: dict, body: str) -> str:
    """
    Return the best geography value for a story.

    If the crawler already wrote a real bucket (EMEA / Americas / Asia Pacific /
    North America / APAC / Latin America / Japan) keep it.
    Otherwise re-infer from topics + body text.
    """
    stored = (raw.get("geography") or "").strip()
    # Valid values from both old and new crawler runs.
    _VALID = {"emea", "americas", "north america", "asia pacific", "apac",
              "japan", "latin america", "other / global"}
    if stored.lower() in _VALID:
        return stored
    # Stored is "Needs review", empty, or unknown — re-infer.
    topics = raw.get("topics") or []
    return _infer_geography_from_topics(topics, body)


# ── Mapping function ─────────────────────────────────────────────────────────

def map_story(raw: dict, idx: int) -> dict:
    """Convert one crawler record to the dashboard schema."""
    customer_name = raw.get("clientName") or raw.get("title") or f"Story-{idx+1}"
    title         = raw.get("title") or customer_name
    body          = " ".join(filter(None, [
        raw.get("description"),
        raw.get("challenge"),
        raw.get("solution"),
        raw.get("businessOutcomes"),
        raw.get("quantifiedProof"),
        raw.get("customerQuote"),
    ]))

    gtm_motions = _tag_gtm(body)
    products_csv = _extract_products(raw)

    return {
        "story_id":              f"S{idx+1:04d}",
        "customer_name":         customer_name,
        "named_unnamed":         "Named" if customer_name else "Unnamed",
        "client_zero":           _is_client_zero(title, customer_name, raw.get("topics") or []),
        "business_partner":      _is_business_partner(raw.get("topics") or [], raw.get("productCategories") or []),
        "industry":              raw.get("industry") or "Needs review",
        "sub_industry":          None,
        "geography":             _resolve_geography(raw, body),
        "products":              products_csv,
        "gtm_motions":           "; ".join(gtm_motions),
        "open_governed_hybrid":  _open_governed_hybrid(raw.get("productCategories") or [], body),
        "structured_unstructured": _structured_unstructured(body),
        "proof_strength":        _proof_strength(
                                     raw.get("quantifiedProof"),
                                     customer_name,
                                     raw.get("customerQuote"),
                                 ),
        "publication_date":      raw.get("publicationDate"),
        "publication_age_months": _months_since(raw.get("publicationDate")),
        "source_url":            raw.get("canonicalUrl") or raw.get("id"),
        "title":                 title,
        "qa_flag":               None,
        # Extended fields from crawler (kept for modal detail view)
        "description":           raw.get("description"),
        "challenge":             raw.get("challenge"),
        "solution":              raw.get("solution"),
        "business_outcomes":     raw.get("businessOutcomes"),
        "quantified_proof":      raw.get("quantifiedProof"),
        "customer_quote":        raw.get("customerQuote"),
        "product_categories":    raw.get("productCategories") or [],
        "topics":                raw.get("topics") or [],
        "collected_at":          raw.get("collectedAt"),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(SOURCE_FILE):
        print(f"ERROR: Source file not found: {SOURCE_FILE}")
        print("Run the crawler first: node node_modules/ts-node/dist/bin.js scripts/crawl-ibm-case-studies.ts --test")
        sys.exit(1)

    with open(SOURCE_FILE, encoding="utf-8") as f:
        raw_stories = json.load(f)

    print(f"Loaded {len(raw_stories)} crawler stories from {SOURCE_FILE}")

    stories = [map_story(r, i) for i, r in enumerate(raw_stories)]

    # Summary stats
    strength_counts = {}
    for s in stories:
        k = s["proof_strength"]
        strength_counts[k] = strength_counts.get(k, 0) + 1

    gtm_counts = {}
    for s in stories:
        for m in s["gtm_motions"].split("; "):
            gtm_counts[m] = gtm_counts.get(m, 0) + 1

    print(f"\n── Proof strength breakdown ──")
    for k, v in sorted(strength_counts.items()):
        print(f"  {k:12s}: {v}")

    print(f"\n── GTM motion breakdown ──")
    for k, v in sorted(gtm_counts.items()):
        print(f"  {k}: {v}")

    # Write data.json
    os.makedirs(DASH_DIR, exist_ok=True)
    payload = {"stories": stories, "proof_points": []}
    with open(DASH_DATA, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nWrote dashboard data: {DASH_DATA}  ({os.path.getsize(DASH_DATA):,} bytes)")

    # Rebuild the HTML dashboard
    try:
        from src.dashboard import write_dashboard_html
        write_dashboard_html(stories=stories, proof_points=[])
        print(f"Wrote dashboard HTML: {DASH_HTML}")
    except Exception as exc:
        print(f"WARNING: Could not write dashboard HTML: {exc}")
        print("Run python run.py to regenerate the full dashboard.")

    print(f"\n✓ Done. Open the dashboard: {DASH_HTML}")
    print(f"  Stories mapped: {len(stories)}")


if __name__ == "__main__":
    main()
