# core/workflow.py
from __future__ import annotations

from .models import CriteriaTaxonomy, Vendor, VendorSource, VendorStatus

SKILLS: list[dict[str, str]] = [
    {
        "name": "dast-criteria",
        "purpose": "Establish or revise the criteria taxonomy (categories, weights, rubrics)",
        "reads": "-",
        "writes": "data/criteria.yaml",
    },
    {
        "name": "dast-discovery",
        "purpose": "Build or extend the candidate vendor list via live research + seeded must-includes",
        "reads": "data/criteria.yaml",
        "writes": "data/candidates/*.yaml",
    },
    {
        "name": "dast-shortlist",
        "purpose": "Score one candidate against every criterion; once all are scored, decide finalists/rejected",
        "reads": "data/criteria.yaml, data/candidates/*.yaml",
        "writes": "data/candidates/*.yaml (scores, status)",
    },
    {
        "name": "dast-onboard-tool",
        "purpose": "Wire a new DAST tool into the CI workflow, or produce a manual runbook",
        "reads": "data/candidates/*.yaml",
        "writes": ".github/workflows/dast-benchmark.yml, data/candidates/*.yaml (ci_tool_id)",
    },
    {
        "name": "dast-scan",
        "purpose": "Hands-on test a finalist (CI or manual), refine detection scores, mark evaluated",
        "reads": "data/candidates/*.yaml, data/benchmarks.yaml",
        "writes": "data/candidates/*.yaml (hands-on results, scores, status)",
    },
    {
        "name": "dast-report",
        "purpose": "Render the SSoT into reports + write a narrative executive summary",
        "reads": "data/criteria.yaml, data/candidates/*.yaml",
        "writes": "reports/",
    },
]


def _skill(name: str) -> dict[str, str]:
    return next(s for s in SKILLS if s["name"] == name)


def _fully_scored(vendor: Vendor, taxonomy: CriteriaTaxonomy) -> bool:
    return all(vendor.score_for(c.id) is not None for c in taxonomy.criteria)


def phase_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> list[str]:
    lines = ["", "Progress:"]

    if not taxonomy.criteria:
        lines.append("[ ] Criteria      not started")
    elif taxonomy.validate_weights():
        lines.append(f"[!] Criteria      {len(taxonomy.criteria)} criteria, weights invalid")
    else:
        lines.append(f"[x] Criteria      {len(taxonomy.criteria)} criteria, weights sum to 100")

    if not vendors:
        lines.append("[ ] Discovery     no candidates yet")
    else:
        seeded = sum(1 for v in vendors if v.source == VendorSource.SEEDED)
        discovered = len(vendors) - seeded
        lines.append(f"[x] Discovery     {len(vendors)} candidates ({seeded} seeded, {discovered} discovered)")

    if not vendors:
        lines.append("[ ] Shortlist     no candidates yet")
    elif not taxonomy.criteria:
        lines.append("[ ] Shortlist     no criteria to score against yet")
    else:
        scored = [v for v in vendors if _fully_scored(v, taxonomy)]
        undecided = [v for v in vendors if v.status == VendorStatus.CANDIDATE]
        if len(scored) < len(vendors):
            lines.append(f"[ ] Shortlist     {len(scored)}/{len(vendors)} candidates fully scored")
        elif undecided:
            lines.append(f"[ ] Shortlist     scored, {len(undecided)} finalist decision(s) pending")
        else:
            finalists = sum(1 for v in vendors if v.status in (VendorStatus.FINALIST, VendorStatus.EVALUATED))
            rejected = sum(1 for v in vendors if v.status == VendorStatus.REJECTED)
            lines.append(
                f"[x] Shortlist     {len(vendors)}/{len(vendors)} scored, {finalists} finalists, {rejected} rejected"
            )

    finalist_like = [v for v in vendors if v.status in (VendorStatus.FINALIST, VendorStatus.EVALUATED)]
    if not finalist_like:
        lines.append("[ ] Hands-on scan no finalists yet")
    else:
        evaluated = sum(1 for v in finalist_like if v.status == VendorStatus.EVALUATED)
        marker = "x" if evaluated == len(finalist_like) else " "
        lines.append(f"[{marker}] Hands-on scan {evaluated}/{len(finalist_like)} finalists evaluated")

    lines.append("")
    lines.append(f"Next: {_next_action(taxonomy, vendors)}")
    return lines


def _next_action(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> str:
    if not taxonomy.criteria or taxonomy.validate_weights():
        return f"run dast-criteria -- {_skill('dast-criteria')['purpose']}"
    if not vendors:
        return f"run dast-discovery -- {_skill('dast-discovery')['purpose']}"
    if any(not _fully_scored(v, taxonomy) for v in vendors):
        return f"run dast-shortlist -- {_skill('dast-shortlist')['purpose']}"
    if any(v.status == VendorStatus.CANDIDATE for v in vendors):
        return f"run dast-shortlist -- {_skill('dast-shortlist')['purpose']}"
    finalist_like = [v for v in vendors if v.status in (VendorStatus.FINALIST, VendorStatus.EVALUATED)]
    if any(v.status == VendorStatus.FINALIST for v in finalist_like):
        return f"run dast-scan (or dast-onboard-tool if not CI-wired) -- {_skill('dast-scan')['purpose']}"
    return f"everything's current -- run dast-report -- {_skill('dast-report')['purpose']}"
