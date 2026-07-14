# Report Disclaimer & Hyperlinks (Code) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a draft/sample disclaimer to every deterministic report artifact (`comparison-matrix.md`, `scorecard-<id>.md`, `dashboard.html`, `comparison-matrix.xlsx`) and auto-linkify evidence source citations in scorecards.

**Architecture:** Three independent, per-file tasks in `core/render/` — `markdown.py` (disclaimer + `_linkify_sources`), `html.py` (disclaimer div), `xlsx.py` (disclaimer rows). No interface dependency between tasks; each is separately testable.

**Tech Stack:** Python, pytest, openpyxl (xlsx). No new dependencies.

## Global Constraints

- This is Track A (code) only. Track B (`dast-report`/`dast-shortlist` skill-instruction edits) is a separate plan.
- No new data fields, no `Criterion`/`Vendor`/`ScoreEntry` model changes.
- `comparison-matrix.md` does not gain an evidence column — linkification applies only where evidence text is already shown (`render_scorecard`).
- The `_linkify_sources` regex must be used exactly as given below — it has already been verified against every real "Source:" citation in `data/candidates/*.yaml` (30 strings) plus 4 negative cases. Do not redesign it.
- `tests/test_render_markdown.py` and `tests/test_render_html.py`'s existing tests must keep passing unmodified — only new test functions added.
- `tests/test_render_xlsx.py`'s existing test **must be deliberately updated** (not left unmodified): inserting a disclaimer row + blank spacer row shifts the header from row 1 to row 3 and the first vendor's first score from row 2 to row 4. This is an intended consequence of the design, not a regression to avoid.
- Use `uv run pytest` for every test run. Never modify `uv.lock`.

---

### Task 1: Disclaimer + evidence-source linkification in `core/render/markdown.py`

**Files:**
- Modify: `core/render/markdown.py` (full-file replacement)
- Test: `tests/test_render_markdown.py` (extend import line, append new test functions — do not edit any existing test)

**Interfaces:**
- Produces: `_linkify_sources(text: str) -> str`, `_DISCLAIMER: str` (module-level constant) — no other task in this plan consumes these (html.py and xlsx.py get their own independent disclaimer constants, see Tasks 2/3).

- [ ] **Step 1: Write the failing tests**

Update the import line at the top of `tests/test_render_markdown.py` from:

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

to:

```python
from core.render.markdown import (
    _linkify_sources,
    _ordered_categories,
    category_weighted_score,
    render_comparison_matrix,
    render_scorecard,
    render_scoring_legend,
    weighted_score,
    write_markdown,
)
```

Then append these test functions to the end of `tests/test_render_markdown.py`:

```python
def test_linkify_sources_wraps_clean_url_citation():
    text = "...weaker JS-rendered SPA content discovery than ZAP's AJAX Spider. Source: github.com/projectdiscovery/nuclei-templates"
    result = _linkify_sources(text)
    assert "[github.com/projectdiscovery/nuclei-templates](https://github.com/projectdiscovery/nuclei-templates)" in result


def test_linkify_sources_wraps_bare_domain_with_no_path():
    text = "...not scanning for unknown/rogue external assets like a network-based ASM tool. Source: docs.stackhawk.com"
    result = _linkify_sources(text)
    assert "[docs.stackhawk.com](https://docs.stackhawk.com)" in result


def test_linkify_sources_handles_multiple_comma_separated_urls():
    text = (
        "...StackHawk's own marketed differentiator. Source: "
        "stackhawk.com/blog/business-logic-testing, docs.stackhawk.com/hawkscan/business-logic-testing"
    )
    result = _linkify_sources(text)
    assert (
        "[stackhawk.com/blog/business-logic-testing](https://stackhawk.com/blog/business-logic-testing), "
        "[docs.stackhawk.com/hawkscan/business-logic-testing](https://docs.stackhawk.com/hawkscan/business-logic-testing)"
    ) in result


def test_linkify_sources_stops_before_trailing_prose():
    text = "...fully air-gapped operation not confirmed. Source: projectdiscovery.io platform docs"
    result = _linkify_sources(text)
    assert "[projectdiscovery.io](https://projectdiscovery.io) platform docs" in result


def test_linkify_sources_strips_trailing_sentence_punctuation():
    text = (
        "...against a large community rule library). Source: ProjectDiscovery's own GitHub project "
        "(github.com/projectdiscovery/nuclei)."
    )
    result = _linkify_sources(text)
    assert "([github.com/projectdiscovery/nuclei](https://github.com/projectdiscovery/nuclei))." in result


def test_linkify_sources_ignores_version_numbers():
    text = "v3.2 added real static + dynamic authentication"
    assert _linkify_sources(text) == text


def test_linkify_sources_ignores_dotted_version_numbers():
    text = "PCI DSS v4.0.1 mapping blog post"
    assert _linkify_sources(text) == text


def test_linkify_sources_ignores_abbreviations():
    text = "e.g. some example, i.e. another"
    assert _linkify_sources(text) == text


def test_linkify_sources_ignores_regulation_codes():
    text = "23 NYCRR 500 guidance"
    assert _linkify_sources(text) == text


def test_render_scorecard_includes_disclaimer():
    scorecard = render_scorecard(_sample_taxonomy(), _sample_vendor())
    assert "Draft/sample output" in scorecard
    assert "not a final vendor recommendation" in scorecard


def test_render_comparison_matrix_includes_disclaimer():
    matrix = render_comparison_matrix(_sample_taxonomy(), [_sample_vendor()])
    assert "Draft/sample output" in matrix
    assert "not a final vendor recommendation" in matrix


def test_render_scorecard_linkifies_evidence_with_source_citation():
    taxonomy = _sample_taxonomy()
    vendor = Vendor(id="v3", name="Vendor Three", source=VendorSource.DISCOVERED)
    vendor.scores.append(
        ScoreEntry(
            criterion_id="c1",
            score=4,
            evidence="Some finding. Source: example.com/docs/page",
            confidence=Confidence.PAPER,
        )
    )
    scorecard = render_scorecard(taxonomy, vendor)
    assert "[example.com/docs/page](https://example.com/docs/page)" in scorecard
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_markdown.py -v`
Expected: collection error / `ImportError: cannot import name '_linkify_sources' from 'core.render.markdown'` (the function doesn't exist yet).

- [ ] **Step 3: Replace the entire file with the new implementation**

Replace the entire contents of `core/render/markdown.py` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_markdown.py -v`
Expected: all tests PASS (12 pre-existing + 12 new = 24 total).

- [ ] **Step 5: Commit**

```bash
git add core/render/markdown.py tests/test_render_markdown.py
git commit -m "Add draft/sample disclaimer and evidence-source linkification to markdown renderers"
```

---

### Task 2: Disclaimer banner in `core/render/html.py`

**Files:**
- Modify: `core/render/html.py` (full-file replacement)
- Test: `tests/test_render_html.py` (append a new test function — do not edit the existing test)

**Interfaces:**
- N/A — independent of Task 1 and Task 3; `write_html`'s signature is unchanged.

- [ ] **Step 1: Write the failing test**

Append this test function to the end of `tests/test_render_html.py`:

```python
def test_write_html_includes_disclaimer(tmp_path):
    out_path = tmp_path / "dashboard.html"
    write_html(_sample_taxonomy(), [_sample_vendor()], out_path)
    html = out_path.read_text()
    assert "Draft/sample output" in html
    assert "not a final vendor recommendation" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render_html.py -v`
Expected: `test_write_html_includes_disclaimer` FAILS (the disclaimer text isn't in the output yet). `test_write_html_includes_vendor_and_criterion_names` still PASSES.

- [ ] **Step 3: Replace the entire file with the new implementation**

Replace the entire contents of `core/render/html.py` with:

```python
# core/render/html.py
from __future__ import annotations

import html as html_lib
from pathlib import Path

from ..models import CriteriaTaxonomy, Vendor
from .markdown import weighted_score

_SORT_SCRIPT = """
<script>
function sortTable(colIndex) {
  const table = document.querySelector('table');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const asc = table.dataset.sortCol == colIndex && table.dataset.sortDir !== 'asc';
  rows.sort((a, b) => {
    const av = a.children[colIndex].textContent.trim();
    const bv = b.children[colIndex].textContent.trim();
    const an = parseFloat(av);
    const bn = parseFloat(bv);
    const cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
    return asc ? cmp : -cmp;
  });
  rows.forEach((r) => tbody.appendChild(r));
  table.dataset.sortCol = colIndex;
  table.dataset.sortDir = asc ? 'asc' : 'desc';
}
</script>
"""

_DISCLAIMER_HTML = (
    '<div style="border: 1px solid #c00; background: #fee; padding: 0.75rem; margin-bottom: 1rem;">\n'
    "🚧 Draft/sample output demonstrating what dast-bench produces — not a final vendor "
    "recommendation. Scores, weights, and evidence below are illustrative of a real "
    "evaluation in progress.\n"
    "</div>"
)


def write_html(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None:
    header_cells = ["Criterion", "Category"] + [html_lib.escape(v.name) for v in vendors]
    header_html = "".join(f'<th onclick="sortTable({i})">{name}</th>' for i, name in enumerate(header_cells))

    rows = []
    for criterion in taxonomy.criteria:
        cells = "".join(
            f"<td>{(entry.score if (entry := v.score_for(criterion.id)) else '-')}</td>" for v in vendors
        )
        rows.append(f"<tr><td>{html_lib.escape(criterion.name)}</td><td>{html_lib.escape(criterion.category)}</td>{cells}</tr>")

    totals = "".join(f"<td>{weighted_score(taxonomy, v):.2f}</td>" for v in vendors)

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DAST Comparison Matrix</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
th {{ cursor: pointer; }}
tfoot td {{ font-weight: bold; }}
</style>
</head>
<body>
<h1>DAST Tool Comparison Matrix</h1>
{_DISCLAIMER_HTML}
<table>
<thead><tr>{header_html}</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
<tfoot><tr><td>Weighted Total</td><td></td>{totals}</tr></tfoot>
</table>
{_SORT_SCRIPT}
</body>
</html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_html.py -v`
Expected: both tests PASS (1 pre-existing + 1 new = 2 total).

- [ ] **Step 5: Commit**

```bash
git add core/render/html.py tests/test_render_html.py
git commit -m "Add draft/sample disclaimer banner to HTML dashboard"
```

---

### Task 3: Disclaimer rows in `core/render/xlsx.py`

**Files:**
- Modify: `core/render/xlsx.py` (full-file replacement)
- Test: `tests/test_render_xlsx.py` (update the existing test's row-position assertions, add a new test function)

**Interfaces:**
- N/A — independent of Task 1 and Task 2; `write_xlsx`'s signature is unchanged.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_render_xlsx.py` with:

```python
from openpyxl import load_workbook

from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.render.xlsx import write_xlsx


def _sample_taxonomy() -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="API Coverage", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="Noise Reduction", description="d", weight=40, rubric="r"),
        ]
    )


def _sample_vendor() -> Vendor:
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2, evidence="trial", confidence=Confidence.HANDS_ON))
    return vendor


def test_write_xlsx_creates_sheet_with_header_and_vendor_column(tmp_path):
    out_path = tmp_path / "comparison-matrix.xlsx"
    write_xlsx(_sample_taxonomy(), [_sample_vendor()], out_path)
    wb = load_workbook(out_path)
    ws = wb["Comparison"]
    header = [cell.value for cell in ws[3]]
    assert header == ["Criterion", "Category", "Weight", "Vendor One"]
    assert ws.cell(row=4, column=4).value == 4
    last_row = [cell.value for cell in ws[ws.max_row]]
    assert last_row[0] == "Weighted Total"
    assert last_row[3] == 4 * 0.6 + 2 * 0.4


def test_write_xlsx_includes_disclaimer(tmp_path):
    out_path = tmp_path / "comparison-matrix.xlsx"
    write_xlsx(_sample_taxonomy(), [_sample_vendor()], out_path)
    wb = load_workbook(out_path)
    ws = wb["Comparison"]
    first_cell = ws.cell(row=1, column=1).value
    assert "Draft/sample output" in first_cell
    assert "not a final vendor recommendation" in first_cell
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_xlsx.py -v`
Expected: both tests FAIL — `test_write_xlsx_creates_sheet_with_header_and_vendor_column` fails because the header is still at row 1 (not yet shifted to row 3), and `test_write_xlsx_includes_disclaimer` fails because row 1 doesn't contain the disclaimer yet.

- [ ] **Step 3: Replace the entire file with the new implementation**

Replace the entire contents of `core/render/xlsx.py` with:

```python
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from ..models import CriteriaTaxonomy, Vendor
from .markdown import weighted_score

_DISCLAIMER = (
    "🚧 Draft/sample output demonstrating what dast-bench produces -- "
    "not a final vendor recommendation. Scores, weights, and evidence "
    "below are illustrative of a real evaluation in progress."
)


def write_xlsx(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Comparison"
    ws.append([_DISCLAIMER])
    ws.append([])
    ws.append(["Criterion", "Category", "Weight"] + [v.name for v in vendors])
    for criterion in taxonomy.criteria:
        row = [criterion.name, criterion.category, criterion.weight]
        for v in vendors:
            entry = v.score_for(criterion.id)
            row.append(entry.score if entry else None)
        ws.append(row)
    ws.append(["Weighted Total", "", ""] + [round(weighted_score(taxonomy, v), 2) for v in vendors])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_xlsx.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS, no regressions elsewhere (in particular `tests/test_cli_render.py`, which only checks that `dast-bench render` exits 0 and creates the expected files — it doesn't assert on exact content).

- [ ] **Step 6: Commit**

```bash
git add core/render/xlsx.py tests/test_render_xlsx.py
git commit -m "Add draft/sample disclaimer rows to XLSX comparison matrix"
```
