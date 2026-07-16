# Stakeholder Review Workbook UX Polish Round 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the top-10-row yellow shading, restructure the Executive Summary tab into a renamed "Overview" tab with a plain-language intro block, move its Legend to a new "How This Works" tab with added Methodology content, fix the chart by switching to a vertical column layout, give every tab a consistent 16pt title, add a Reviewers-tab caveat note, change the reviewer placeholder wording, and re-add evidence-cell hyperlinks.

**Architecture:** All changes live in `core/render/stakeholder_workbook.py` (workbook generation). No changes to `core/stakeholder_review.py` in this round. No new files — `_add_how_it_works_sheet` is a new function alongside the existing `_add_executive_summary_sheet` and `_add_reviewers_sheet`.

**Tech Stack:** Python, openpyxl, pytest, LibreOffice headless (`soffice` + `pdftoppm`, already installed in this container) for visual verification.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-07-16-stakeholder-review-workbook-ux-polish-round5-design.md` — read it before starting if anything below is unclear.
- **Do not build the auto-pending redesign or any cross-version-merge/reviewer-reclaim tooling.** Both were discussed and explicitly deferred — see the spec's "Explicitly deferred" section. If a task's brief seems to imply either, that's a bug in the brief — escalate rather than build it.
- Don't touch `core/stakeholder_review.py`, `merge()`, or add any reviewer-slot locking/protection mechanism — out of scope for this round (and a protection mechanism was explicitly declined in round 4).
- The vendor-row highlight on the Overview/Executive-Summary ranked table (`_TIER_FILL` used for the #1-ranked vendor's row, around line 221 in the current file) is a **different feature** from the top-10-criteria tier shading this round removes (item 1). Do not touch the vendor-row highlight.
- Sheet order after this round: Overview (formerly "Executive Summary"), Reviewers, one tab per vendor, How This Works (last).
- Every tab's row-1 title cell: 16pt bold, row height 28.

---

### Task 1: Remove top-10-row yellow shading

**Files:**
- Modify: `core/render/stakeholder_workbook.py:31-33` (constants), `core/render/stakeholder_workbook.py:452-458` (per-row fill logic inside `generate_workbook`)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Removes `_TIER_FILL_ODD` (constant). `_TIER_FILL` stays — it's still used by the unrelated vendor-row highlight in `_add_executive_summary_sheet`.
- No new functions.

- [ ] **Step 1: Write the failing test**

Find `test_generate_workbook_bands_continuously_under_tier_highlight` in `tests/test_stakeholder_workbook.py` (currently around line 673) and replace it:

```python
def test_generate_workbook_bands_continuously_regardless_of_tier(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Cat", name="C1", description="d", weight=100, rubric="r"),
            Criterion(id="c2", category="Cat", name="C2", description="d", weight=90, rubric="r"),
            Criterion(id="c3", category="Cat", name="C3", description="d", weight=80, rubric="r"),
            Criterion(id="c4", category="Cat", name="C4", description="d", weight=70, rubric="r"),
        ]
    )
    vendor = Vendor(id="v1", name="V1", source=VendorSource.DISCOVERED)
    for criterion_id in ("c1", "c2", "c3", "c4"):
        vendor.scores.append(ScoreEntry(criterion_id=criterion_id, score=4.0, evidence="e", confidence=Confidence.PAPER))

    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
        top_tier_count=2,
    )
    ws = load_workbook(out_path)["v1"]
    # Banding is continuous regardless of tier membership now -- no more
    # full-row yellow fill for the top 10 rows.
    assert ws.cell(row=4, column=1).fill.fgColor.rgb == "00000000"  # tier, even (i=0) -- no fill
    assert ws.cell(row=5, column=1).fill.fgColor.rgb == "00F2F2F2"  # tier, odd (i=1) -- banded
    assert ws.cell(row=6, column=1).fill.fgColor.rgb == "00000000"  # non-tier, even (i=2) -- no fill
    assert ws.cell(row=7, column=1).fill.fgColor.rgb == "00F2F2F2"  # non-tier, odd (i=3) -- banded
```

Also add a new test right after it confirming the pink-while-empty conditional formatting on top-tier Score cells still works (this behavior already exists via `CellIsRule` at what's currently line 474-478 — this test locks it in as unchanged):

```python
def test_generate_workbook_still_flags_empty_top_tier_score_cells(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
        top_tier_count=10,
    )
    ws = load_workbook(out_path)["v1"]
    rules = list(ws.conditional_formatting)
    assert len(rules) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_bands_continuously_regardless_of_tier -v`
Expected: FAIL — `assert '00FFF2CC' == '00000000'` (row 4 currently gets the yellow tier fill).

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, find:
```python
_TIER_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
_TIER_FILL_ODD = PatternFill(start_color="F9E79F", end_color="F9E79F", fill_type="solid")
_UNFILLED_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
```
Replace with:
```python
_TIER_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
_UNFILLED_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
```

Find (inside `generate_workbook`'s per-criterion-row loop):
```python
            if i < top_tier_count:
                tier_fill = _TIER_FILL_ODD if i % 2 == 1 else _TIER_FILL
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = tier_fill
            elif i % 2 == 1:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _BAND_FILL
```
Replace with:
```python
            if i % 2 == 1:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _BAND_FILL
```

Leave the conditional-formatting block (`if i < top_tier_count: ws.conditional_formatting.add(...)`, further down in the same loop, applying `_UNFILLED_FILL` to empty top-tier Score cells) completely untouched — that's the pink-while-empty behavior this task keeps.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_bands_continuously_regardless_of_tier tests/test_stakeholder_workbook.py::test_generate_workbook_still_flags_empty_top_tier_score_cells -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: rest of the suite still passes (no other test currently asserts on `_TIER_FILL_ODD`'s color).

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "fix: remove top-10-row yellow shading, keep pink-while-empty Score cells"
```

---

### Task 2: Overview tab restructure + new "How This Works" tab

**Files:**
- Modify: `core/render/stakeholder_workbook.py` (multiple locations, listed below)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- `_EXEC_SHEET_NAME` changes value from `"Executive Summary"` to `"Overview"`.
- Removes `_EXEC_LEGEND_HEADER_ROW`, `_EXEC_LEGEND_FIRST_ROW`, `_EXEC_LEGEND_LINES_TEMPLATE`.
- Adds `_EXEC_ABOUT_HEADER_ROW`, `_EXEC_ABOUT_FIRST_ROW`, `_EXEC_ABOUT_LINES` (used by `_add_executive_summary_sheet`, which drops its `top_tier_count` parameter — it's no longer needed there).
- Adds `_HOW_IT_WORKS_SHEET_NAME = "How This Works"`, `_HOW_IT_WORKS_TAB_COLOR = "808080"`, `_METHODOLOGY_HEADER_ROW`, `_METHODOLOGY_FIRST_ROW`, `_METHODOLOGY_LINES`, `_LEGEND_HEADER_ROW`, `_LEGEND_FIRST_ROW`, `_LEGEND_LINES` (module-level).
- Produces: `_add_how_it_works_sheet(wb: Workbook, top_tier_count: int) -> None`, called from `generate_workbook` as the last sheet added.
- `EXEC_TABLE_HEADER_ROW` and `EXEC_TABLE_FIRST_DATA_ROW` are recomputed from the new About-block length (values change from 11/12 to 8/9), but stay the same *names* — nothing outside this file imports their old values directly, so no other ripple.

- [ ] **Step 1: Write the failing tests**

In `tests/test_stakeholder_workbook.py`, update the import block. Find:
```python
from core.render.stakeholder_workbook import (
    _all_headers,
    _column_index,
    _EXEC_LEGEND_FIRST_ROW,
    _EXEC_LEGEND_HEADER_ROW,
    _EXEC_LEGEND_LINES_TEMPLATE,
    _REVIEWERS_FIRST_DATA_ROW,
    _REVIEWERS_NAME_COL,
    _REVIEWERS_ROLE_COL,
    _REVIEWERS_SHEET_NAME,
    _reviewer_slot_columns,
    _rollup_row_numbers,
    compute_priority_order,
    EXEC_TABLE_FIRST_DATA_ROW,
    EXEC_TABLE_HEADER_ROW,
    HEADER_ROW,
    generate_workbook,
)
```
Replace with:
```python
from core.render.stakeholder_workbook import (
    _all_headers,
    _column_index,
    _EXEC_ABOUT_FIRST_ROW,
    _EXEC_ABOUT_HEADER_ROW,
    _EXEC_ABOUT_LINES,
    _EXEC_SHEET_NAME,
    _HOW_IT_WORKS_SHEET_NAME,
    _LEGEND_FIRST_ROW,
    _LEGEND_HEADER_ROW,
    _LEGEND_LINES,
    _REVIEWERS_FIRST_DATA_ROW,
    _REVIEWERS_NAME_COL,
    _REVIEWERS_ROLE_COL,
    _REVIEWERS_SHEET_NAME,
    _reviewer_slot_columns,
    _rollup_row_numbers,
    compute_priority_order,
    EXEC_TABLE_FIRST_DATA_ROW,
    EXEC_TABLE_HEADER_ROW,
    HEADER_ROW,
    generate_workbook,
)
```

Now update every test that references the old sheet name or the old Legend location. Use `_EXEC_SHEET_NAME` (now `"Overview"`) and `_HOW_IT_WORKS_SHEET_NAME` (`"How This Works"`) instead of hardcoded strings everywhere below, so a future rename doesn't require touching every test again.

**2a.** Find (around line 106 and 132, both in reviewer-sheet tests):
```python
    assert wb.sheetnames == ["Executive Summary", _REVIEWERS_SHEET_NAME, "v1"]
```
Replace both occurrences with:
```python
    assert wb.sheetnames == [_EXEC_SHEET_NAME, _REVIEWERS_SHEET_NAME, "v1", _HOW_IT_WORKS_SHEET_NAME]
```

**2b.** Find `test_generate_workbook_title_and_header_rows_have_explicit_height` (around line 398) and replace its body from `wb = load_workbook(out_path)` through the `exec_ws` assertions:
```python
    wb = load_workbook(out_path)

    exec_ws = wb["Executive Summary"]
    assert exec_ws.row_dimensions[1].height == 26
    assert exec_ws.row_dimensions[_EXEC_LEGEND_HEADER_ROW].height == 20
    assert exec_ws.row_dimensions[EXEC_TABLE_HEADER_ROW].height == 34
```
with:
```python
    wb = load_workbook(out_path)

    exec_ws = wb[_EXEC_SHEET_NAME]
    assert exec_ws.row_dimensions[1].height == 28
    assert exec_ws.row_dimensions[_EXEC_ABOUT_HEADER_ROW].height == 20
    assert exec_ws.row_dimensions[EXEC_TABLE_HEADER_ROW].height == 34
```
(Leave the `vendor_ws` and `summary_header_row` assertions below it unchanged — those are Task 1/round-4 territory, untouched here.)

**2c.** Find `test_generate_workbook_adds_executive_summary_sheet_first_with_legend_and_ranked_table` (around line 482). Rename the test and replace its Legend-specific assertions with About-block assertions. Find:
```python
def test_generate_workbook_adds_executive_summary_sheet_first_with_legend_and_ranked_table(tmp_path):
```
Replace with:
```python
def test_generate_workbook_adds_overview_sheet_first_with_about_block_and_ranked_table(tmp_path):
```
Then find:
```python
    wb = load_workbook(out_path)
    assert wb.sheetnames[0] == "Executive Summary"
    ws = wb["Executive Summary"]
    assert ws.cell(row=1, column=1).value == "Executive Summary"
    assert ws.cell(row=3, column=1).value == "Legend"
    assert "top 10 priority" in ws.cell(row=5, column=1).value
```
Replace with:
```python
    wb = load_workbook(out_path)
    assert wb.sheetnames[0] == _EXEC_SHEET_NAME
    ws = wb[_EXEC_SHEET_NAME]
    assert ws.cell(row=1, column=1).value == _EXEC_SHEET_NAME
    assert ws.cell(row=_EXEC_ABOUT_HEADER_ROW, column=1).value == "About This Report"
    assert ws.cell(row=_EXEC_ABOUT_FIRST_ROW, column=1).value == _EXEC_ABOUT_LINES[0]
```
(The rest of that test — `header = [c.value for c in ws[EXEC_TABLE_HEADER_ROW]]` through the end — stays unchanged; `EXEC_TABLE_HEADER_ROW` and `EXEC_TABLE_FIRST_DATA_ROW` are still valid names, just recomputed.)

**2d.** Find and update the sheet-name lookup in these 5 tests (each currently has exactly one `load_workbook(out_path)["Executive Summary"]` — change to `load_workbook(out_path)[_EXEC_SHEET_NAME]`):
- `test_generate_workbook_executive_summary_ranks_by_normalized_average_not_raw_achieved_points`
- `test_generate_workbook_executive_summary_sorts_all_pending_vendor_last`
- `test_generate_workbook_executive_summary_includes_bar_chart`
- `test_generate_workbook_executive_summary_highlights_top_vendor_row`

(A 5th, `test_generate_workbook_bar_chart_category_axis_is_reversed`, is replaced entirely in Task 3 — don't touch it here.)

**2e.** Find `test_generate_workbook_executive_summary_legend_has_border_and_fill` (around line 703) and replace the whole test:
```python
def test_generate_workbook_executive_summary_legend_has_border_and_fill(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["Executive Summary"]
    legend_last_row = _EXEC_LEGEND_FIRST_ROW + len(_EXEC_LEGEND_LINES_TEMPLATE) - 1

    top_left = ws.cell(row=_EXEC_LEGEND_HEADER_ROW, column=1)
    assert top_left.fill.fgColor.rgb == "00F2F2F2"
    assert top_left.border.top.style == "thin"

    bottom_right = ws.cell(row=legend_last_row, column=5)
    assert bottom_right.fill.fgColor.rgb == "00F2F2F2"
    assert bottom_right.border.bottom.style == "thin"
```
Replace with:
```python
def test_generate_workbook_how_it_works_has_methodology_and_legend(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    wb = load_workbook(out_path)
    assert wb.sheetnames[-1] == _HOW_IT_WORKS_SHEET_NAME
    ws = wb[_HOW_IT_WORKS_SHEET_NAME]
    assert ws.cell(row=1, column=1).value == _HOW_IT_WORKS_SHEET_NAME
    assert ws.cell(row=3, column=1).value == "Methodology"
    assert ws.cell(row=_LEGEND_HEADER_ROW, column=1).value == "Legend"
    assert "top 10 priority" in ws.cell(row=_LEGEND_FIRST_ROW + 1, column=1).value

    legend_last_row = _LEGEND_FIRST_ROW + len(_LEGEND_LINES) - 1
    top_left = ws.cell(row=_LEGEND_FIRST_ROW, column=1)
    assert top_left.fill.fgColor.rgb == "00F2F2F2"
    assert top_left.border.top.style == "thin"

    bottom_right = ws.cell(row=legend_last_row, column=5)
    assert bottom_right.fill.fgColor.rgb == "00F2F2F2"
    assert bottom_right.border.bottom.style == "thin"
```

**2f.** Find `test_generate_workbook_executive_summary_legend_explains_weight` (around line 806) and replace:
```python
def test_generate_workbook_executive_summary_legend_explains_weight(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["Executive Summary"]
    weight_legend_row = _EXEC_LEGEND_FIRST_ROW + 5
    legend_text = ws.cell(row=weight_legend_row, column=1).value
    assert "Weight" in legend_text
    assert "set by the evaluator" in legend_text
```
Replace with:
```python
def test_generate_workbook_how_it_works_legend_explains_weight(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)[_HOW_IT_WORKS_SHEET_NAME]
    weight_legend_row = _LEGEND_FIRST_ROW + 5
    legend_text = ws.cell(row=weight_legend_row, column=1).value
    assert "Weight" in legend_text
    assert "set by the evaluator" in legend_text
```

**2g.** Add a new test for the corrected Legend content (tier + pending lines), right after the test added in 2e:
```python
def test_generate_workbook_how_it_works_legend_tier_and_pending_lines_are_corrected(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)[_HOW_IT_WORKS_SHEET_NAME]
    pending_line = ws.cell(row=_LEGEND_FIRST_ROW, column=1).value
    assert "marked pending automatically" not in pending_line
    assert "treat the Overview ranking as provisional" in pending_line

    tier_line = ws.cell(row=_LEGEND_FIRST_ROW + 1, column=1).value
    assert "gold left border" not in tier_line
    assert "Tier highlight (pink)" in tier_line
    assert "tinted while still empty" in tier_line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py -v 2>&1 | tail -60`
Expected: multiple FAILs and likely an `ImportError` at collection (the new names don't exist in the module yet) — that's expected at this stage.

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, find:
```python
_EXEC_SHEET_NAME = "Executive Summary"
_EXEC_TAB_COLOR = "1F4E78"
_EXEC_TITLE_ROW = 1
_EXEC_LEGEND_HEADER_ROW = 3
_EXEC_LEGEND_FIRST_ROW = 4
_EXEC_LEGEND_LINES_TEMPLATE = [
    "Pending rows: dast-scan results not yet available; locked until Round 2 populate fills them in.",
    "Tier highlight (light yellow): top {top_tier_count} priority criteria for this round, shown for quick scanning.",
    "Dispute = Yes requires a non-blank Rationale; discuss unresolved disputes before finalizing a score.",
    "Automated Confidence: 'paper' = desk research only; 'hands-on' = verified via dast-scan.",
    "Weighted Avg Score is normalized to a 0-5 scale and is comparable across vendors even when the "
    "number of pending criteria differs. Row order below is fixed when this workbook is generated and "
    "does not auto-resort if scores change later.",
    "Weight (on each vendor sheet) is each criterion's relative importance in the overall weighted "
    "score — the same value used in the actual score calculation, set by the evaluator when the "
    "criteria taxonomy was defined, not something a reviewer sets.",
]

EXEC_TABLE_HEADER_ROW = _EXEC_LEGEND_FIRST_ROW + len(_EXEC_LEGEND_LINES_TEMPLATE) + 1
EXEC_TABLE_FIRST_DATA_ROW = EXEC_TABLE_HEADER_ROW + 1
```
Replace with:
```python
_EXEC_SHEET_NAME = "Overview"
_EXEC_TAB_COLOR = "1F4E78"
_EXEC_TITLE_ROW = 1
_EXEC_ABOUT_HEADER_ROW = 3
_EXEC_ABOUT_FIRST_ROW = 4
_EXEC_ABOUT_LINES = [
    "This workbook ranks DAST (dynamic application security testing) vendors against a weighted set "
    "of evaluation criteria, blending automated desk research with hands-on benchmark testing where "
    "available.",
    "Reviewers can weigh in on any criterion on that vendor's tab and resolve disagreements with the "
    "automated score; resolved scores take precedence in the totals below. Claim a reviewer slot once "
    "on the \"Reviewers\" tab and it applies automatically to every vendor tab.",
    "See the \"How This Works\" tab (last tab) for the full methodology, scoring formulas, and "
    "definitions.",
]

EXEC_TABLE_HEADER_ROW = _EXEC_ABOUT_FIRST_ROW + len(_EXEC_ABOUT_LINES) + 1
EXEC_TABLE_FIRST_DATA_ROW = EXEC_TABLE_HEADER_ROW + 1

_HOW_IT_WORKS_SHEET_NAME = "How This Works"
_HOW_IT_WORKS_TAB_COLOR = "808080"
_METHODOLOGY_HEADER_ROW = 3
_METHODOLOGY_FIRST_ROW = 4
_METHODOLOGY_LINES = [
    "The evaluation criteria, categories, and weights were defined up front, before any vendor was "
    "researched, based on standard DAST-buying considerations — coverage, detection quality, "
    "production safety, developer experience, reporting, and deployment/data governance. Fixing the "
    "rubric first keeps the comparison consistent instead of retrofitting criteria to favor a "
    "particular tool.",
    "Each criterion has a written rubric describing what a 1 vs. a 3 vs. a 5 looks like. Automated "
    "scores come from structured desk research against that rubric — vendor docs, pricing pages, "
    "release notes, and public third-party reviews — with the evidence and reasoning captured "
    "alongside every score so it's traceable, not a black box.",
    "Two criteria, Detection Accuracy and False Positive Rate, also get a hands-on pass: the tool is "
    "run against known-vulnerable benchmark targets (OWASP Juice Shop, VAmPI) and the desk-research "
    "score is replaced with one based on real scan output. Confidence is upgraded from 'paper' to "
    "'hands-on' when that happens.",
    "Reviewer input on each vendor's tab exists to catch what desk research misses or gets wrong — "
    "resolved scores from reviewers take precedence over the automated ones in the final totals.",
]

_LEGEND_HEADER_ROW = _METHODOLOGY_FIRST_ROW + len(_METHODOLOGY_LINES) + 1
_LEGEND_FIRST_ROW = _LEGEND_HEADER_ROW + 1
_LEGEND_LINES = [
    "Pending rows: dast-scan results not yet available; locked until Round 2 populate fills them in. "
    "Until then, treat the Overview ranking as provisional.",
    "Tier highlight (pink): top {top_tier_count} priority Score cells are tinted while still empty, "
    "as a reminder they still need a value.",
    "Dispute = Yes requires a non-blank Rationale; discuss unresolved disputes before finalizing a score.",
    "Automated Confidence: 'paper' = desk research only; 'hands-on' = verified via dast-scan.",
    "Weighted Avg Score is normalized to a 0-5 scale and is comparable across vendors even when the "
    "number of pending criteria differs. Row order below is fixed when this workbook is generated and "
    "does not auto-resort if scores change later.",
    "Weight (on each vendor sheet) is each criterion's relative importance in the overall weighted "
    "score — the same value used in the actual score calculation, set by the evaluator when the "
    "criteria taxonomy was defined, not something a reviewer sets.",
]
```

Now find (inside `_add_executive_summary_sheet`'s signature and body):
```python
def _add_executive_summary_sheet(
    wb: Workbook,
    taxonomy: CriteriaTaxonomy,
    vendors: list[Vendor],
    pending_criteria: dict[str, set[str]],
    headers: list[str],
    top_tier_count: int,
) -> None:
    ws = wb.create_sheet(title=_EXEC_SHEET_NAME)
    ws.sheet_properties.tabColor = _EXEC_TAB_COLOR

    title_cell = ws.cell(row=_EXEC_TITLE_ROW, column=1, value=_EXEC_SHEET_NAME)
    title_cell.font = Font(bold=True, size=14)
    ws.row_dimensions[_EXEC_TITLE_ROW].height = 26

    legend_header_cell = ws.cell(row=_EXEC_LEGEND_HEADER_ROW, column=1, value="Legend")
    legend_header_cell.font = Font(bold=True)
    ws.row_dimensions[_EXEC_LEGEND_HEADER_ROW].height = 20
    for i, line in enumerate(_EXEC_LEGEND_LINES_TEMPLATE):
        ws.cell(row=_EXEC_LEGEND_FIRST_ROW + i, column=1, value=line.format(top_tier_count=top_tier_count))

    legend_last_row = _EXEC_LEGEND_FIRST_ROW + len(_EXEC_LEGEND_LINES_TEMPLATE) - 1
    for row in range(_EXEC_LEGEND_HEADER_ROW, legend_last_row + 1):
        for col in range(1, 6):
            cell = ws.cell(row=row, column=col)
            cell.fill = _BAND_FILL
            cell.border = _HEADER_BORDER

    categories = _ordered_categories(taxonomy)
```
Replace with:
```python
def _add_executive_summary_sheet(
    wb: Workbook,
    taxonomy: CriteriaTaxonomy,
    vendors: list[Vendor],
    pending_criteria: dict[str, set[str]],
    headers: list[str],
) -> None:
    ws = wb.create_sheet(title=_EXEC_SHEET_NAME)
    ws.sheet_properties.tabColor = _EXEC_TAB_COLOR

    title_cell = ws.cell(row=_EXEC_TITLE_ROW, column=1, value=_EXEC_SHEET_NAME)
    title_cell.font = Font(bold=True, size=16)
    ws.row_dimensions[_EXEC_TITLE_ROW].height = 28

    about_header_cell = ws.cell(row=_EXEC_ABOUT_HEADER_ROW, column=1, value="About This Report")
    about_header_cell.font = Font(bold=True)
    ws.row_dimensions[_EXEC_ABOUT_HEADER_ROW].height = 20
    for i, line in enumerate(_EXEC_ABOUT_LINES):
        ws.cell(row=_EXEC_ABOUT_FIRST_ROW + i, column=1, value=line)

    categories = _ordered_categories(taxonomy)
```

Now find the call site in `generate_workbook`:
```python
    _add_executive_summary_sheet(wb, taxonomy, vendors, pending_criteria, headers, top_tier_count)
    _add_reviewers_sheet(wb, reviewer_slots)
```
Replace with:
```python
    _add_executive_summary_sheet(wb, taxonomy, vendors, pending_criteria, headers)
    _add_reviewers_sheet(wb, reviewer_slots)
```

Add the new `_add_how_it_works_sheet` function. Place it right after `_add_reviewers_sheet` (find `def _all_headers(reviewer_slots: int) -> list[str]:` and insert before it):
```python
def _add_how_it_works_sheet(wb: Workbook, top_tier_count: int) -> None:
    ws = wb.create_sheet(title=_HOW_IT_WORKS_SHEET_NAME)
    ws.sheet_properties.tabColor = _HOW_IT_WORKS_TAB_COLOR
    ws.column_dimensions["A"].width = 100

    title_cell = ws.cell(row=1, column=1, value=_HOW_IT_WORKS_SHEET_NAME)
    title_cell.font = Font(bold=True, size=16)
    ws.row_dimensions[1].height = 28

    methodology_header_cell = ws.cell(row=_METHODOLOGY_HEADER_ROW, column=1, value="Methodology")
    methodology_header_cell.font = Font(bold=True)
    ws.row_dimensions[_METHODOLOGY_HEADER_ROW].height = 20
    for i, line in enumerate(_METHODOLOGY_LINES):
        cell = ws.cell(row=_METHODOLOGY_FIRST_ROW + i, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    legend_header_cell = ws.cell(row=_LEGEND_HEADER_ROW, column=1, value="Legend")
    legend_header_cell.font = Font(bold=True)
    ws.row_dimensions[_LEGEND_HEADER_ROW].height = 20
    for i, line in enumerate(_LEGEND_LINES):
        cell = ws.cell(row=_LEGEND_FIRST_ROW + i, column=1, value=line.format(top_tier_count=top_tier_count))
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    legend_last_row = _LEGEND_FIRST_ROW + len(_LEGEND_LINES) - 1
    for row in range(_LEGEND_FIRST_ROW, legend_last_row + 1):
        for col in range(1, 6):
            cell = ws.cell(row=row, column=col)
            cell.fill = _BAND_FILL
            cell.border = _HEADER_BORDER
            if col == 1:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
```

Finally, call it at the very end of `generate_workbook`, after the vendor loop, so it's the last sheet. Find:
```python
        for hidden_name in _HIDDEN_HEADERS:
            ws.column_dimensions[get_column_letter(_column_index(headers, hidden_name))].hidden = True
        ws.protection.sheet = True
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
```
Replace with:
```python
        for hidden_name in _HIDDEN_HEADERS:
            ws.column_dimensions[get_column_letter(_column_index(headers, hidden_name))].hidden = True
        ws.protection.sheet = True
    _add_how_it_works_sheet(wb, top_tier_count)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all pass. If any test not explicitly listed above still references `"Executive Summary"` as a literal string, update it to use `_EXEC_SHEET_NAME` the same way.

- [ ] **Step 5: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all pass (nothing outside `stakeholder_workbook.py`/its test file references the old Legend row constants or the "Executive Summary" name).

- [ ] **Step 6: Visually verify with a real render**

```bash
cd /devx/repos/dast-eval
uv run dast-bench stakeholder-review generate --vendor-id invicti --vendor-id veracode --vendor-id nuclei --vendor-id zap --vendor-id stackhawk --out /tmp/task2-check.xlsx
mkdir -p /tmp/task2-render
timeout 120 soffice --headless --convert-to pdf --outdir /tmp/task2-render /tmp/task2-check.xlsx
pdftoppm -png -r 150 -f 1 -l 1 /tmp/task2-render/task2-check.pdf /tmp/task2-render/overview
pdftotext /tmp/task2-render/task2-check.pdf - 2>/dev/null | grep -n "How This Works" | head -3
```

Read `/tmp/task2-render/overview-001.png` with the Read tool — confirm the Overview tab shows the title, "About This Report" header, and the 3 paragraph lines above the ranked table, with no Legend content on this page. Then find which page "How This Works" starts on from the `pdftotext` output, render that page the same way (`pdftoppm -png -r 150 -f N -l N ...`), and read it to confirm the Methodology and Legend sections are both present and readable (not clipped by the narrow default column width).

- [ ] **Step 7: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: rename Executive Summary to Overview, add About block, move Legend to new How This Works tab"
```

---

### Task 3: Chart — horizontal bar to vertical column

**Files:**
- Modify: `core/render/stakeholder_workbook.py:225-241` (approximately — the chart-building block inside `_add_executive_summary_sheet`, after Task 2's edits)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- No signature changes. `chart.type` changes from `"bar"` to `"col"`; the `chart.x_axis.scaling.orientation = "maxMin"` line is removed entirely.

- [ ] **Step 1: Write the failing test**

Find `test_generate_workbook_bar_chart_category_axis_is_reversed` in `tests/test_stakeholder_workbook.py` (around line 612) and replace the whole test:
```python
def test_generate_workbook_bar_chart_category_axis_is_reversed(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["Executive Summary"]
    chart = ws._charts[0]
    # Horizontal bar charts plot the first category at the bottom by default,
    # which is backwards from the ranked table listed above the chart (best
    # vendor first/top). Reversing the category axis puts the first-ranked
    # vendor at the top of the chart too.
    assert chart.x_axis.scaling.orientation == "maxMin"
```
Replace with:
```python
def test_generate_workbook_bar_chart_is_a_vertical_column_chart_with_natural_order(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor_a = Vendor(id="a", name="Vendor A", source=VendorSource.DISCOVERED)
    vendor_a.scores.append(ScoreEntry(criterion_id="c1", score=5.0, evidence="e", confidence=Confidence.PAPER))
    vendor_a.scores.append(ScoreEntry(criterion_id="c2", score=5.0, evidence="e", confidence=Confidence.PAPER))
    vendor_b = Vendor(id="b", name="Vendor B", source=VendorSource.DISCOVERED)
    vendor_b.scores.append(ScoreEntry(criterion_id="c1", score=2.0, evidence="e", confidence=Confidence.PAPER))
    vendor_b.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="e", confidence=Confidence.PAPER))

    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor_b, vendor_a],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={
            "a": VendorResearchCache(vendor_id="a"),
            "b": VendorResearchCache(vendor_id="b"),
        },
        out_path=out_path,
    )
    ws = load_workbook(out_path)[_EXEC_SHEET_NAME]
    chart = ws._charts[0]
    # Vertical column charts plot the first category leftmost by default, so
    # feeding ranked_vendors (already best-first) in directly gives the
    # correct order with no axis-orientation override needed.
    assert chart.type == "col"
    assert chart.x_axis.scaling.orientation in (None, "minMax")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_bar_chart_is_a_vertical_column_chart_with_natural_order -v`
Expected: FAIL — `assert 'bar' == 'col'`.

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, find:
```python
        chart = BarChart()
        chart.type = "bar"
        chart.title = "Weighted Avg Score by Vendor"
        chart.x_axis.title = "Vendor"
        chart.y_axis.title = "Weighted Avg Score (0-5)"
        data = Reference(ws, min_col=avg_col, min_row=EXEC_TABLE_HEADER_ROW, max_row=last_row)
        cats = Reference(ws, min_col=1, min_row=EXEC_TABLE_FIRST_DATA_ROW, max_row=last_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        # Horizontal bar charts plot the first category at the bottom by default,
        # backwards from the ranked table above (best vendor listed first/top).
        # x_axis is the category axis in openpyxl's model even for a horizontal
        # "bar" chart type -- reversing it puts the first-ranked vendor on top.
        chart.x_axis.scaling.orientation = "maxMin"
        ws.add_chart(chart, f"A{last_row + 3}")
```
Replace with:
```python
        chart = BarChart()
        chart.type = "col"
        chart.title = "Weighted Avg Score by Vendor"
        chart.x_axis.title = "Vendor"
        chart.y_axis.title = "Weighted Avg Score (0-5)"
        data = Reference(ws, min_col=avg_col, min_row=EXEC_TABLE_HEADER_ROW, max_row=last_row)
        cats = Reference(ws, min_col=1, min_row=EXEC_TABLE_FIRST_DATA_ROW, max_row=last_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        ws.add_chart(chart, f"A{last_row + 3}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_bar_chart_is_a_vertical_column_chart_with_natural_order -v`
Expected: PASS

- [ ] **Step 5: Visually verify with a real render**

```bash
cd /devx/repos/dast-eval
uv run dast-bench stakeholder-review generate --vendor-id invicti --vendor-id veracode --vendor-id nuclei --vendor-id zap --vendor-id stackhawk --out /tmp/task3-check.xlsx
mkdir -p /tmp/task3-render
timeout 120 soffice --headless --convert-to pdf --outdir /tmp/task3-render /tmp/task3-check.xlsx
pdftoppm -png -r 150 -f 1 -l 1 /tmp/task3-render/page.pdf /tmp/task3-render/page 2>/dev/null || pdftoppm -png -r 150 -f 1 -l 1 /tmp/task3-render/task3-check.pdf /tmp/task3-render/page
```

Read `/tmp/task3-render/page-001.png` with the Read tool. Confirm: vertical columns, vendor names along the bottom, Invicti (or whichever vendor ranks first) leftmost, chart title and axis titles are both fully visible with no overlap.

- [ ] **Step 6: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "fix: switch Overview chart from horizontal bar to vertical column"
```

---

### Task 4: 16pt titles everywhere, remove vendor-tab "Provisional" banner

**Files:**
- Modify: `core/render/stakeholder_workbook.py` (`generate_workbook`'s per-vendor loop, `_add_reviewers_sheet`)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- No signature changes.

- [ ] **Step 1: Write the failing tests**

Find `test_generate_workbook_writes_provisional_note_above_header` in `tests/test_stakeholder_workbook.py` (around line 325) and replace the whole test:
```python
def test_generate_workbook_writes_provisional_note_above_header(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    row1 = [c.value for c in ws[1]]
    note = "Provisional — ranking may shift once pending dast-scan results land."
    assert note in row1
```
Replace with:
```python
def test_generate_workbook_writes_vendor_name_title_above_header(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria(name="Vendor One")
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    title_cell = ws.cell(row=1, column=1)
    assert title_cell.value == "Vendor One"
    assert title_cell.font.bold is True
    assert title_cell.font.size == 16
    assert ws.row_dimensions[1].height == 28

    row1_values = [c.value for c in ws[1]]
    assert "Provisional — ranking may shift once pending dast-scan results land." not in row1_values
```

Extend `test_generate_workbook_title_and_header_rows_have_explicit_height` (edited in Task 2) to also cover the Reviewers-tab title bump. Find (this is the same test edited in Task 2 step 2b — add to the end of its body, after the `vendor_ws`/`summary_header_row` assertions already there):
```python
    category_rows, _ = _rollup_row_numbers(taxonomy)
    summary_header_row = min(category_rows.values()) - 1
    assert vendor_ws.row_dimensions[summary_header_row].height == 20
```
Add immediately after it (same test function, same indentation):
```python

    reviewers_ws = wb[_REVIEWERS_SHEET_NAME]
    assert reviewers_ws.row_dimensions[1].height == 28
    assert reviewers_ws.cell(row=1, column=1).font.size == 16
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_writes_vendor_name_title_above_header tests/test_stakeholder_workbook.py::test_generate_workbook_title_and_header_rows_have_explicit_height -v`
Expected: FAIL — the vendor tab still writes the Provisional banner at 11pt with no explicit row-1 height, and the Reviewers tab title is still 14pt/height 26.

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, inside `generate_workbook`'s per-vendor loop, find:
```python
        ws = wb.create_sheet(title=vendor.id[:31])
        ws.sheet_properties.tabColor = _tab_color_for(vendor_index)
        ws.append(["Provisional — ranking may shift once pending dast-scan results land."])
        ws.append([])
```
Replace with:
```python
        ws = wb.create_sheet(title=vendor.id[:31])
        ws.sheet_properties.tabColor = _tab_color_for(vendor_index)
        ws.append([vendor.name])
        ws.cell(row=1, column=1).font = Font(bold=True, size=16)
        ws.row_dimensions[1].height = 28
        ws.append([])
```

In `_add_reviewers_sheet`, find:
```python
    title_cell = ws.cell(row=_REVIEWERS_TITLE_ROW, column=1, value=_REVIEWERS_SHEET_NAME)
    title_cell.font = Font(bold=True, size=14)
    ws.row_dimensions[_REVIEWERS_TITLE_ROW].height = 26
```
Replace with:
```python
    title_cell = ws.cell(row=_REVIEWERS_TITLE_ROW, column=1, value=_REVIEWERS_SHEET_NAME)
    title_cell.font = Font(bold=True, size=16)
    ws.row_dimensions[_REVIEWERS_TITLE_ROW].height = 28
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all pass.

- [ ] **Step 5: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: 16pt vendor-name title on every vendor tab, drop Provisional banner, bump Reviewers title to 16pt"
```

---

### Task 5: Reviewers-tab caveat note

**Files:**
- Modify: `core/render/stakeholder_workbook.py` (`_add_reviewers_sheet`)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- No signature changes. Adds one more row of static text below the existing instructions row on the Reviewers sheet; nothing else on that sheet shifts (the Slot/Name/Role header stays at `_REVIEWERS_HEADER_ROW`, unaffected — the new line is written into a currently-blank row between the instructions and the header, not one that pushes other rows down).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stakeholder_workbook.py`, near `test_generate_workbook_adds_reviewers_sheet_with_editable_name_role_cells`:
```python
def test_generate_workbook_reviewers_sheet_has_no_overwrite_caveat(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)[_REVIEWERS_SHEET_NAME]
    caveat = ws.cell(row=4, column=1).value
    assert caveat is not None
    assert "don't overwrite" in caveat.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_reviewers_sheet_has_no_overwrite_caveat -v`
Expected: FAIL — row 4 is currently blank (the instructions are on row 3, the Slot/Name/Role header is on row 5).

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, inside `_add_reviewers_sheet`, find:
```python
    ws.cell(
        row=_REVIEWERS_INSTRUCTIONS_ROW,
        column=1,
        value="Claim a slot by filling in your name and role below — it appears automatically on every vendor tab.",
    )

    header_labels = ["Slot", "Name", "Role / Title"]
```
Replace with:
```python
    ws.cell(
        row=_REVIEWERS_INSTRUCTIONS_ROW,
        column=1,
        value="Claim a slot by filling in your name and role below — it appears automatically on every vendor tab.",
    )
    ws.cell(
        row=_REVIEWERS_INSTRUCTIONS_ROW + 1,
        column=1,
        value=(
            "Please don't overwrite an existing reviewer's name/role — you may be reassigning someone "
            "else's already-entered scores to yourself."
        ),
    )

    header_labels = ["Slot", "Name", "Role / Title"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_reviewers_sheet_has_no_overwrite_caveat -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all pass — `_REVIEWERS_HEADER_ROW` (5) and `_REVIEWERS_FIRST_DATA_ROW` (6) are unchanged, so nothing that depends on those shifts.

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add don't-overwrite caveat note to Reviewers tab"
```

---

### Task 6: Reviewer placeholder wording

**Files:**
- Modify: `core/render/stakeholder_workbook.py:308-319` (approximately — `_unclaimed_reviewer_label` and `_reviewer_slot_group_header_formula`)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- `_unclaimed_reviewer_label` signature changes from `(slot_number: int) -> str` to `() -> str` (it no longer varies by slot).
- `_reviewer_slot_group_header_formula(slot_index: int, slot_number: int) -> str` keeps its signature (it still needs `slot_number` is unused now, `slot_index` for the row lookup) but calls `_unclaimed_reviewer_label()` with no argument.

- [ ] **Step 1: Write the failing test**

Find `test_generate_workbook_reviewer_slot_header_is_a_formula_referencing_reviewers_sheet` in `tests/test_stakeholder_workbook.py` (around line 147) and replace its assertions:
```python
    slot1_score_col, _, _ = slot_columns[0]
    slot1_cell = ws.cell(row=2, column=slot1_score_col)
    assert slot1_cell.value == (
        '=IF(Reviewers!B6="","Reviewer 1 - {name} - {role/title}",Reviewers!B6&" - "&Reviewers!C6)'
    )
    assert slot1_cell.protection.locked is True

    slot2_score_col, _, _ = slot_columns[1]
    slot2_cell = ws.cell(row=2, column=slot2_score_col)
    assert slot2_cell.value == (
        '=IF(Reviewers!B7="","Reviewer 2 - {name} - {role/title}",Reviewers!B7&" - "&Reviewers!C7)'
    )
```
Replace with:
```python
    slot1_score_col, _, _ = slot_columns[0]
    slot1_cell = ws.cell(row=2, column=slot1_score_col)
    assert slot1_cell.value == (
        '=IF(Reviewers!B6="","Unassigned — see Reviewers tab",Reviewers!B6&" - "&Reviewers!C6)'
    )
    assert slot1_cell.protection.locked is True

    slot2_score_col, _, _ = slot_columns[1]
    slot2_cell = ws.cell(row=2, column=slot2_score_col)
    assert slot2_cell.value == (
        '=IF(Reviewers!B7="","Unassigned — see Reviewers tab",Reviewers!B7&" - "&Reviewers!C7)'
    )
```

Find `test_generate_workbook_adds_merged_reviewer_slot_group_headers` (around line 176) and replace its assertions the same way:
```python
    slot1_cell = ws.cell(row=2, column=slot1_score_col)
    assert slot1_cell.value == (
        '=IF(Reviewers!B6="","Reviewer 1 - {name} - {role/title}",Reviewers!B6&" - "&Reviewers!C6)'
    )
    assert slot1_cell.font.bold is True
    assert slot1_cell.fill.fgColor.rgb == "001F4E78"

    slot2_score_col, _, slot2_rationale_col = slot_columns[1]
    slot2_range = f"{get_column_letter(slot2_score_col)}2:{get_column_letter(slot2_rationale_col)}2"
    assert slot2_range in [str(r) for r in ws.merged_cells.ranges]
    assert ws.cell(row=2, column=slot2_score_col).value == (
        '=IF(Reviewers!B7="","Reviewer 2 - {name} - {role/title}",Reviewers!B7&" - "&Reviewers!C7)'
    )
```
Replace with:
```python
    slot1_cell = ws.cell(row=2, column=slot1_score_col)
    assert slot1_cell.value == (
        '=IF(Reviewers!B6="","Unassigned — see Reviewers tab",Reviewers!B6&" - "&Reviewers!C6)'
    )
    assert slot1_cell.font.bold is True
    assert slot1_cell.fill.fgColor.rgb == "001F4E78"

    slot2_score_col, _, slot2_rationale_col = slot_columns[1]
    slot2_range = f"{get_column_letter(slot2_score_col)}2:{get_column_letter(slot2_rationale_col)}2"
    assert slot2_range in [str(r) for r in ws.merged_cells.ranges]
    assert ws.cell(row=2, column=slot2_score_col).value == (
        '=IF(Reviewers!B7="","Unassigned — see Reviewers tab",Reviewers!B7&" - "&Reviewers!C7)'
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_reviewer_slot_header_is_a_formula_referencing_reviewers_sheet tests/test_stakeholder_workbook.py::test_generate_workbook_adds_merged_reviewer_slot_group_headers -v`
Expected: FAIL — the formula still embeds `"Reviewer 1 - {name} - {role/title}"`.

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, find:
```python
def _unclaimed_reviewer_label(slot_number: int) -> str:
    return f"Reviewer {slot_number} - {{name}} - {{role/title}}"


def _reviewer_slot_group_header_formula(slot_index: int, slot_number: int) -> str:
    """A vendor sheet's reviewer-slot header pulls live from the Reviewers sheet, so
    claiming a slot there propagates to every vendor tab instead of being re-typed per tab."""
    row = _REVIEWERS_FIRST_DATA_ROW + slot_index
    name_ref = f"Reviewers!{get_column_letter(_REVIEWERS_NAME_COL)}{row}"
    role_ref = f"Reviewers!{get_column_letter(_REVIEWERS_ROLE_COL)}{row}"
    placeholder = _unclaimed_reviewer_label(slot_number)
    return f'=IF({name_ref}="","{placeholder}",{name_ref}&" - "&{role_ref})'
```
Replace with:
```python
def _unclaimed_reviewer_label() -> str:
    return "Unassigned — see Reviewers tab"


def _reviewer_slot_group_header_formula(slot_index: int) -> str:
    """A vendor sheet's reviewer-slot header pulls live from the Reviewers sheet, so
    claiming a slot there propagates to every vendor tab instead of being re-typed per tab."""
    row = _REVIEWERS_FIRST_DATA_ROW + slot_index
    name_ref = f"Reviewers!{get_column_letter(_REVIEWERS_NAME_COL)}{row}"
    role_ref = f"Reviewers!{get_column_letter(_REVIEWERS_ROLE_COL)}{row}"
    placeholder = _unclaimed_reviewer_label()
    return f'=IF({name_ref}="","{placeholder}",{name_ref}&" - "&{role_ref})'
```

Now find the call site in `_write_reviewer_slot_group_headers`:
```python
def _write_reviewer_slot_group_headers(ws, reviewer_slots: int) -> None:
    for slot_index, (score_col, _dispute_col, rationale_col) in enumerate(_reviewer_slot_columns(reviewer_slots)):
        ws.merge_cells(start_row=2, start_column=score_col, end_row=2, end_column=rationale_col)
        anchor = ws.cell(
            row=2, column=score_col,
            value=_reviewer_slot_group_header_formula(slot_index, slot_index + 1),
        )
```
Replace with:
```python
def _write_reviewer_slot_group_headers(ws, reviewer_slots: int) -> None:
    for slot_index, (score_col, _dispute_col, rationale_col) in enumerate(_reviewer_slot_columns(reviewer_slots)):
        ws.merge_cells(start_row=2, start_column=score_col, end_row=2, end_column=rationale_col)
        anchor = ws.cell(
            row=2, column=score_col,
            value=_reviewer_slot_group_header_formula(slot_index),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all pass.

- [ ] **Step 5: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all pass — `_unclaimed_reviewer_label` isn't imported anywhere outside this file (round 4 already removed `core/stakeholder_review.py`'s dependency on it).

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: change reviewer placeholder wording to 'Unassigned — see Reviewers tab'"
```

---

### Task 7: Evidence-cell hyperlinks

**Files:**
- Modify: `core/render/stakeholder_workbook.py` (imports, one new helper function, one call site in `generate_workbook`'s per-criterion-row loop)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Produces: `_linkify_evidence(text: str) -> tuple[str, CellRichText] | tuple[None, None]`.
- Consumes: `_DOMAIN_TOKEN` (existing compiled regex in `core/render/markdown.py`, already used by that module's own markdown-link rendering — unchanged, just imported here too).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stakeholder_workbook.py`, anywhere after the imports (e.g. right before the first `def test_` in the file, or at the end — placement doesn't matter, it's a standalone test):
```python
def test_generate_workbook_links_first_url_in_evidence(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = Vendor(id="v1", name="V1", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(
        criterion_id="c1", score=4.0,
        evidence="See docs.example.com/report for details.", confidence=Confidence.PAPER,
    ))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="no link here", confidence=Confidence.PAPER))

    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    evidence_col = header.index("Automated Evidence") + 1

    linked_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    unlinked_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")

    linked_cell = ws.cell(row=linked_row, column=evidence_col)
    assert linked_cell.hyperlink.target == "https://docs.example.com/report"
    # Plain (non rich-text-aware) reads still see the full original evidence text.
    assert linked_cell.value == "See docs.example.com/report for details."

    assert ws.cell(row=unlinked_row, column=evidence_col).hyperlink is None

    ws_rich = load_workbook(out_path, rich_text=True)["v1"]
    linked_cell_rich = ws_rich.cell(row=linked_row, column=evidence_col)
    link_block = next(b for b in linked_cell_rich.value if not isinstance(b, str))
    assert link_block.text == "docs.example.com/report"
    assert link_block.font.color.rgb == "000563C1"
    plain_blocks = [b for b in linked_cell_rich.value if isinstance(b, str)]
    assert "See " in plain_blocks and " for details." in plain_blocks
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_links_first_url_in_evidence -v`
Expected: FAIL — `linked_cell.hyperlink` is `None` (no hyperlink code exists yet).

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, find the import block:
```python
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ..models import CriteriaTaxonomy, Vendor, VendorResearchCache
from .markdown import _ordered_categories
```
Replace with:
```python
from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ..models import CriteriaTaxonomy, Vendor, VendorResearchCache
from .markdown import _DOMAIN_TOKEN, _ordered_categories
```

Add a module-level constant near the other fill/font constants (find `_UNFILLED_FILL = PatternFill(...)` and add after it):
```python
_UNFILLED_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")

_EVIDENCE_LINK_INLINE_FONT = InlineFont(color="0563C1", u="single")
```

Add the `_linkify_evidence` function. Place it near `_is_wrapped_text` (find `def _is_wrapped_text(header_name: str) -> bool:` and its body, then insert this function right after it):
```python
def _linkify_evidence(text: str) -> tuple[str, CellRichText] | tuple[None, None]:
    """Find the first URL-looking token in evidence text and return its target plus a rich-text
    value that styles only that substring as a link, leaving the rest of the text plain."""
    match = _DOMAIN_TOKEN.search(text)
    if not match:
        return None, None
    token = match.group(1)
    stripped = token.rstrip(".,;:)")
    start = match.start(1)
    link_end = start + len(stripped)
    before, link_text, after = text[:start], text[start:link_end], text[link_end:]
    blocks: list = [before] if before else []
    blocks.append(TextBlock(_EVIDENCE_LINK_INLINE_FONT, link_text))
    if after:
        blocks.append(after)
    return f"https://{stripped}", CellRichText(blocks)
```

Wire it into `generate_workbook`'s per-criterion-row loop. Find:
```python
            for col_idx, header_name in enumerate(headers, start=1):
                if header_name in _HIDDEN_HEADERS:
                    continue
                cell = ws.cell(row=row_num, column=col_idx)
                if _is_right_aligned_numeric(header_name):
                    cell.number_format = "0.0"
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.alignment = Alignment(horizontal="left", wrap_text=_is_wrapped_text(header_name))

            for col in score_cols:
```
Replace with:
```python
            for col_idx, header_name in enumerate(headers, start=1):
                if header_name in _HIDDEN_HEADERS:
                    continue
                cell = ws.cell(row=row_num, column=col_idx)
                if _is_right_aligned_numeric(header_name):
                    cell.number_format = "0.0"
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.alignment = Alignment(horizontal="left", wrap_text=_is_wrapped_text(header_name))

            if not is_pending and entry and entry.evidence:
                url, rich_text = _linkify_evidence(entry.evidence)
                if url:
                    evidence_cell = ws.cell(row=row_num, column=_column_index(headers, "Automated Evidence"))
                    evidence_cell.value = rich_text
                    evidence_cell.hyperlink = url

            for col in score_cols:
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_links_first_url_in_evidence -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all pass — no existing test asserts the literal type of the Evidence cell's `.value` for a criterion whose evidence text happens to contain a domain-like token, so this shouldn't break anything already passing (existing evidence fixtures in other tests use plain text like `"e"`, `"ev1"`, `"ev2"` with no domain-like substrings, so `_linkify_evidence` returns `(None, None)` for those and the cell is left as a plain string exactly as before).

- [ ] **Step 6: Final end-to-end visual check**

```bash
cd /devx/repos/dast-eval
uv run dast-bench stakeholder-review generate --vendor-id invicti --vendor-id veracode --vendor-id nuclei --vendor-id zap --vendor-id stackhawk --reviewer-slots 7 --out reports/stakeholder-review-all.xlsx
mkdir -p /tmp/task7-render
timeout 120 soffice --headless --convert-to pdf --outdir /tmp/task7-render reports/stakeholder-review-all.xlsx
pdftoppm -png -r 150 -f 1 -l 3 /tmp/task7-render/final.pdf /tmp/task7-render/page
```

Read `/tmp/task7-render/page-001.png` (Overview — chart + About block), `page-002.png` (Reviewers — caveat note present), and `page-003.png` (first vendor tab — 16pt vendor-name title, no Provisional banner, hyperlinked evidence where present) with the Read tool. Confirm everything from Tasks 1-7 together looks right, with no new visual issues.

- [ ] **Step 7: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: hyperlink the first URL in Automated Evidence cells"
```
