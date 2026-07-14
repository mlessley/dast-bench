from __future__ import annotations

from pathlib import Path
import re

from ..models import CriteriaTaxonomy, Vendor

_RUBRIC_MARKER = re.compile(r"(?<!\d)([135]):\s")
_DOMAIN_TOKEN = re.compile(r"\b((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s,;]*)?)")

_DISCLAIMER = (
    "> 🚧 Draft/sample output demonstrating what dast-bench produces — "
    "not a final vendor recommendation. Scores, weights, and evidence "
    "below are illustrative of a real evaluation in progress."
)


def _md_cell(value: str) -> str:
    """Escape special characters in Markdown table cells."""
    return value.replace("|", "\\|").replace("\n", " ")


def _linkify_sources(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        stripped = token.rstrip(".,;:)")
        trailing = token[len(stripped):]
        return f"[{stripped}](https://{stripped}){trailing}"

    return _DOMAIN_TOKEN.sub(replace, text)


def weighted_score(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> float:
    total = 0.0
    for criterion in taxonomy.criteria:
        entry = vendor.score_for(criterion.id)
        if entry:
            total += entry.score * (criterion.weight / 100.0)
    return total


def _ordered_categories(taxonomy: CriteriaTaxonomy) -> list[str]:
    seen: list[str] = []
    for criterion in taxonomy.criteria:
        if criterion.category not in seen:
            seen.append(criterion.category)
    return seen


def category_weighted_score(taxonomy: CriteriaTaxonomy, vendor: Vendor, category: str) -> float:
    total = 0.0
    category_weight = 0.0
    for criterion in taxonomy.criteria:
        if criterion.category != category:
            continue
        category_weight += criterion.weight
        entry = vendor.score_for(criterion.id)
        if entry:
            total += entry.score * criterion.weight
    return total / category_weight if category_weight else 0.0


def render_scoring_legend(taxonomy: CriteriaTaxonomy) -> str:
    lines = ["## Scoring Legend", ""]
    for category in _ordered_categories(taxonomy):
        lines.append(f"### {category}")
        lines.append("")
        for criterion in taxonomy.criteria:
            if criterion.category != category:
                continue
            lines.append(f"**{_md_cell(criterion.name)}**")
            parts = _RUBRIC_MARKER.split(criterion.rubric)
            for i in range(1, len(parts), 2):
                marker = parts[i]
                text = parts[i + 1].strip() if i + 1 < len(parts) else ""
                lines.append(f"- {marker}: {_md_cell(text)}")
            lines.append("")
    return "\n".join(lines).rstrip("\n")


def render_scorecard(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> str:
    lines = [f"# {_md_cell(vendor.name)} Scorecard", "", _DISCLAIMER, "", f"Status: {vendor.status.value}", ""]
    lines.append("| Criterion | Category | Weight | Score | Evidence | Confidence |")
    lines.append("|---|---|---|---|---|---|")
    for criterion in taxonomy.criteria:
        entry = vendor.score_for(criterion.id)
        if entry:
            lines.append(
                f"| {_md_cell(criterion.name)} | {_md_cell(criterion.category)} | {criterion.weight:g} | {entry.score:g} | {_md_cell(_linkify_sources(entry.evidence))} | "
                f"{entry.confidence.value} |"
            )
        else:
            lines.append(
                f"| {_md_cell(criterion.name)} | {_md_cell(criterion.category)} | {criterion.weight:g} | _unscored_ | | |"
            )
    lines.append("")
    lines.append("## Category Breakdown")
    lines.append("")
    lines.append("| Category | Weight | Weighted Score |")
    lines.append("|---|---|---|")
    for category in _ordered_categories(taxonomy):
        category_weight = sum(c.weight for c in taxonomy.criteria if c.category == category)
        lines.append(
            f"| {_md_cell(category)} | {category_weight:g} | {category_weighted_score(taxonomy, vendor, category):.2f} |"
        )
    lines.append("")
    lines.append(f"**Weighted score: {weighted_score(taxonomy, vendor):.2f} / 5.00**")
    return "\n".join(lines)


def render_comparison_matrix(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> str:
    lines = ["# DAST Tool Comparison Matrix", "", _DISCLAIMER, ""]
    lines.append(render_scoring_legend(taxonomy))
    lines.append("")
    header = "| Criterion | Weight | " + " | ".join(_md_cell(v.name) for v in vendors) + " |"
    separator = "|---|---|" + "---|" * len(vendors)
    lines += [header, separator]
    for criterion in taxonomy.criteria:
        row = [_md_cell(criterion.name), f"{criterion.weight:g}"]
        for v in vendors:
            entry = v.score_for(criterion.id)
            row.append(f"{entry.score:g}" if entry else "-")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("## Category Breakdown")
    lines.append("")
    cat_header = "| Category | Weight | " + " | ".join(_md_cell(v.name) for v in vendors) + " |"
    cat_separator = "|---|---|" + "---|" * len(vendors)
    lines += [cat_header, cat_separator]
    for category in _ordered_categories(taxonomy):
        category_weight = sum(c.weight for c in taxonomy.criteria if c.category == category)
        row = [_md_cell(category), f"{category_weight:g}"]
        for v in vendors:
            row.append(f"{category_weighted_score(taxonomy, v, category):.2f}")
        lines.append("| " + " | ".join(row) + " |")
    total_weight = sum(c.weight for c in taxonomy.criteria)
    totals = ["**Weighted Total**", f"{total_weight:g}"] + [f"{weighted_score(taxonomy, v):.2f}" for v in vendors]
    lines.append("| " + " | ".join(totals) + " |")
    return "\n".join(lines)


def write_markdown(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for v in vendors:
        (out_dir / f"scorecard-{v.id}.md").write_text(render_scorecard(taxonomy, v))
    (out_dir / "comparison-matrix.md").write_text(render_comparison_matrix(taxonomy, vendors))
