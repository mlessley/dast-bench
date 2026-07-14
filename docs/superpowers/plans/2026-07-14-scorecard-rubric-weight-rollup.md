# Scorecard Rubric, Weight & Category Roll-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose already-existing scoring rubric anchors and criterion weights in `dast-bench`'s markdown output, and add a deterministic per-category weighted subtotal between the 29 individual criterion rows and the grand total.

**Architecture:** Three new pure functions in `core/render/markdown.py` (`_ordered_categories`, `category_weighted_score`, `render_scoring_legend`), then wiring them into the existing `render_scorecard`/`render_comparison_matrix` output as additive sections. No model or schema changes — `rubric` and `weight` already exist on `Criterion`.

**Tech Stack:** Python, Pydantic (existing models, unchanged), pytest, `uv`.

## Global Constraints

- Scope is `core/render/markdown.py` and `tests/test_render_markdown.py` only — no changes to `core/render/xlsx.py`, `core/render/html.py`, `core/models.py`, `data/criteria.yaml`, or any `.claude/skills/` file.
- No "Enterprise Takeaway / Fit" narrative text and no "Where They Win" vendor comparison table — those are `dast-report` skill-authored judgment, out of scope here.
- Existing function signatures (`weighted_score`, `render_scorecard`, `render_comparison_matrix`, `write_markdown`) stay exactly as they are — all changes are additive to their *output*, not their signatures.
- All 5 existing tests in `tests/test_render_markdown.py` must keep passing unmodified — only add new test functions and extend the shared import line, never edit an existing test's body or assertions.
- Use `uv run pytest` for every test run (never bare `pytest`/`pip`). Never modify `uv.lock`.
- Every rubric string in `data/criteria.yaml` has been verified to contain exactly one `1:`, `3:`, `5:` marker in that order (checked via `re.findall(r'(?<!\d)([135]):\s', rubric)` against all 29 real criteria) — safe to parse with `re.split(r'(?<!\d)([135]):\s', rubric)` with no fallback-handling needed for malformed rubric strings.

---

### Task 1: Category math + scoring legend (new pure functions)

**Files:**
- Modify: `core/render/markdown.py:1-5` (add `import re`), and insert three new functions after `weighted_score` (currently ends at line 19) and before `render_scorecard` (currently starts at line 22)
- Test: `tests/test_render_markdown.py` (add a new taxonomy helper + 5 new test functions)

**Interfaces:**
- Produces: `_ordered_categories(taxonomy: CriteriaTaxonomy) -> list[str]`, `category_weighted_score(taxonomy: CriteriaTaxonomy, vendor: Vendor, category: str) -> float`, `render_scoring_legend(taxonomy: CriteriaTaxonomy) -> str` — Task 2 imports and calls all three.

- [ ] **Step 1: Write the failing tests**

Add this taxonomy helper and these five test functions to the end of `tests/test_render_markdown.py` (do not touch anything already in the file):

```python
def _rubric_taxonomy() -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(
                id="c1",
                category="Coverage",
                name="API Coverage",
                description="d",
                weight=60,
                rubric="1: No API coverage at all. 3: Covers REST but not GraphQL. 5: Full REST and GraphQL coverage.",
            ),
            Criterion(
                id="c2",
                category="Coverage",
                name="Shadow API Discovery",
                description="d",
                weight=15,
                rubric="1: No discovery. 3: Basic heuristic discovery. 5: Full traffic-analysis-based discovery.",
            ),
            Criterion(id="c3", category="DX", name="Noise Reduction", description="d", weight=25, rubric="r"),
        ]
    )


def test_ordered_categories_preserves_first_occurrence_order():
    taxonomy = _rubric_taxonomy()
    assert _ordered_categories(taxonomy) == ["Coverage", "DX"]


def test_category_weighted_score_combines_only_that_categorys_criteria():
    taxonomy = _rubric_taxonomy()
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c3", score=5, evidence="docs", confidence=Confidence.PAPER))
    # Coverage: (4*60 + 2*15) / (60+15) = 270/75 = 3.6
    assert category_weighted_score(taxonomy, vendor, "Coverage") == 3.6
    # DX: (5*25) / 25 = 5.0
    assert category_weighted_score(taxonomy, vendor, "DX") == 5.0


def test_category_weighted_score_missing_score_drags_score_down():
    taxonomy = _rubric_taxonomy()
    vendor = Vendor(id="v2", name="Vendor Two", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=5, evidence="docs", confidence=Confidence.PAPER))
    # c2 unscored: (5*60 + 0) / (60+15) = 300/75 = 4.0, not 5.0 -- missing scores drag the category down,
    # mirroring how the existing overall weighted_score() already treats unscored criteria.
    assert category_weighted_score(taxonomy, vendor, "Coverage") == 4.0


def test_category_weighted_score_returns_zero_for_unknown_category():
    taxonomy = _rubric_taxonomy()
    vendor = Vendor(id="v3", name="Vendor Three", source=VendorSource.DISCOVERED)
    assert category_weighted_score(taxonomy, vendor, "Nonexistent") == 0.0


def test_render_scoring_legend_parses_rubric_anchors_grouped_by_category():
    legend = render_scoring_legend(_rubric_taxonomy())
    assert "## Scoring Legend" in legend
    assert "### Coverage" in legend
    assert "### DX" in legend
    assert "**API Coverage**" in legend
    assert "- 1: No API coverage at all." in legend
    assert "- 3: Covers REST but not GraphQL." in legend
    assert "- 5: Full REST and GraphQL coverage." in legend
```

Update the existing import line at the top of `tests/test_render_markdown.py` from:

```python
from core.render.markdown import render_comparison_matrix, render_scorecard, weighted_score, write_markdown
```

to:

```python
from core.render.markdown import (
    _ordered_categories,
    category_weighted_score,
    render_comparison_matrix,
    render_scorecard,
    render_scoring_legend,
    weighted_score,
    write_markdown,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_markdown.py -v`
Expected: collection error / `ImportError: cannot import name '_ordered_categories' from 'core.render.markdown'` (the three new names don't exist yet).

- [ ] **Step 3: Implement the three new functions**

In `core/render/markdown.py`, change the top of the file from:

```python
from __future__ import annotations

from pathlib import Path

from ..models import CriteriaTaxonomy, Vendor
```

to:

```python
from __future__ import annotations

from pathlib import Path
import re

from ..models import CriteriaTaxonomy, Vendor

_RUBRIC_MARKER = re.compile(r"(?<!\d)([135]):\s")
```

Then insert these three new functions immediately after `weighted_score` (which currently ends at line 19 with `return total`) and before `def render_scorecard`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_markdown.py -v`
Expected: all tests PASS, including the 5 existing ones and the 5 new ones from Step 1.

- [ ] **Step 5: Commit**

```bash
git add core/render/markdown.py tests/test_render_markdown.py
git commit -m "Add category-weighted scoring and rubric legend rendering functions"
```

---

### Task 2: Wire rubric/weight/roll-up into scorecard and comparison matrix output

**Files:**
- Modify: `core/render/markdown.py` (`render_scorecard`, currently lines 22-37; `render_comparison_matrix`, currently lines 40-53)
- Test: `tests/test_render_markdown.py` (add 2 new test functions)

**Interfaces:**
- Consumes: `_ordered_categories(taxonomy) -> list[str]`, `category_weighted_score(taxonomy, vendor, category) -> float`, `render_scoring_legend(taxonomy) -> str` (all from Task 1, unchanged signatures)

- [ ] **Step 1: Write the failing tests**

Add these two test functions to the end of `tests/test_render_markdown.py`:

```python
def test_render_scorecard_includes_weight_column_and_category_breakdown():
    scorecard = render_scorecard(_sample_taxonomy(), _sample_vendor())
    assert "| Criterion | Category | Weight | Score | Evidence | Confidence |" in scorecard
    assert "## Category Breakdown" in scorecard
    assert "| Category | Weight | Weighted Score |" in scorecard
    # Coverage category has only c1 (weight 60), scored 4 -> category score 4.00
    assert "| Coverage | 60 | 4.00 |" in scorecard
    # DX category has only c2 (weight 40), scored 2 -> category score 2.00
    assert "| DX | 40 | 2.00 |" in scorecard


def test_render_comparison_matrix_includes_weight_column_and_category_breakdown():
    matrix = render_comparison_matrix(_sample_taxonomy(), [_sample_vendor()])
    assert "## Scoring Legend" in matrix
    assert "| Criterion | Weight | Vendor One |" in matrix
    assert "## Category Breakdown" in matrix
    assert "| Category | Weight | Vendor One |" in matrix
    assert "| Coverage | 60 | 4.00 |" in matrix
    assert "| DX | 40 | 2.00 |" in matrix
    assert "| **Weighted Total** | 100 | 3.20 |" in matrix
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_markdown.py -v`
Expected: the 2 new tests FAIL (assertion errors — the new columns/sections don't exist in the output yet). All other tests still PASS.

- [ ] **Step 3: Implement the changes to render_scorecard and render_comparison_matrix**

Replace the entire `render_scorecard` function (currently lines 22-37 of `core/render/markdown.py`) with:

```python
def render_scorecard(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> str:
    lines = [f"# {_md_cell(vendor.name)} Scorecard", "", f"Status: {vendor.status.value}", ""]
    lines.append("| Criterion | Category | Weight | Score | Evidence | Confidence |")
    lines.append("|---|---|---|---|---|---|")
    for criterion in taxonomy.criteria:
        entry = vendor.score_for(criterion.id)
        if entry:
            lines.append(
                f"| {_md_cell(criterion.name)} | {_md_cell(criterion.category)} | {criterion.weight:g} | {entry.score:g} | {_md_cell(entry.evidence)} | "
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
```

Replace the entire `render_comparison_matrix` function (currently lines 40-53 of `core/render/markdown.py`) with:

```python
def render_comparison_matrix(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> str:
    lines = ["# DAST Tool Comparison Matrix", ""]
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
```

Note: the `**Weighted Total**` row is deliberately kept as the final row of the *Category Breakdown* table (no blank line before it), not a standalone line — it was already a table row before this change (aligned under the criterion table's columns), and a lone `| ... |` line with no header/separator directly above it would not render as a valid markdown table row. Attaching it to the Category Breakdown table (whose columns are shape-compatible: label, weight, one column per vendor) preserves valid table syntax while still satisfying "the roll-up sits between the criterion table and the total."

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_markdown.py -v`
Expected: all tests PASS (5 original + 5 from Task 1 + 2 from this task = 12 total).

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS, no regressions in `tests/test_cli_render.py` or elsewhere (those tests only check that `dast-bench render` exits 0 and creates files — they don't assert on exact table shape).

- [ ] **Step 6: Commit**

```bash
git add core/render/markdown.py tests/test_render_markdown.py
git commit -m "Render rubric legend, weight columns, and category roll-up in scorecards and comparison matrix"
```
