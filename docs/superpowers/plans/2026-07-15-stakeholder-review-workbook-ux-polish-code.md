# Stakeholder Review Workbook — UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the generated stakeholder-review workbook look and feel
professional (per
`docs/superpowers/specs/2026-07-15-stakeholder-review-workbook-ux-polish-design.md`):
styled vendor sheets, a fixed `Dispute?` case-sensitivity bug, and a new
"Executive Summary" comparison tab with a native chart.

**Architecture:** All changes land in the existing two modules —
`core/render/stakeholder_workbook.py` (styling constants/helpers,
`generate_workbook`'s per-vendor loop, and a new
`_add_executive_summary_sheet` function) and `core/stakeholder_review.py`
(the `Dispute?` case-insensitivity fix in `merge`/`validate_workbook`).
No new files, no new CLI surface — `dast-bench stakeholder-review
generate` produces the improved output automatically.

**Tech Stack:** Python, `openpyxl` (styles, data validation, charts),
`pytest`. No new dependencies.

## Global Constraints

- Excel-only target — no Google Sheets/LibreOffice rendering fallback
  needed for the new chart or cross-sheet formulas.
- No new Pydantic models, no new YAML storage, no CLI flag changes.
- No macros/add-ins — chart and formulas only, consistent with the base
  spec's existing constraint.
- `openpyxl` color/RGB values round-trip with a leading `00` alpha byte
  when read back after `load_workbook` (e.g. writing `"1F4E78"` reads
  back as `"001F4E78"`) — every test asserting a color must account for
  this.
- Every new/modified test that asserts a specific cell's row number for
  the rollup block must derive it from `FIRST_DATA_ROW` and
  `_rollup_row_numbers`/`EXEC_TABLE_HEADER_ROW`/`EXEC_TABLE_FIRST_DATA_ROW`
  rather than a hand-computed magic number, since these are exact,
  already-defined quantities and hand-computing them independently is
  where a plan (or a test) would silently drift from the implementation.

---

## File Structure

- Modify: `core/render/stakeholder_workbook.py` — add styling constants
  (column widths, header/band/border styles, tab-color palette), the
  `Dispute?` dropdown, the `_rollup_row_numbers` helper, and the new
  `_add_executive_summary_sheet` function (legend + ranked comparison
  table + chart), wired into `generate_workbook`.
- Modify: `core/stakeholder_review.py` — case-insensitive `Dispute?`
  matching in `merge` and `validate_workbook` via a new `_is_dispute_yes`
  helper.
- Test: `tests/test_stakeholder_workbook.py` (existing file, extended)
- Test: `tests/test_stakeholder_review.py` (existing file, extended)

---

### Task 1: Vendor sheet layout — column widths, freeze panes, header styling

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: existing `generate_workbook`, `_all_headers`, `_column_index`,
  `HEADER_ROW`, `FIRST_DATA_ROW` (all already in the file).
- Produces: `_column_width_for(header: str) -> float | None`, used again
  unmodified by later tasks — no other task needs to touch it.

- [ ] **Step 1: Write the failing test**

Add this import at the top of `tests/test_stakeholder_workbook.py`,
replacing the existing line 15:

```python
from openpyxl.utils import get_column_letter

from core.render.stakeholder_workbook import compute_priority_order, generate_workbook
```

Then append to the file:

```python
def test_generate_workbook_applies_column_widths_freeze_panes_and_header_style(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    assert ws.freeze_panes == "C4"
    assert ws.column_dimensions["A"].width == 32  # Criterion

    header = [c.value for c in ws[3]]
    evidence_letter = get_column_letter(header.index("Automated Evidence") + 1)
    assert ws.column_dimensions[evidence_letter].width == 45

    header_cell = ws.cell(row=3, column=1)
    assert header_cell.font.bold is True
    assert header_cell.font.color.rgb == "00FFFFFF"
    assert header_cell.fill.fgColor.rgb == "001F4E78"
    assert header_cell.alignment.wrap_text is True
    assert header_cell.border.top.style == "thin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k column_widths_freeze_panes -v`
Expected: FAIL — `assert None == "C4"` (freeze_panes not set)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, replace the imports block
(current lines 1–12) with:

```python
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ..models import CriteriaTaxonomy, Vendor, VendorResearchCache
from .markdown import _ordered_categories
```

Add these constants right after the existing `_TIER_FILL`/`_UNFILLED_FILL`
definitions (current lines 30–31):

```python
_HEADER_FILL_COLOR = "1F4E78"
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color=_HEADER_FILL_COLOR, end_color=_HEADER_FILL_COLOR, fill_type="solid")
_HEADER_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

_FIXED_COLUMN_WIDTHS = {
    "Criterion": 32,
    "Category": 16,
    "Weight": 10,
    "Automated Score": 14,
    "Automated Evidence": 45,
    "Automated Confidence": 16,
    "Resolved Score": 14,
    "Resolved By": 16,
    "Resolved Timestamp": 18,
    "Automated vs. Resolved Delta": 14,
}
_COLUMN_WIDTHS_BY_SUFFIX = [
    (" Rationale", 40),
    (" Dispute?", 12),
    (" Score", 12),
]


def _column_width_for(header: str) -> float | None:
    if header in _FIXED_COLUMN_WIDTHS:
        return _FIXED_COLUMN_WIDTHS[header]
    for suffix, width in _COLUMN_WIDTHS_BY_SUFFIX:
        if header.endswith(suffix):
            return width
    return None
```

Then, inside `generate_workbook`, immediately after `ws.append(headers)`
(the line right before `pending_for_vendor = pending_criteria.get(...)`),
insert:

```python
        ws.freeze_panes = "C4"
        for col_idx, header_name in enumerate(headers, start=1):
            width = _column_width_for(header_name)
            if width is not None:
                ws.column_dimensions[get_column_letter(col_idx)].width = width
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=HEADER_ROW, column=col_idx)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.border = _HEADER_BORDER
            cell.alignment = _HEADER_ALIGNMENT
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS (existing tests unaffected, new one passes)

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: style vendor sheet headers, column widths, and freeze panes"
```

---

### Task 2: Vendor sheet data formatting — number formats, row banding, rollup border, tab color

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: Task 1's imports/constants (`Alignment`, `Border`, `Side`,
  `PatternFill`, `HEADER_ROW`).
- Produces: `_TAB_COLOR_PALETTE: list[str]` and `_tab_color_for(index:
  int) -> str` — used again unmodified by no later task (styling is
  self-contained), but the constant is imported directly by this task's
  test.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stakeholder_workbook.py`:

```python
def test_generate_workbook_applies_number_formats_banding_border_and_tab_color(tmp_path):
    from core.render.stakeholder_workbook import FIRST_DATA_ROW, _TAB_COLOR_PALETTE

    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
        top_tier_count=0,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    score_col = header.index("Automated Score") + 1
    crit_col = header.index("Criterion") + 1

    assert ws.cell(row=4, column=score_col).number_format == "0.0"
    assert ws.cell(row=4, column=score_col).alignment.horizontal == "right"
    assert ws.cell(row=4, column=crit_col).alignment.horizontal == "left"

    row4_fill = ws.cell(row=4, column=crit_col).fill.fgColor.rgb
    row5_fill = ws.cell(row=5, column=crit_col).fill.fgColor.rgb
    assert row5_fill == "00F2F2F2"
    assert row4_fill != row5_fill

    last_data_row = FIRST_DATA_ROW + len(taxonomy.criteria) - 1
    first_rollup_row = last_data_row + 2
    assert ws.cell(row=first_rollup_row, column=1).border.top.style == "medium"

    assert ws.sheet_properties.tabColor.rgb == "00" + _TAB_COLOR_PALETTE[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k number_formats_banding -v`
Expected: FAIL — `assert '0.0' == 'General'` (no number format applied yet)

- [ ] **Step 3: Write minimal implementation**

Add these constants after the `_FIXED_COLUMN_WIDTHS`/`_COLUMN_WIDTHS_BY_SUFFIX`
block from Task 1:

```python
_BAND_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
_ROLLUP_BORDER = Border(top=Side(style="medium"))

_RIGHT_ALIGN_NUMERIC_HEADERS_EXACT = {"Weight", "Automated vs. Resolved Delta"}
_RIGHT_ALIGN_NUMERIC_HEADERS_SUFFIX = " Score"

_TAB_COLOR_PALETTE = ["2E86AB", "A23B72", "F18F01", "C73E1D", "3B1F2B", "6A994E"]


def _tab_color_for(index: int) -> str:
    return _TAB_COLOR_PALETTE[index % len(_TAB_COLOR_PALETTE)]


def _is_right_aligned_numeric(header_name: str) -> bool:
    return (
        header_name in _RIGHT_ALIGN_NUMERIC_HEADERS_EXACT
        or header_name.endswith(_RIGHT_ALIGN_NUMERIC_HEADERS_SUFFIX)
    )
```

Change `for vendor in vendors:` to `for vendor_index, vendor in
enumerate(vendors):` and, right after `ws = wb.create_sheet(title=vendor.id[:31])`,
add:

```python
        ws.sheet_properties.tabColor = _tab_color_for(vendor_index)
```

In the per-criterion loop, replace the tier-fill block:

```python
            if i < top_tier_count:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _TIER_FILL
```

with:

```python
            if i < top_tier_count:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _TIER_FILL
            elif i % 2 == 1:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _BAND_FILL

            for col_idx, header_name in enumerate(headers, start=1):
                if header_name in _HIDDEN_HEADERS:
                    continue
                cell = ws.cell(row=row_num, column=col_idx)
                if _is_right_aligned_numeric(header_name):
                    cell.number_format = "0.0"
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.alignment = Alignment(horizontal="left")
```

Finally, replace the rollup-block section:

```python
        ws.append([])
        for category in _ordered_categories(taxonomy):
            _write_rollup_row(category, category)
        _write_rollup_row("Weighted Total", None)
```

with:

```python
        ws.append([])
        first_rollup_row = ws.max_row + 1
        for category in _ordered_categories(taxonomy):
            _write_rollup_row(category, category)
        _write_rollup_row("Weighted Total", None)
        for col in range(1, len(headers) + 1):
            ws.cell(row=first_rollup_row, column=col).border = _ROLLUP_BORDER
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add number formatting, row banding, rollup border, and tab colors"
```

---

### Task 3: `Dispute?` case-insensitivity fix + dropdown validation

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Modify: `core/stakeholder_review.py`
- Test: `tests/test_stakeholder_workbook.py`
- Test: `tests/test_stakeholder_review.py`

**Interfaces:**
- Produces: `_is_dispute_yes(value) -> bool` in
  `core/stakeholder_review.py` — a private helper used only within that
  module (`merge` and `validate_workbook`); no other task depends on it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_stakeholder_workbook.py`:

```python
def test_generate_workbook_adds_dispute_dropdown(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    dispute_col_letter = get_column_letter(header.index("DAST SME Dispute?") + 1)
    dispute_dvs = [dv for dv in ws.data_validations.dataValidation if dv.formula1 == '"Yes"']
    assert len(dispute_dvs) == 1
    assert f"{dispute_col_letter}4" in str(dispute_dvs[0].sqref)
```

Append to `tests/test_stakeholder_review.py` (it already imports `merge`,
`_column_map`, `_row_for`, `_generate_two_stakeholders`, `validate_workbook`
from earlier tasks in the base plan):

```python
def test_merge_accepts_case_insensitive_dispute_yes_value(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{cols['Jane Doe (DAST SME) Dispute?']}{row}"] = "yes"
    copy_ws[f"{cols['Jane Doe (DAST SME) Rationale']}{row}"] = "Confirmed with vendor demo"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "merged 1 cell" in summary

    master_ws = load_workbook(master_path)["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    assert master_ws[f"{mcols['Jane Doe (DAST SME) Dispute?']}{mrow}"].value == "yes"


def test_merge_flags_mixed_case_dispute_without_rationale_as_invalid(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row2 = _row_for(copy_ws, cols, "c2")
    copy_ws[f"{cols['Jane Doe (DAST SME) Dispute?']}{row2}"] = "Yes"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "1 invalid" in summary


def test_validate_workbook_flags_lowercase_dispute_without_rationale(tmp_path):
    file_path = _generate_two_stakeholders(tmp_path, "review.xlsx")
    wb = load_workbook(file_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c1")
    ws[f"{cols['Jane Doe (DAST SME) Dispute?']}{row}"] = "yes"
    wb.save(file_path)

    issues = validate_workbook(file_path)
    assert len(issues) == 1
    assert "disputed with no rationale" in issues[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k dispute_dropdown -v`
Expected: FAIL — `assert 0 == 1` (no dropdown with formula `"Yes"` exists yet)

Run: `uv run pytest tests/test_stakeholder_review.py -k dispute -v`
Expected: FAIL — `test_merge_accepts_case_insensitive_dispute_yes_value` fails
because `"yes"` (lowercase) doesn't satisfy the current exact `!= "Y"`
check, so the cell is treated as invalid instead of merged.

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, inside `generate_workbook`,
find the existing `dv = DataValidation(...)` / `ws.add_data_validation(dv)`
block (right after `score_cols = [...]`) and add immediately after it:

```python
        dispute_cols = [
            _column_index(headers, h) for h in stakeholder_headers(stakeholders) if h.endswith(" Dispute?")
        ]
        dispute_dv = DataValidation(type="list", formula1='"Yes"', allow_blank=True)
        ws.add_data_validation(dispute_dv)
```

Then, in the per-criterion loop, right after the existing:

```python
            for col in score_cols:
                cell = ws.cell(row=row_num, column=col)
                cell.protection = Protection(locked=is_pending)
                dv.add(cell)
                if i < top_tier_count:
                    ws.conditional_formatting.add(
                        cell.coordinate,
                        CellIsRule(operator="equal", formula=['""'], fill=_UNFILLED_FILL),
                    )
```

add:

```python
            for col in dispute_cols:
                dispute_dv.add(ws.cell(row=row_num, column=col))
```

In `core/stakeholder_review.py`, add this helper right after the imports
(before `_column_map`):

```python
_DISPUTE_YES_VALUES = {"y", "yes"}


def _is_dispute_yes(value) -> bool:
    return isinstance(value, str) and value.strip().lower() in _DISPUTE_YES_VALUES
```

Then replace, in `merge` (current line 122):

```python
                valid = (f_score is None or f_score in SCORE_VALUES) and (f_dispute != "Y" or bool(f_rationale))
```

with:

```python
                valid = (f_score is None or f_score in SCORE_VALUES) and (
                    not _is_dispute_yes(f_dispute) or bool(f_rationale)
                )
```

And replace, in `validate_workbook` (current line 164):

```python
                if dispute == "Y" and not rationale:
```

with:

```python
                if _is_dispute_yes(dispute) and not rationale:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stakeholder_workbook.py tests/test_stakeholder_review.py -v`
Expected: all tests PASS, including the pre-existing tests that use
exact `"Y"` (still accepted — the check is now a strict superset)

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py core/stakeholder_review.py tests/test_stakeholder_workbook.py tests/test_stakeholder_review.py
git commit -m "fix: accept case-insensitive Dispute? values and add dropdown validation"
```

---

### Task 4: Executive Summary tab — legend + ranked comparison table

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `_HEADER_FONT`, `_HEADER_FILL`, `_HEADER_BORDER` (Task 1);
  `_ordered_categories` (already imported); `_all_headers`,
  `_column_index` (existing).
- Produces: `_rollup_row_numbers(taxonomy: CriteriaTaxonomy) -> tuple[dict[str, int], int]`
  (category name → its rollup row number, and the `Weighted Total` row
  number — identical across every vendor sheet in one `generate_workbook`
  call, since all vendor sheets share the same taxonomy and therefore the
  same row count) and `EXEC_TABLE_HEADER_ROW: int`,
  `EXEC_TABLE_FIRST_DATA_ROW: int` module constants. Task 5 (the chart)
  extends the same `_add_executive_summary_sheet` function and reuses
  `EXEC_TABLE_HEADER_ROW`/`EXEC_TABLE_FIRST_DATA_ROW`.

- [ ] **Step 1: Write the failing tests**

Add these imports to the top of `tests/test_stakeholder_workbook.py`,
replacing the current import line:

```python
from core.render.stakeholder_workbook import (
    _all_headers,
    _column_index,
    _rollup_row_numbers,
    compute_priority_order,
    EXEC_TABLE_FIRST_DATA_ROW,
    EXEC_TABLE_HEADER_ROW,
    generate_workbook,
)
```

Append to the file:

```python
def test_generate_workbook_adds_executive_summary_sheet_first_with_legend_and_ranked_table(tmp_path):
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
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={
            "a": VendorResearchCache(vendor_id="a"),
            "b": VendorResearchCache(vendor_id="b"),
        },
        out_path=out_path,
    )

    wb = load_workbook(out_path)
    assert wb.sheetnames[0] == "Executive Summary"
    ws = wb["Executive Summary"]
    assert ws.cell(row=1, column=1).value == "Executive Summary"
    assert ws.cell(row=3, column=1).value == "Legend"
    assert "top 10 priority" in ws.cell(row=5, column=1).value

    header = [c.value for c in ws[EXEC_TABLE_HEADER_ROW]]
    assert header == ["Vendor", "Coverage", "DX", "Weighted Avg Score", "Total Achieved / Available"]

    # Vendor A scored higher on every criterion, so it ranks first
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1).value == "Vendor A"
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW + 1, column=1).value == "Vendor B"

    category_rows, weighted_total_row = _rollup_row_numbers(taxonomy)
    vendor_headers = _all_headers([(None, "DAST SME")])
    weight_col = get_column_letter(_column_index(vendor_headers, "Weight"))
    evidence_col = get_column_letter(_column_index(vendor_headers, "Automated Evidence"))
    score_col = get_column_letter(_column_index(vendor_headers, "Automated Score"))

    coverage_row = category_rows["Coverage"]
    expected_coverage_formula = (
        f"=IF('a'!{evidence_col}{coverage_row}=0,\"Pending\","
        f"'a'!{weight_col}{coverage_row}/'a'!{evidence_col}{coverage_row}*5)"
    )
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=2).value == expected_coverage_formula
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=5).value == f"='a'!{score_col}{weighted_total_row}"


def test_generate_workbook_executive_summary_sorts_all_pending_vendor_last(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor_a = Vendor(id="a", name="Vendor A", source=VendorSource.DISCOVERED)
    vendor_a.scores.append(ScoreEntry(criterion_id="c1", score=1.0, evidence="e", confidence=Confidence.PAPER))
    vendor_a.scores.append(ScoreEntry(criterion_id="c2", score=1.0, evidence="e", confidence=Confidence.PAPER))
    vendor_b = Vendor(id="b", name="Vendor B", source=VendorSource.DISCOVERED)
    vendor_b.scores.append(ScoreEntry(criterion_id="c1", score=5.0, evidence="e", confidence=Confidence.PAPER))
    vendor_b.scores.append(ScoreEntry(criterion_id="c2", score=5.0, evidence="e", confidence=Confidence.PAPER))

    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor_a, vendor_b],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={"b": {"c1", "c2"}},
        research_caches={
            "a": VendorResearchCache(vendor_id="a"),
            "b": VendorResearchCache(vendor_id="b"),
        },
        out_path=out_path,
    )

    ws = load_workbook(out_path)["Executive Summary"]
    # Vendor B has nothing scored yet (fully pending), so it must not
    # outrank Vendor A's real (if low) score.
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1).value == "Vendor A"
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW + 1, column=1).value == "Vendor B"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k executive_summary -v`
Expected: FAIL — `ImportError: cannot import name 'EXEC_TABLE_HEADER_ROW'`

- [ ] **Step 3: Write minimal implementation**

Add these constants and functions to `core/render/stakeholder_workbook.py`,
after the `_TAB_COLOR_PALETTE`/`_tab_color_for` block from Task 2:

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
]

EXEC_TABLE_HEADER_ROW = _EXEC_LEGEND_FIRST_ROW + len(_EXEC_LEGEND_LINES_TEMPLATE) + 1
EXEC_TABLE_FIRST_DATA_ROW = EXEC_TABLE_HEADER_ROW + 1


def _rollup_row_numbers(taxonomy: CriteriaTaxonomy) -> tuple[dict[str, int], int]:
    last_data_row = FIRST_DATA_ROW + len(taxonomy.criteria) - 1
    categories = _ordered_categories(taxonomy)
    first_category_row = last_data_row + 2
    category_rows = {category: first_category_row + i for i, category in enumerate(categories)}
    weighted_total_row = first_category_row + len(categories)
    return category_rows, weighted_total_row


def _weighted_avg_score(taxonomy: CriteriaTaxonomy, vendor: Vendor, pending_for_vendor: set[str]) -> float | None:
    achieved = 0.0
    available = 0.0
    for criterion in taxonomy.criteria:
        if criterion.id in pending_for_vendor:
            continue
        entry = vendor.score_for(criterion.id)
        score = entry.score if entry else 0.0
        achieved += criterion.weight * score
        available += criterion.weight
    if available == 0:
        return None
    return achieved / available


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

    legend_header_cell = ws.cell(row=_EXEC_LEGEND_HEADER_ROW, column=1, value="Legend")
    legend_header_cell.font = Font(bold=True)
    for i, line in enumerate(_EXEC_LEGEND_LINES_TEMPLATE):
        ws.cell(row=_EXEC_LEGEND_FIRST_ROW + i, column=1, value=line.format(top_tier_count=top_tier_count))

    categories = _ordered_categories(taxonomy)
    category_rows, weighted_total_row = _rollup_row_numbers(taxonomy)
    table_headers = ["Vendor"] + categories + ["Weighted Avg Score", "Total Achieved / Available"]
    avg_col = 2 + len(categories)

    for col_idx, header_name in enumerate(table_headers, start=1):
        cell = ws.cell(row=EXEC_TABLE_HEADER_ROW, column=col_idx, value=header_name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _HEADER_BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    weight_col_letter = get_column_letter(_column_index(headers, "Weight"))
    evidence_col_letter = get_column_letter(_column_index(headers, "Automated Evidence"))
    score_col_letter = get_column_letter(_column_index(headers, "Automated Score"))

    def _sort_key(vendor: Vendor) -> tuple[bool, float]:
        avg = _weighted_avg_score(taxonomy, vendor, pending_criteria.get(vendor.id, set()))
        return (avg is None, -(avg or 0.0))

    ranked_vendors = sorted(vendors, key=_sort_key)

    for i, vendor in enumerate(ranked_vendors):
        row_num = EXEC_TABLE_FIRST_DATA_ROW + i
        sheet_name = vendor.id[:31]
        ws.cell(row=row_num, column=1, value=vendor.name)

        for col_offset, category in enumerate(categories):
            r = category_rows[category]
            formula = (
                f"=IF('{sheet_name}'!{evidence_col_letter}{r}=0,\"Pending\","
                f"'{sheet_name}'!{weight_col_letter}{r}/'{sheet_name}'!{evidence_col_letter}{r}*5)"
            )
            cell = ws.cell(row=row_num, column=2 + col_offset, value=formula)
            cell.number_format = "0.0"
            cell.alignment = Alignment(horizontal="right")

        avg_formula = (
            f"=IF('{sheet_name}'!{evidence_col_letter}{weighted_total_row}=0,\"Pending\","
            f"'{sheet_name}'!{weight_col_letter}{weighted_total_row}/"
            f"'{sheet_name}'!{evidence_col_letter}{weighted_total_row}*5)"
        )
        avg_cell = ws.cell(row=row_num, column=avg_col, value=avg_formula)
        avg_cell.number_format = "0.0"
        avg_cell.alignment = Alignment(horizontal="right")

        ws.cell(
            row=row_num,
            column=avg_col + 1,
            value=f"='{sheet_name}'!{score_col_letter}{weighted_total_row}",
        )

    for col_idx, header_name in enumerate(table_headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 40 if header_name == "Vendor" else 20

    ws.protection.sheet = True
```

Now wire it in. In `generate_workbook`, replace:

```python
    wb = Workbook()
    wb.remove(wb.active)
    headers = _all_headers(stakeholders)
    for vendor_index, vendor in enumerate(vendors):
```

with:

```python
    wb = Workbook()
    wb.remove(wb.active)
    headers = _all_headers(stakeholders)
    _add_executive_summary_sheet(wb, taxonomy, vendors, pending_criteria, headers, top_tier_count)
    for vendor_index, vendor in enumerate(vendors):
```

Finally, refactor the per-vendor rollup border computation (from Task 2)
to reuse `_rollup_row_numbers` instead of computing `first_rollup_row`
independently — this guarantees the per-vendor sheet's rollup rows and
the Executive Summary's formula references can never drift apart. Replace:

```python
        ws.append([])
        first_rollup_row = ws.max_row + 1
        for category in _ordered_categories(taxonomy):
            _write_rollup_row(category, category)
        _write_rollup_row("Weighted Total", None)
        for col in range(1, len(headers) + 1):
            ws.cell(row=first_rollup_row, column=col).border = _ROLLUP_BORDER
```

with:

```python
        ws.append([])
        category_rows_for_border, _ = _rollup_row_numbers(taxonomy)
        first_rollup_row = category_rows_for_border[_ordered_categories(taxonomy)[0]]
        for category in _ordered_categories(taxonomy):
            _write_rollup_row(category, category)
        _write_rollup_row("Weighted Total", None)
        for col in range(1, len(headers) + 1):
            ws.cell(row=first_rollup_row, column=col).border = _ROLLUP_BORDER
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions (in particular, `tests/test_cli_stakeholder_review.py`
and `tests/test_stakeholder_review.py`, which don't touch the Executive
Summary sheet directly but do call `generate_workbook`)

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add Executive Summary tab with legend and ranked vendor comparison"
```

---

### Task 5: Executive Summary bar chart

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `_add_executive_summary_sheet` (Task 4) — extends its body
  only, no signature change.
- Produces: nothing new consumed elsewhere — this is the final task.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stakeholder_workbook.py`:

```python
def test_generate_workbook_executive_summary_includes_bar_chart(tmp_path):
    from openpyxl.chart import BarChart

    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["Executive Summary"]
    assert len(ws._charts) == 1
    assert isinstance(ws._charts[0], BarChart)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k bar_chart -v`
Expected: FAIL — `assert 0 == 1` (no chart added yet)

- [ ] **Step 3: Write minimal implementation**

Add this import to the top of `core/render/stakeholder_workbook.py`,
alongside the other `openpyxl` imports:

```python
from openpyxl.chart import BarChart, Reference
```

In `_add_executive_summary_sheet`, at the very end of the function (after
the `ws.protection.sheet = True` line), add:

```python
    if ranked_vendors:
        last_row = EXEC_TABLE_FIRST_DATA_ROW + len(ranked_vendors) - 1
        chart = BarChart()
        chart.type = "bar"
        chart.title = "Weighted Avg Score by Vendor"
        chart.x_axis.title = "Weighted Avg Score (0-5)"
        chart.y_axis.title = "Vendor"
        data = Reference(ws, min_col=avg_col, min_row=EXEC_TABLE_HEADER_ROW, max_row=last_row)
        cats = Reference(ws, min_col=1, min_row=EXEC_TABLE_FIRST_DATA_ROW, max_row=last_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        ws.add_chart(chart, f"A{last_row + 3}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add native bar chart to Executive Summary tab"
```
