"""
classifier.py
-------------
Takes the parsed story data produced by parser.py and:
  1. Tags each proof point with one or more GTM motions.
  2. Assigns a proof strength (Strong / Medium / Weak / Restricted).
  3. Classifies each story as Open / Governed / Hybrid.
  4. Classifies each story as Structured / Unstructured data.
  5. Rolls up the highest proof strength to the story level.
"""

import re
from src.config import GTM_KEYWORDS, GTM_MOTIONS
from src import logger


# ─────────────────────────────────────────────────────────────────────────────
# GTM motion tagging
# ─────────────────────────────────────────────────────────────────────────────

def _tag_gtm_motions(text: str) -> list[str]:
    """
    Return a list of GTM motions whose keywords appear in 'text'.
    Returns ['Needs review'] if none match.
    """
    lower = text.lower()
    matched = []
    for motion, keywords in GTM_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            matched.append(motion)
    return matched if matched else ["Needs review"]


# ─────────────────────────────────────────────────────────────────────────────
# Proof strength
# ─────────────────────────────────────────────────────────────────────────────

# Phrases that always push to Restricted.
_RESTRICTED_SIGNALS = re.compile(
    r"\b(project|expect|estimat|anticipat|potential|possibl|could save|"
    r"might|forecast|target|up to|as much as|partner-reported|"
    r"unnamed|undisclosed|confidential client)\b",
    re.IGNORECASE,
)


def assign_proof_strength(proof: dict, story: dict) -> str:
    """
    Apply the four-tier proof-strength rules from the plan.

    Strong:     Named customer + quantified realized result + IBM attribution.
    Medium:     Named customer + qualitative outcome OR direct quote.
    Weak:       Product adoption or aspirational benefit only.
    Restricted: Projected / estimated / partner / unnamed result.
    """
    text     = proof.get("proof_text", "")
    ptype    = proof.get("proof_type", "")
    result   = proof.get("result_type", "Realized")
    quantity = proof.get("quantified_result", "")
    customer = story.get("customer_name", "Unnamed")
    named    = story.get("named_unnamed", "Unnamed")

    # Restricted first — trumps everything.
    if result in ("Projected", "Estimated") or _RESTRICTED_SIGNALS.search(text):
        return "Restricted"
    if named == "Unnamed" and result != "Realized":
        return "Restricted"

    # Strong: named + quantified realized result.
    if named == "Named" and quantity and result == "Realized":
        return "Strong"

    # Medium: named + qualitative outcome or quote.
    if named == "Named" and ptype in ("Qualitative outcome", "Customer quote"):
        return "Medium"

    # Weak: everything else (product adoption, aspirational).
    return "Weak"


# ─────────────────────────────────────────────────────────────────────────────
# Open / Governed / Hybrid classification
# ─────────────────────────────────────────────────────────────────────────────

_OPEN_KEYWORDS = [
    "open source", "open data", "hadoop", "spark", "kafka", "parquet",
    "delta lake", "iceberg", "hudi", "open lakehouse",
]
_GOVERNED_KEYWORDS = [
    "governance", "governed", "compliance", "lineage", "data quality",
    "data catalog", "master data", "metadata", "data steward",
    "regulatory", "policy", "ibm knowledge catalog", "wkc",
]


def _classify_open_governed_hybrid(text: str) -> str:
    lower = text.lower()
    has_open      = any(kw in lower for kw in _OPEN_KEYWORDS)
    has_governed  = any(kw in lower for kw in _GOVERNED_KEYWORDS)
    if has_open and has_governed:
        return "Hybrid"
    if has_governed:
        return "Governed"
    if has_open:
        return "Open"
    return "Needs review"


# ─────────────────────────────────────────────────────────────────────────────
# Structured / Unstructured classification
# ─────────────────────────────────────────────────────────────────────────────

_UNSTRUCTURED_KEYWORDS = [
    "unstructured", "text analytics", "nlp", "natural language",
    "document", "pdf", "image", "video", "audio", "email",
    "social media", "sentiment", "speech", "ocr",
]
_STRUCTURED_KEYWORDS = [
    "structured", "relational", "sql", "database", "table",
    "row", "column", "data warehouse", "etl", "olap",
    "transactional", "erp", "crm",
]


def _classify_structured_unstructured(text: str) -> str:
    lower = text.lower()
    has_unstructured = any(kw in lower for kw in _UNSTRUCTURED_KEYWORDS)
    has_structured   = any(kw in lower for kw in _STRUCTURED_KEYWORDS)
    if has_unstructured and has_structured:
        return "Both"
    if has_unstructured:
        return "Unstructured"
    if has_structured:
        return "Structured"
    return "Needs review"


# ─────────────────────────────────────────────────────────────────────────────
# Proof strength roll-up for a whole story
# ─────────────────────────────────────────────────────────────────────────────

_STRENGTH_RANK = {"Strong": 4, "Medium": 3, "Weak": 2, "Restricted": 1, "": 0}


def _highest_strength(strengths: list[str]) -> str:
    best = ""
    for s in strengths:
        if _STRENGTH_RANK.get(s, 0) > _STRENGTH_RANK.get(best, 0):
            best = s
    return best or "Weak"


# ─────────────────────────────────────────────────────────────────────────────
# Main classify function
# ─────────────────────────────────────────────────────────────────────────────

def classify_story(story: dict) -> dict:
    """
    Add classification fields to a story dict (mutates and returns it).

    There is exactly ONE proof point per story (the story itself).
    Its strength is assigned here and rolled up to the story level.
    """
    body_text = story.get("body_text", "")

    # Story-level classifications.
    story["open_governed_hybrid"]    = _classify_open_governed_hybrid(body_text)
    story["structured_unstructured"] = _classify_structured_unstructured(body_text)

    # GTM motions — derived from the single proof point + body context.
    story_gtm: set[str] = set()
    proofs = story.get("proof_points", [])

    for proof in proofs:
        proof_text = proof.get("proof_text", "")
        motions = _tag_gtm_motions(proof_text + " " + body_text[:2000])
        proof["gtm_motions"] = motions
        story_gtm.update(m for m in motions if m != "Needs review")

        strength = assign_proof_strength(proof, story)
        proof["proof_strength"] = strength

    # Story proof_strength = the single proof point's strength (or Weak if none).
    story["proof_strength"] = proofs[0]["proof_strength"] if proofs else "Weak"
    valid_gtm = [m for m in story_gtm if m in GTM_MOTIONS]
    story["gtm_motions"] = "; ".join(valid_gtm) if valid_gtm else "Needs review"

    logger.info(
        f"Classified {story['story_id']}: strength={story['proof_strength']} "
        f"| OGH={story['open_governed_hybrid']} "
        f"| GTM={story['gtm_motions']}"
    )
    return story
