"""
taxonomy.py
-----------
IBM Software Product Taxonomy normalization layer.

Loads src/config/product-taxonomy.json and provides:

  normalize_products(text, original_products_csv) -> dict

The returned dict contains ADDITIVE fields only — it never overwrites
the original `products` CSV or any other existing story field.

Additive fields added to each story:
  product_tags          – list of canonical product names detected
  product_families      – list of unique product family labels
  product_portfolios    – list of unique portfolio labels
  product_taxonomy      – list of dicts, one per detected product, with
                          full taxonomy metadata (canonical, family,
                          portfolio, aliases, legacy terms, confidence)
  taxonomy_search_terms – flat list of all searchable terms (canonical +
                          aliases + legacy term names) for search enrichment
"""

import json
import os
import re
from src import logger

_TAXONOMY_PATH = os.path.join(
    os.path.dirname(__file__), "config", "product-taxonomy.json"
)

# ── Load and flatten taxonomy at import time ──────────────────────────────────

def _load_taxonomy() -> list[dict]:
    """
    Load the taxonomy JSON and return a flat list of product entries,
    each augmented with its portfolio and family labels.
    """
    try:
        with open(_TAXONOMY_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        logger.warn(f"Taxonomy file not found: {_TAXONOMY_PATH} — skipping enrichment")
        return []
    except json.JSONDecodeError as e:
        logger.warn(f"Taxonomy JSON parse error: {e} — skipping enrichment")
        return []

    flat: list[dict] = []
    for portfolio in raw.get("portfolios", []):
        portfolio_label = portfolio.get("label", "")
        for family in portfolio.get("families", []):
            family_label = family.get("label", "")
            for product in family.get("products", []):
                entry = dict(product)
                entry["portfolio"] = portfolio_label
                entry["family"] = family_label
                # Compile detection patterns to regex objects (case-insensitive).
                entry["_patterns"] = []
                for pat in product.get("detection_patterns", []):
                    try:
                        entry["_patterns"].append(re.compile(pat, re.IGNORECASE))
                    except re.error:
                        # Treat malformed patterns as plain substring patterns.
                        entry["_patterns"].append(
                            re.compile(re.escape(pat), re.IGNORECASE)
                        )
                flat.append(entry)
    return flat


_FLAT_PRODUCTS: list[dict] = _load_taxonomy()


# ── Search-term expansion ─────────────────────────────────────────────────────

def _all_search_terms(entry: dict) -> list[str]:
    """
    Return all terms a user might search for to find this product:
    canonical name + aliases + legacy term names.
    """
    terms = [entry["canonical"]]
    terms.extend(entry.get("aliases", []))
    for leg in entry.get("legacy", []):
        if isinstance(leg, dict) and leg.get("term"):
            terms.append(leg["term"])
    return [t for t in terms if t]


# ── Main normalization function ───────────────────────────────────────────────

def normalize_products(text: str, original_products_csv: str) -> dict:
    """
    Scan `text` (body text, titles, topics joined, etc.) and
    `original_products_csv` (the existing `products` field) against every
    product's detection_patterns.

    Returns a dict of ADDITIVE fields — never modifies original data.

    Fields returned:
        product_tags          list[str]   canonical product names matched
        product_families      list[str]   unique family labels
        product_portfolios    list[str]   unique portfolio labels
        product_taxonomy      list[dict]  full metadata per matched product
        taxonomy_search_terms list[str]   all searchable aliases for matched products
    """
    if not _FLAT_PRODUCTS:
        return {
            "product_tags": [],
            "product_families": [],
            "product_portfolios": [],
            "product_taxonomy": [],
            "taxonomy_search_terms": [],
        }

    # Combine all text sources for matching.
    combined = (text or "") + " " + (original_products_csv or "")

    matched_ids: set[str] = set()
    product_tags: list[str] = []
    product_families: list[str] = []
    product_portfolios: list[str] = []
    product_taxonomy: list[dict] = []
    search_terms: list[str] = []

    for entry in _FLAT_PRODUCTS:
        pid = entry.get("id", "")
        if pid in matched_ids:
            continue
        # Test every compiled pattern against the combined text.
        if any(p.search(combined) for p in entry.get("_patterns", [])):
            matched_ids.add(pid)
            canonical = entry["canonical"]
            family = entry["family"]
            portfolio = entry["portfolio"]

            if canonical not in product_tags:
                product_tags.append(canonical)
            if family and family not in product_families:
                product_families.append(family)
            if portfolio and portfolio not in product_portfolios:
                product_portfolios.append(portfolio)

            # Build slim taxonomy record for the story (no compiled regexes).
            tax_record = {
                "id": pid,
                "canonical": canonical,
                "family": family,
                "portfolio": portfolio,
                "aliases": entry.get("aliases", []),
                "legacy": entry.get("legacy", []),
                "related_to": entry.get("related_to", []),
                "confidence": entry.get("confidence", "needs_review"),
                "note": entry.get("note", ""),
            }
            product_taxonomy.append(tax_record)
            search_terms.extend(_all_search_terms(entry))

    # Deduplicate search terms (preserve order, case-insensitive dedup).
    seen: set[str] = set()
    unique_search_terms: list[str] = []
    for t in search_terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_search_terms.append(t)

    return {
        "product_tags": product_tags,
        "product_families": product_families,
        "product_portfolios": product_portfolios,
        "product_taxonomy": product_taxonomy,
        "taxonomy_search_terms": unique_search_terms,
    }
