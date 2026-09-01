"""
gap_analyzer.py
---------------
Compares the classified stories against the four GTM motions and six
geographies to find where strong customer proof is missing.

Produces:
  - A coverage matrix (dict of dicts) used for Excel Sheet 4.
  - A prioritised evidence pipeline list used for Excel Sheet 5.
"""

from src.config import GTM_MOTIONS, GEOGRAPHIES, PROOF_STRENGTHS
from src import logger


# How important is each GTM motion? Used to set gap priority.
_GTM_PRIORITY = {
    "Real-time data and context":          1,
    "Governed data for AI":                1,
    "Data integration and modernization":  2,
    "Cost and workload optimization":      2,
}


def build_coverage_matrix(stories: list[dict]) -> dict:
    """
    Returns a nested dict:
      matrix[gtm_motion][geography][strength] = count_of_stories

    Example:
      matrix["Governed data for AI"]["EMEA"]["Strong"] = 3
    """
    # Initialise everything to zero.
    matrix: dict = {}
    for motion in GTM_MOTIONS:
        matrix[motion] = {}
        for geo in GEOGRAPHIES:
            matrix[motion][geo] = {s: 0 for s in PROOF_STRENGTHS}

    for story in stories:
        geo      = story.get("geography", "Other / Global")
        if geo not in GEOGRAPHIES:
            geo = "Other / Global"
        strength = story.get("proof_strength", "Weak")
        if strength not in PROOF_STRENGTHS:
            strength = "Weak"
        motions_str = story.get("gtm_motions", "")
        if not motions_str or motions_str == "Needs review":
            continue
        for motion in motions_str.split("; "):
            motion = motion.strip()
            if motion in GTM_MOTIONS:
                matrix[motion][geo][strength] += 1

    return matrix


def build_evidence_pipeline(
    matrix: dict,
    stories: list[dict],
) -> list[dict]:
    """
    Identify gaps (GTM motion × Geography combinations with zero Strong proof)
    and return a prioritised list for the Evidence Pipeline sheet.
    """
    gaps = []
    gap_id = 0

    for motion in GTM_MOTIONS:
        for geo in GEOGRAPHIES:
            strong_count = matrix[motion][geo].get("Strong", 0)
            medium_count = matrix[motion][geo].get("Medium", 0)
            weak_count   = matrix[motion][geo].get("Weak", 0)

            if strong_count >= 2:
                continue  # Good coverage — skip.

            gap_id += 1
            # Priority: High if no strong proof and high-priority motion.
            if strong_count == 0 and _GTM_PRIORITY.get(motion, 2) == 1:
                priority = "High"
            elif strong_count == 0:
                priority = "Medium"
            else:
                priority = "Low"  # Has 1 strong — good but room to grow.

            # Find Medium/Weak stories that could be upgraded.
            upgradeable = []
            for s in stories:
                s_geo = s.get("geography", "Other / Global")
                s_motions = s.get("gtm_motions", "")
                s_strength = s.get("proof_strength", "Weak")
                if s_geo == geo and motion in s_motions and s_strength in ("Medium", "Weak"):
                    upgradeable.append(s.get("customer_name", "Unnamed"))

            upgradeable_str = ", ".join(upgradeable[:3])
            if len(upgradeable) > 3:
                upgradeable_str += f" (+{len(upgradeable)-3} more)"

            gaps.append({
                "gap_id": f"G{gap_id:03d}",
                "gap_description": (
                    f"No Strong proof for '{motion}' in {geo}"
                    if strong_count == 0
                    else f"Only {strong_count} Strong proof(s) for '{motion}' in {geo}"
                ),
                "priority": priority,
                "gtm_motion": motion,
                "geography": geo,
                "industry": "All",
                "strong_count": strong_count,
                "medium_count": medium_count,
                "weak_count": weak_count,
                "suggested_story_type": (
                    "New named customer story with quantified business outcome"
                    if strong_count == 0
                    else "Upgrade existing story to include quantified metric"
                ),
                "upgradeable_stories": upgradeable_str or "None identified",
                "notes": "",
            })

    # Sort: High → Medium → Low, then alphabetically within each tier.
    order = {"High": 0, "Medium": 1, "Low": 2}
    gaps.sort(key=lambda g: (order.get(g["priority"], 3), g["gtm_motion"]))

    logger.info(f"Evidence pipeline: {len(gaps)} gaps identified.")
    return gaps


def build_executive_summary(
    stories: list[dict],
    proof_points: list[dict],
    matrix: dict,
    pipeline: list[dict],
) -> dict:
    """
    Produce the summary numbers that go on Excel Sheet 1.
    """
    import datetime, collections

    total_stories  = len(stories)
    named_count    = sum(1 for s in stories if s.get("named_unnamed") == "Named")
    unnamed_count  = total_stories - named_count

    strength_counts = collections.Counter(
        p.get("proof_strength", "Weak") for p in proof_points
    )

    # Coverage score per GTM motion = % geographies with >= 1 Strong proof.
    gtm_coverage: dict[str, str] = {}
    for motion in GTM_MOTIONS:
        covered = sum(
            1 for geo in GEOGRAPHIES
            if matrix[motion][geo].get("Strong", 0) > 0
        )
        pct = int(100 * covered / len(GEOGRAPHIES))
        gtm_coverage[motion] = f"{pct}%  ({covered}/{len(GEOGRAPHIES)} geos)"

    # Top 5 industries.
    industry_counts = collections.Counter(s.get("industry", "Other") for s in stories)
    top5 = industry_counts.most_common(5)

    high_gaps  = sum(1 for g in pipeline if g["priority"] == "High")
    total_gaps = len(pipeline)

    return {
        "run_timestamp":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_stories":    total_stories,
        "named_stories":    named_count,
        "unnamed_stories":  unnamed_count,
        "total_proofs":     len(proof_points),
        "strong_proofs":    strength_counts.get("Strong", 0),
        "medium_proofs":    strength_counts.get("Medium", 0),
        "weak_proofs":      strength_counts.get("Weak", 0),
        "restricted_proofs":strength_counts.get("Restricted", 0),
        "gtm_coverage":     gtm_coverage,
        "top5_industries":  top5,
        "total_gaps":       total_gaps,
        "high_priority_gaps": high_gaps,
    }
