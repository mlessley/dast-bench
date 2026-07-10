from __future__ import annotations

from pathlib import Path

from ..models import CriteriaTaxonomy, Vendor


def _md_cell(value: str) -> str:
    """Escape special characters in Markdown table cells."""
    return value.replace("|", "\\|").replace("\n", " ")


def weighted_score(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> float:
    total = 0.0
    for criterion in taxonomy.criteria:
        entry = vendor.score_for(criterion.id)
        if entry:
            total += entry.score * (criterion.weight / 100.0)
    return total


def render_scorecard(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> str:
    lines = [f"# {_md_cell(vendor.name)} Scorecard", "", f"Status: {vendor.status.value}", ""]
    lines.append("| Criterion | Category | Score | Evidence | Confidence |")
    lines.append("|---|---|---|---|---|")
    for criterion in taxonomy.criteria:
        entry = vendor.score_for(criterion.id)
        if entry:
            lines.append(
                f"| {_md_cell(criterion.name)} | {_md_cell(criterion.category)} | {entry.score:g} | {_md_cell(entry.evidence)} | "
                f"{entry.confidence.value} |"
            )
        else:
            lines.append(f"| {_md_cell(criterion.name)} | {_md_cell(criterion.category)} | _unscored_ | | |")
    lines.append("")
    lines.append(f"**Weighted score: {weighted_score(taxonomy, vendor):.2f} / 5.00**")
    return "\n".join(lines)


def render_comparison_matrix(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> str:
    lines = ["# DAST Tool Comparison Matrix", ""]
    header = "| Criterion | " + " | ".join(_md_cell(v.name) for v in vendors) + " |"
    separator = "|---|" + "---|" * len(vendors)
    lines += [header, separator]
    for criterion in taxonomy.criteria:
        row = [_md_cell(criterion.name)]
        for v in vendors:
            entry = v.score_for(criterion.id)
            row.append(f"{entry.score:g}" if entry else "-")
        lines.append("| " + " | ".join(row) + " |")
    totals = ["**Weighted Total**"] + [f"{weighted_score(taxonomy, v):.2f}" for v in vendors]
    lines.append("| " + " | ".join(totals) + " |")
    return "\n".join(lines)


def write_markdown(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for v in vendors:
        (out_dir / f"scorecard-{v.id}.md").write_text(render_scorecard(taxonomy, v))
    (out_dir / "comparison-matrix.md").write_text(render_comparison_matrix(taxonomy, vendors))
