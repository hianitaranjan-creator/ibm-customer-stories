"""
parser.py
---------
Reads cached HTML for each IBM case study and extracts structured data.

What it extracts from each page:
  - Customer name (or "Unnamed" if not found)
  - Industry, sub-industry
  - Geography / country
  - IBM products mentioned
  - Publication date
  - Story body text
  - Individual proof points: metrics, quotes, qualitative outcomes
  - Source URL

When a field cannot be identified confidently it is set to "Needs review"
and an entry is added to the QA exceptions list.
"""

import re
import datetime
from bs4 import BeautifulSoup

from src import logger
from src.config import IBM_BASE

# ─────────────────────────────────────────────────────────────────────────────
# QA exceptions — collected here, written to Excel Sheet 6 later.
# ─────────────────────────────────────────────────────────────────────────────
qa_exceptions: list[dict] = []

_story_counter = 0   # Used to generate sequential Story IDs (S001, S002 …)
_proof_counter  = 0  # Used to generate sequential Proof IDs (P001, P002 …)


def _next_story_id() -> str:
    global _story_counter
    _story_counter += 1
    return f"S{_story_counter:04d}"


def _next_proof_id() -> str:
    global _proof_counter
    _proof_counter += 1
    return f"P{_proof_counter:04d}"


def _add_qa(story_id: str, field: str, raw: str, suggested: str) -> None:
    qa_exceptions.append({
        "story_id": story_id,
        "field": field,
        "raw_text_found": raw[:500] if raw else "",
        "suggested_value": suggested,
        "reviewer_action": "",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Geography inference
# ─────────────────────────────────────────────────────────────────────────────

# Map country/region name fragments → geography bucket.
_GEO_MAP = {
    "North America": [
        "united states", "u.s.", "us ", "usa", "canada", "canadian",
        "american", "north america",
    ],
    "EMEA": [
        "uk", "united kingdom", "britain", "germany", "german", "france",
        "french", "spain", "spanish", "italy", "italian", "netherlands",
        "dutch", "belgium", "sweden", "sweden", "norway", "denmark",
        "finland", "switzerland", "austria", "poland", "czech", "hungary",
        "europe", "european", "middle east", "africa", "african",
        "south africa", "nigeria", "kenya", "saudi", "emirates", "uae",
        "israel", "turkey", "türkiye", "ireland", "scotland", "wales",
        "portugal", "greece", "russia",
    ],
    "APAC": [
        "india", "indian", "china", "chinese", "australia", "australian",
        "new zealand", "singapore", "hong kong", "south korea", "korea",
        "taiwan", "indonesia", "malaysia", "thailand", "vietnam",
        "philippines", "philippines", "bangladesh", "pakistan", "asia",
        "asia pacific", "apac",
    ],
    "Japan": ["japan", "japanese"],
    "Latin America": [
        "brazil", "brazilian", "mexico", "mexican", "argentina", "argentine",
        "colombia", "colombian", "chile", "chilean", "peru", "venezuela",
        "latin america", "latam",
    ],
}


def _infer_geography(text: str) -> str:
    """
    Scan the story text for geography clues.
    Returns the best-matching bucket, or 'Other / Global'.
    """
    lower = text.lower()
    for bucket, keywords in _GEO_MAP.items():
        for kw in keywords:
            if kw in lower:
                return bucket
    return "Other / Global"


# ─────────────────────────────────────────────────────────────────────────────
# IBM product detection
# ─────────────────────────────────────────────────────────────────────────────

IBM_PRODUCT_PATTERNS = [
    # Data & AI
    "Watson", "watsonx", "Watson Studio", "Watson Query", "Watson Knowledge Catalog",
    "OpenScale", "OpenPages",
    # Data Platform
    "Cloud Pak for Data", "Db2", "Informix", "Netezza",
    "DataStage", "Data Virtualization", "Match360",
    "IBM Knowledge Catalog",
    # Integration & modernisation
    "MQ", "App Connect", "API Connect", "DataPower",
    "Sterling", "Aspera",
    # Infrastructure
    "IBM Z", "Z Systems", "Power", "FlashSystem", "Spectrum",
    # Cloud
    "IBM Cloud", "Red Hat", "OpenShift",
    # AI
    "Granite", "IBM AI", "AI Factsheets",
    # Generic
    "IBM Consulting",
]

def _detect_products(text: str) -> list[str]:
    """Return a deduplicated list of IBM products mentioned in the text."""
    found = []
    for product in IBM_PRODUCT_PATTERNS:
        if product.lower() in text.lower() and product not in found:
            found.append(product)
    return found if found else ["Needs review"]


# ─────────────────────────────────────────────────────────────────────────────
# Industry detection
# ─────────────────────────────────────────────────────────────────────────────

_INDUSTRY_MAP = {
    "Financial Services": [
        "bank", "banking", "financial", "insurance", "capital markets",
        "investment", "fintech", "credit", "loan", "mortgage", "payment",
        "wealth management",
    ],
    "Healthcare & Life Sciences": [
        "health", "hospital", "clinic", "pharmaceutical", "pharma",
        "biotech", "life science", "medical", "patient", "drug", "genomic",
        "laboratory", "lab ",
    ],
    "Telecommunications": [
        "telecom", "telco", "mobile network", "5g", "broadband",
        "carrier", "operator", "communications provider",
    ],
    "Retail & Consumer Goods": [
        "retail", "retailer", "consumer goods", "e-commerce", "ecommerce",
        "supermarket", "grocery", "fashion", "apparel", "cpg",
    ],
    "Manufacturing": [
        "manufactur", "automotive", "automobile", "car maker", "industrial",
        "supply chain", "factory", "plant", "aerospace", "chemical",
        "steel", "semiconductor",
    ],
    "Energy & Utilities": [
        "energy", "utility", "utilities", "oil", "gas", "electric",
        "power grid", "renewable", "solar", "wind", "nuclear",
    ],
    "Government & Public Sector": [
        "government", "federal", "municipal", "public sector", "ministry",
        "agency", "department of", "city of", "state of",
    ],
    "Transportation & Logistics": [
        "transport", "logistics", "shipping", "freight", "airline",
        "airport", "railway", "rail ", "port ", "fleet",
    ],
    "Education": [
        "university", "college", "school", "education", "academic",
        "research institution",
    ],
    "Media & Entertainment": [
        "media", "entertainment", "broadcast", "publishing", "gaming",
        "streaming platform",
    ],
}


def _infer_industry(text: str) -> tuple[str, str]:
    """
    Return (industry, sub_industry) best matching the story text.
    Falls back to ('Other', 'Needs review') if nothing matches.
    """
    lower = text.lower()
    best_industry = "Other"
    best_hits = 0
    for industry, keywords in _INDUSTRY_MAP.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits > best_hits:
            best_hits = hits
            best_industry = industry
    sub = "Needs review"
    return best_industry, sub


# ─────────────────────────────────────────────────────────────────────────────
# Proof-point extraction
# ─────────────────────────────────────────────────────────────────────────────

# Patterns that suggest a quantified result.
_QUANTITY_PATTERN = re.compile(
    r"""
    (
        \d[\d,\.]*          # number with optional commas/decimals
        \s*                 # optional space
        (?:
            [%x×]           # percent or multiplier
            | times         # "3 times faster"
            | percent       # spelled out
            | \$            # currency before the number (we'll also catch it below)
            | USD | EUR | GBP | £ | €
            | million | billion | thousand
            | hours? | days? | weeks? | months? | years?
            | hours? | minutes? | seconds?
            | TB | GB | MB | KB
        )
    )
    |
    (
        [\$£€]              # currency symbol before number
        \s*\d[\d,\.]*
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Phrases that flag a result as projected/estimated rather than realized.
_PROJECTED_PHRASES = re.compile(
    r"\b(project|expect|estimat|anticipat|potential|possibl|could|might|"
    r"forecast|target|goal|aim|plan to|intended to|up to|as much as|"
    r"hope|aspir)\b",
    re.IGNORECASE,
)

# Partner-reported / unnamed signals.
_PARTNER_PHRASES = re.compile(
    r"\b(business partner|partner-reported|our partner|solution provider|"
    r"reseller|distributor|partner solution)\b",
    re.IGNORECASE,
)

# Metric / outcome sentences typically contain these verbs.
_OUTCOME_VERBS = re.compile(
    r"\b(reduc|increas|improv|cut|sav|achiev|deliver|boost|accelerat|"
    r"eliminat|lower|faster|gain|generat|grow|shrink|optimiz|consolidat|"
    r"deploy|migrat|process|handl|complet|resolv|enabl|transform)\b",
    re.IGNORECASE,
)


def _classify_result_type(sentence: str) -> str:
    """Return Realized | Projected | Estimated | Aspirational."""
    if _PROJECTED_PHRASES.search(sentence):
        if re.search(r"\bestimated?\b", sentence, re.IGNORECASE):
            return "Estimated"
        return "Projected"
    if re.search(r"\b(aspir|vision|strat|long-term)\b", sentence, re.IGNORECASE):
        return "Aspirational"
    return "Realized"


def _extract_quantity(sentence: str) -> str:
    """Pull the first measurable figure from a sentence, or '' if none."""
    match = _QUANTITY_PATTERN.search(sentence)
    return match.group(0).strip() if match else ""


def _split_into_sentences(text: str) -> list[str]:
    """Very simple sentence splitter."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def _extract_proof_points(
    story_id: str,
    customer_name: str,
    named_flag: str,
    url: str,
    body_text: str,
    quotes: list[str],
) -> list[dict]:
    """
    Produce exactly ONE proof point per story.

    The story itself is the proof point — individual sentences and verbatim
    quotes are NOT split into separate rows.  Instead we pick the single
    best representative piece of evidence:
      1. Best quantified metric sentence (strongest evidence).
      2. First verbatim quote (if no metric found).
      3. First outcome-verb sentence (fallback).
      4. Product-adoption placeholder (last resort).
    """
    # --- Find the best quantified sentence in the body ---
    best_metric_sentence = ""
    best_quantity = ""
    for sentence in _split_into_sentences(body_text):
        if not _OUTCOME_VERBS.search(sentence):
            continue
        qty = _extract_quantity(sentence)
        if qty and not best_metric_sentence:
            best_metric_sentence = sentence
            best_quantity = qty

    # --- Pick the representative proof text ---
    if best_metric_sentence:
        proof_text = best_metric_sentence
        proof_type = "Metric"
        result_type = _classify_result_type(best_metric_sentence)
        quantified_result = best_quantity
    elif quotes:
        proof_text = quotes[0].strip()
        proof_type = "Customer quote"
        result_type = _classify_result_type(proof_text)
        quantified_result = _extract_quantity(proof_text)
    else:
        fallback = next(
            (s for s in _split_into_sentences(body_text) if _OUTCOME_VERBS.search(s)),
            None,
        )
        if fallback:
            proof_text = fallback
            proof_type = "Qualitative outcome"
            result_type = _classify_result_type(fallback)
            quantified_result = _extract_quantity(fallback)
        else:
            proof_text = "No specific outcome or metric found on page."
            proof_type = "Product adoption"
            result_type = "Aspirational"
            quantified_result = ""

    pid = _next_proof_id()
    return [{
        "proof_id": pid,
        "story_id": story_id,
        "customer_name": customer_name,
        "named_unnamed": named_flag,
        "proof_type": proof_type,
        "proof_text": proof_text,
        "result_type": result_type,
        "quantified_result": quantified_result,
        "ibm_solution_credited": "Needs review",
        "gtm_motions": [],        # filled by classifier
        "proof_strength": "",     # filled by classifier
        "source_url": url,
        "qa_flag": "" if proof_type != "Product adoption" else "Needs review",
    }]


# ─────────────────────────────────────────────────────────────────────────────
# Main parse function
# ─────────────────────────────────────────────────────────────────────────────

def parse_story(url: str, html: str) -> dict:
    """
    Parse one story page's HTML and return a structured dict with:
      - story metadata (customer, industry, geography, products, …)
      - a list of proof points
    """
    soup = BeautifulSoup(html, "html.parser")
    story_id = _next_story_id()

    # ── Page title ─────────────────────────────────────────────────────────
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)
    if not title:
        title = "Needs review"

    # ── Customer name ──────────────────────────────────────────────────────
    # IBM case-study pages typically include the customer name in structured
    # metadata, in an <h1>, or in a "Customer" label near the top.
    customer_name = "Unnamed"
    named_flag = "Unnamed"

    # Try JSON-LD structured data first.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string or "")
            # Accept both single object and list.
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    for key in ("name", "author", "brand", "provider"):
                        val = item.get(key)
                        if isinstance(val, str) and len(val) > 2:
                            customer_name = val
                            named_flag = "Named"
                            break
                        if isinstance(val, dict):
                            n = val.get("name", "")
                            if n and len(n) > 2:
                                customer_name = n
                                named_flag = "Named"
                                break
                if named_flag == "Named":
                    break
        except Exception:
            pass

    # Try common HTML patterns if JSON-LD didn't work.
    if customer_name == "Unnamed":
        # Look for elements with "customer" in their class or data attributes.
        for tag in soup.find_all(
            True,
            {"class": re.compile(r"(customer|client|company|brand)", re.IGNORECASE)},
        ):
            text = tag.get_text(strip=True)
            if 2 < len(text) < 80:
                customer_name = text
                named_flag = "Named"
                break

    # Try <h1> as a last resort.
    if customer_name == "Unnamed":
        h1 = soup.find("h1")
        if h1:
            h1_text = h1.get_text(strip=True)
            # Only use h1 if it looks like a company name (short, not a question).
            if 2 < len(h1_text) < 80 and "?" not in h1_text:
                customer_name = h1_text
                named_flag = "Named"

    if customer_name == "Unnamed":
        _add_qa(story_id, "customer_name", title, "Needs review")

    # ── Client Zero & Business Partner flags ──────────────────────────────
    full_text = soup.get_text(separator=" ")
    client_zero_flag = "Yes" if re.search(
        r"\b(IBM client zero|ibm is the customer|ibm uses ibm)\b",
        full_text, re.IGNORECASE
    ) else "No"
    biz_partner_flag = "Yes" if _PARTNER_PHRASES.search(full_text) else "No"

    # ── Industry ──────────────────────────────────────────────────────────
    industry, sub_industry = _infer_industry(full_text)

    # ── Geography ─────────────────────────────────────────────────────────
    geography = _infer_geography(full_text)
    if geography == "Other / Global":
        _add_qa(story_id, "geography", full_text[:200], "Other / Global — manual check recommended")

    # ── IBM products ──────────────────────────────────────────────────────
    products = _detect_products(full_text)

    # ── Publication date ──────────────────────────────────────────────────
    pub_date = "Needs review"
    pub_age_months: int | str = "Needs review"

    # Try <meta> tags first.
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        if prop.lower() in ("article:published_time", "date", "dc.date", "pubdate"):
            content = meta.get("content", "")
            if content:
                pub_date = content[:10]  # YYYY-MM-DD
                break
    # Try <time> tag.
    if pub_date == "Needs review":
        time_tag = soup.find("time")
        if time_tag:
            dt = time_tag.get("datetime", "") or time_tag.get_text(strip=True)
            if dt:
                pub_date = dt[:10]

    if pub_date != "Needs review":
        try:
            parsed = datetime.datetime.strptime(pub_date[:10], "%Y-%m-%d")
            delta = datetime.datetime.now() - parsed
            pub_age_months = int(delta.days / 30)
        except ValueError:
            pub_age_months = "Needs review"
    else:
        _add_qa(story_id, "publication_date", "", "Needs review")

    # ── Story body text and quotes ────────────────────────────────────────
    # Remove nav, header, footer, script, style to get clean body text.
    for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
        tag.decompose()

    body_text = soup.get_text(separator=" ", strip=True)
    # Collapse runs of whitespace.
    body_text = re.sub(r'\s+', ' ', body_text)

    # Extract blockquotes and pull-quotes.
    quotes = []
    for q_tag in soup.find_all(["blockquote", "q"]):
        q_text = q_tag.get_text(strip=True)
        if len(q_text) > 20:
            quotes.append(q_text)
    # Also look for elements with "quote" in the class name.
    for q_tag in soup.find_all(True, {"class": re.compile(r"quote", re.IGNORECASE)}):
        q_text = q_tag.get_text(strip=True)
        if len(q_text) > 20 and q_text not in quotes:
            quotes.append(q_text)

    # ── Proof points ──────────────────────────────────────────────────────
    proof_points = _extract_proof_points(
        story_id, customer_name, named_flag, url, body_text, quotes
    )
    logger.increment("proof_points_extracted", len(proof_points))

    # ── Assemble story dict ───────────────────────────────────────────────
    story = {
        "story_id": story_id,
        "customer_name": customer_name,
        "named_unnamed": named_flag,
        "client_zero": client_zero_flag,
        "business_partner": biz_partner_flag,
        "industry": industry,
        "sub_industry": sub_industry,
        "geography": geography,
        "products": ", ".join(products),
        "gtm_motions": "",            # filled by classifier
        "open_governed_hybrid": "",   # filled by classifier
        "structured_unstructured": "", # filled by classifier
        "proof_strength": "",         # filled by classifier
        "publication_date": pub_date,
        "publication_age_months": pub_age_months,
        "source_url": url,
        "title": title,
        "qa_flag": "",
        "body_text": body_text,       # kept for classifier, not written to Excel
        "proof_points": proof_points,
    }

    logger.info(
        f"Parsed {story_id}: {customer_name} | {industry} | {geography} "
        f"| {len(proof_points)} proof point(s)"
    )
    return story
