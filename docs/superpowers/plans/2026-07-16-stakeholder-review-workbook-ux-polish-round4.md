# Stakeholder Review Workbook UX Polish Round 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reversed chart bar order, fix clipped title/header rows, confirm >5 reviewer slots already works, and add a shared Reviewers sheet so a reviewer's name/role is claimed once and applied to every vendor tab.

**Architecture:** All changes live in `core/render/stakeholder_workbook.py` (workbook generation) and `core/stakeholder_review.py` (post-generation validation). No new files. The Reviewers sheet is a new tab created alongside the existing Executive Summary tab; each vendor tab's reviewer-slot header becomes a formula referencing it instead of free-typed text.

**Tech Stack:** Python, openpyxl, pytest.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-07-16-stakeholder-review-workbook-ux-polish-round4-design.md` — read it before starting if anything below is unclear.
- No reviewer-overwrite protection mechanism (explicitly declined — see design doc). Do not add a `lock-reviewers` command or extend `merge()` for the Reviewers sheet.
- Don't touch chart color/legend/resize, hyperlinks, auto-pending, tier-highlight styling, tab renaming, or any other item from earlier UX-polish rounds — those are out of scope for this round.
- After Task 4, regenerate the real workbook via `uv run dast-bench stakeholder-review generate` and render it with `soffice --headless --convert-to pdf` (already installed in this container) + `pdftoppm` to a PNG, and visually inspect it (via the Read tool) before considering the plan done. This is a manual step, not a pytest assertion.

---

### Task 1: Fix chart bar order

**Files:**
- Modify: `core/render/stakeholder_workbook.py:230-233` (inside `_add_executive_summary_sheet`)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- No new functions. Adds one line to the existing chart-building block.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stakeholder_workbook.py`, after `test_generate_workbook_executive_summary_includes_bar_chart` (currently ends at line 496):

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

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_bar_chart_category_axis_is_reversed -v`
Expected: FAIL — `assert None == "maxMin"` (or similar; `chart.x_axis.scaling.orientation` defaults to `"minMax"` when unset).

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, find:

```python
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        ws.add_chart(chart, f"A{last_row + 3}")
```

Replace with:

```python
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        # Horizontal bar charts plot the first category at the bottom by default,
        # backwards from the ranked table above (best vendor listed first/top).
        # x_axis is the category axis in openpyxl's model even for a horizontal
        # "bar" chart type -- reversing it puts the first-ranked vendor on top.
        chart.x_axis.scaling.orientation = "maxMin"
        ws.add_chart(chart, f"A{last_row + 3}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_bar_chart_category_axis_is_reversed -v`
Expected: PASS

- [ ] **Step 5: Visually verify with a real render**

```bash
cd /devx/repos/dast-eval
uv run dast-bench stakeholder-review generate --vendor-id invicti --vendor-id veracode --vendor-id nuclei --vendor-id zap --vendor-id stackhawk --out /tmp/task1-check.xlsx
mkdir -p /tmp/task1-render
timeout 120 soffice --headless --convert-to pdf --outdir /tmp/task1-render /tmp/task1-check.xlsx
pdftoppm -png -r 150 -f 1 -l 1 /tmp/task1-render/task1-check.pdf /tmp/task1-render/page
```

Then read `/tmp/task1-render/page-001.png` with the Read tool. Confirm: bar order (top to bottom) matches the ranked table above it (best vendor on top), single legend entry, no overlapping text.

- [ ] **Step 6: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all tests pass, no regressions.

- [ ] **Step 7: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "fix: reverse chart category axis so bar order matches ranked table"
```

---

### Task 2: Fix clipped title/header rows

**Files:**
- Modify: `core/render/stakeholder_workbook.py` (multiple locations, listed below)
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- No new functions. Adds `ws.row_dimensions[<row>].height = <value>` calls at 6 locations.

**Rows getting an explicit height, and why:**

| Sheet | Row | Current content/font | Height |
|---|---|---|---|
| Executive Summary | `_EXEC_TITLE_ROW` (1) | "Executive Summary", 14pt bold | 26 |
| Executive Summary | `_EXEC_LEGEND_HEADER_ROW` (3) | "Legend", bold | 20 |
| Executive Summary | `EXEC_TABLE_HEADER_ROW` | Ranked-table headers (e.g. "Production Safety & Operability"), bold + `wrap_text=True`, narrow columns — wraps to 2 lines | 34 |
| each vendor tab | `HEADER_ROW` (3) | Column headers (e.g. "Automated vs. Resolved Delta"), bold + `wrap_text=True`, narrow columns — wraps to 2-3 lines | 36 |
| each vendor tab | row 2 | Merged reviewer-slot header, bold + `wrap_text=True` | 24 |
| each vendor tab | `summary_header_row` | "Summary" banner, bold | 20 |

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stakeholder_workbook.py`, after `test_generate_workbook_applies_column_widths_freeze_panes_and_header_style` (find it with `grep -n "def test_generate_workbook_applies_column_widths_freeze_panes_and_header_style" tests/test_stakeholder_workbook.py`):

```python
def test_generate_workbook_title_and_header_rows_have_explicit_height(tmp_path):
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

    exec_ws = wb["Executive Summary"]
    assert exec_ws.row_dimensions[1].height == 26
    assert exec_ws.row_dimensions[_EXEC_LEGEND_HEADER_ROW].height == 20
    assert exec_ws.row_dimensions[EXEC_TABLE_HEADER_ROW].height == 34

    vendor_ws = wb["v1"]
    assert vendor_ws.row_dimensions[HEADER_ROW].height == 36
    assert vendor_ws.row_dimensions[2].height == 24

    category_rows, _ = _rollup_row_numbers(taxonomy)
    summary_header_row = min(category_rows.values()) - 1
    assert vendor_ws.row_dimensions[summary_header_row].height == 20
```

This test needs `HEADER_ROW` imported. Check the current import block at the top of the file (`grep -n "^from core.render.stakeholder_workbook import" -A 15 tests/test_stakeholder_workbook.py`) and add `HEADER_ROW` to it if it's not already there.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_title_and_header_rows_have_explicit_height -v`
Expected: FAIL — `assert None == 26` (row heights are unset in the current file).

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, inside `_add_executive_summary_sheet`:

Find:
```python
    title_cell = ws.cell(row=_EXEC_TITLE_ROW, column=1, value=_EXEC_SHEET_NAME)
    title_cell.font = Font(bold=True, size=14)
```
Replace with:
```python
    title_cell = ws.cell(row=_EXEC_TITLE_ROW, column=1, value=_EXEC_SHEET_NAME)
    title_cell.font = Font(bold=True, size=14)
    ws.row_dimensions[_EXEC_TITLE_ROW].height = 26
```

Find:
```python
    legend_header_cell = ws.cell(row=_EXEC_LEGEND_HEADER_ROW, column=1, value="Legend")
    legend_header_cell.font = Font(bold=True)
```
Replace with:
```python
    legend_header_cell = ws.cell(row=_EXEC_LEGEND_HEADER_ROW, column=1, value="Legend")
    legend_header_cell.font = Font(bold=True)
    ws.row_dimensions[_EXEC_LEGEND_HEADER_ROW].height = 20
```

Find (the ranked-table header loop):
```python
    for col_idx, header_name in enumerate(table_headers, start=1):
        cell = ws.cell(row=EXEC_TABLE_HEADER_ROW, column=col_idx, value=header_name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _HEADER_BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
```
Replace with:
```python
    for col_idx, header_name in enumerate(table_headers, start=1):
        cell = ws.cell(row=EXEC_TABLE_HEADER_ROW, column=col_idx, value=header_name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _HEADER_BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[EXEC_TABLE_HEADER_ROW].height = 34
```

Now inside `generate_workbook`, in the per-vendor loop:

Find:
```python
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=HEADER_ROW, column=col_idx)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.border = _HEADER_BORDER
            cell.alignment = _HEADER_ALIGNMENT
        _write_reviewer_slot_group_headers(ws, reviewer_slots)
```
Replace with:
```python
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=HEADER_ROW, column=col_idx)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.border = _HEADER_BORDER
            cell.alignment = _HEADER_ALIGNMENT
        ws.row_dimensions[HEADER_ROW].height = 36
        ws.row_dimensions[2].height = 24
        _write_reviewer_slot_group_headers(ws, reviewer_slots)
```

Find:
```python
        summary_cell = ws.cell(row=summary_header_row, column=1)
        summary_cell.font = _HEADER_FONT
```
Replace with:
```python
        summary_cell = ws.cell(row=summary_header_row, column=1)
        summary_cell.font = _HEADER_FONT
        ws.row_dimensions[summary_header_row].height = 20
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_title_and_header_rows_have_explicit_height -v`
Expected: PASS

- [ ] **Step 5: Visually verify with a real render**

```bash
cd /devx/repos/dast-eval
uv run dast-bench stakeholder-review generate --vendor-id invicti --vendor-id veracode --vendor-id nuclei --vendor-id zap --vendor-id stackhawk --out /tmp/task2-check.xlsx
mkdir -p /tmp/task2-render
timeout 120 soffice --headless --convert-to pdf --outdir /tmp/task2-render /tmp/task2-check.xlsx
pdftoppm -png -r 150 -f 1 -l 2 /tmp/task2-render/task2-check.pdf /tmp/task2-render/page
```

Read `/tmp/task2-render/page-001.png` and `/tmp/task2-render/page-002.png`. Confirm titles and wrapped column headers (e.g. "Production Safety & Operability", "Automated vs. Resolved Delta") are fully visible, not clipped, and the rows don't look absurdly oversized either.

- [ ] **Step 6: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "fix: give title and wrapped header rows explicit height so text isn't clipped"
```

---

### Task 3: Confirm >5 reviewer slots already works

**Files:**
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- None. This task adds a regression test for existing, already-working behavior (`--reviewer-slots N` on the CLI, `reviewer_slots` param on `generate_workbook`). No production code changes.

- [ ] **Step 1: Write the test (it should already pass — this locks in existing behavior)**

Add to `tests/test_stakeholder_workbook.py`, near `test_generate_workbook_with_zero_reviewer_slots_has_no_reviewer_columns`:

```python
def test_generate_workbook_supports_more_than_five_reviewer_slots(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=8,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[HEADER_ROW]]
    assert header.count("Score") == 8
    assert header.count("Dispute?") == 8
    assert header.count("Rationale") == 8
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_supports_more_than_five_reviewer_slots -v`
Expected: PASS on first run — this confirms the existing `--reviewer-slots` flag already handles counts above 5 with no code change needed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_stakeholder_workbook.py
git commit -m "test: lock in that reviewer_slots already scales past the default of 5"
```

---

### Task 4: Reviewers sheet — shared roster, formula-linked vendor-tab headers

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Modify: `core/stakeholder_review.py`
- Test: `tests/test_stakeholder_workbook.py`
- Test: `tests/test_stakeholder_review.py`

**Interfaces:**
- Produces (new, exported from `core/render/stakeholder_workbook.py` for use by `core/stakeholder_review.py` and tests):
  - `_REVIEWERS_SHEET_NAME: str = "Reviewers"`
  - `_REVIEWERS_FIRST_DATA_ROW: int = 6`
  - `_REVIEWERS_NAME_COL: int = 2`
  - `_REVIEWERS_ROLE_COL: int = 3`
  - `_add_reviewers_sheet(wb: Workbook, reviewer_slots: int) -> None`
  - `_reviewer_slot_group_header_formula(slot_index: int, slot_number: int) -> str`
- Consumes: `_unclaimed_reviewer_label(slot_number: int) -> str` (already exists, unchanged), `_reviewer_slot_columns`, `_HEADER_FONT`, `_HEADER_FILL`, `_HEADER_BORDER`, `_HEADER_ALIGNMENT`, `_BAND_FILL` (all already exist in the file).

#### Step 1: Write the failing tests (Reviewers sheet structure)

Add to `tests/test_stakeholder_workbook.py`. First, add these names to the existing `from core.render.stakeholder_workbook import (...)` block at the top of the file:

```python
    _REVIEWERS_FIRST_DATA_ROW,
    _REVIEWERS_NAME_COL,
    _REVIEWERS_ROLE_COL,
    _REVIEWERS_SHEET_NAME,
```

Then add the tests:

```python
def test_generate_workbook_adds_reviewers_sheet_with_editable_name_role_cells(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=2,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    wb = load_workbook(out_path)
    assert wb.sheetnames == ["Executive Summary", _REVIEWERS_SHEET_NAME, "v1"]

    ws = wb[_REVIEWERS_SHEET_NAME]
    assert ws.protection.sheet is True

    slot1_row = _REVIEWERS_FIRST_DATA_ROW
    slot2_row = _REVIEWERS_FIRST_DATA_ROW + 1
    assert ws.cell(row=slot1_row, column=1).value == 1
    assert ws.cell(row=slot2_row, column=1).value == 2
    assert ws.cell(row=slot1_row, column=_REVIEWERS_NAME_COL).protection.locked is False
    assert ws.cell(row=slot1_row, column=_REVIEWERS_ROLE_COL).protection.locked is False
    # Only 2 reviewer_slots were requested -- no row for a 3rd slot.
    assert ws.cell(row=_REVIEWERS_FIRST_DATA_ROW + 2, column=1).value is None


def test_generate_workbook_reviewer_slot_header_is_a_formula_referencing_reviewers_sheet(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=2,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    slot_columns = _reviewer_slot_columns(2)

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

- [ ] **Step 1a: Run tests to verify they fail**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_adds_reviewers_sheet_with_editable_name_role_cells tests/test_stakeholder_workbook.py::test_generate_workbook_reviewer_slot_header_is_a_formula_referencing_reviewers_sheet -v`
Expected: FAIL — `ImportError` (the new names don't exist yet), or once you comment out the import temporarily to check: `KeyError`/`AssertionError` since there's no Reviewers sheet or formula yet.

#### Step 2: Implement the Reviewers sheet and formula-linked headers

In `core/render/stakeholder_workbook.py`, find the existing reviewer-slot constants and functions (`grep -n "_unclaimed_reviewer_label\|_write_reviewer_slot_group_headers" core/render/stakeholder_workbook.py` to locate them — currently around lines 289-300).

Add these new constants right before `def _unclaimed_reviewer_label`:

```python
_REVIEWERS_SHEET_NAME = "Reviewers"
_REVIEWERS_TAB_COLOR = "8E44AD"
_REVIEWERS_TITLE_ROW = 1
_REVIEWERS_INSTRUCTIONS_ROW = 3
_REVIEWERS_HEADER_ROW = 5
_REVIEWERS_FIRST_DATA_ROW = 6
_REVIEWERS_SLOT_COL = 1
_REVIEWERS_NAME_COL = 2
_REVIEWERS_ROLE_COL = 3
```

Find:
```python
def _unclaimed_reviewer_label(slot_number: int) -> str:
    return f"Reviewer {slot_number} - {{name}} - {{role/title}}"


def _write_reviewer_slot_group_headers(ws, reviewer_slots: int) -> None:
    for i, (score_col, _dispute_col, rationale_col) in enumerate(_reviewer_slot_columns(reviewer_slots), start=1):
        ws.merge_cells(start_row=2, start_column=score_col, end_row=2, end_column=rationale_col)
        anchor = ws.cell(row=2, column=score_col, value=_unclaimed_reviewer_label(i))
        anchor.font = _HEADER_FONT
        anchor.fill = _HEADER_FILL
        anchor.border = _HEADER_BORDER
        anchor.alignment = _HEADER_ALIGNMENT
```

Replace with:

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


def _write_reviewer_slot_group_headers(ws, reviewer_slots: int) -> None:
    for slot_index, (score_col, _dispute_col, rationale_col) in enumerate(_reviewer_slot_columns(reviewer_slots)):
        ws.merge_cells(start_row=2, start_column=score_col, end_row=2, end_column=rationale_col)
        anchor = ws.cell(
            row=2, column=score_col,
            value=_reviewer_slot_group_header_formula(slot_index, slot_index + 1),
        )
        anchor.font = _HEADER_FONT
        anchor.fill = _HEADER_FILL
        anchor.border = _HEADER_BORDER
        anchor.alignment = _HEADER_ALIGNMENT
        anchor.protection = Protection(locked=True)


def _add_reviewers_sheet(wb: Workbook, reviewer_slots: int) -> None:
    ws = wb.create_sheet(title=_REVIEWERS_SHEET_NAME)
    ws.sheet_properties.tabColor = _REVIEWERS_TAB_COLOR

    title_cell = ws.cell(row=_REVIEWERS_TITLE_ROW, column=1, value=_REVIEWERS_SHEET_NAME)
    title_cell.font = Font(bold=True, size=14)
    ws.row_dimensions[_REVIEWERS_TITLE_ROW].height = 26

    ws.cell(
        row=_REVIEWERS_INSTRUCTIONS_ROW,
        column=1,
        value="Claim a slot by filling in your name and role below — it appears automatically on every vendor tab.",
    )

    header_labels = ["Slot", "Name", "Role / Title"]
    for col_idx, label in enumerate(header_labels, start=1):
        cell = ws.cell(row=_REVIEWERS_HEADER_ROW, column=col_idx, value=label)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _HEADER_BORDER
        cell.alignment = _HEADER_ALIGNMENT
    ws.row_dimensions[_REVIEWERS_HEADER_ROW].height = 20

    for i in range(reviewer_slots):
        row = _REVIEWERS_FIRST_DATA_ROW + i
        if i % 2 == 1:
            for col in range(1, 4):
                ws.cell(row=row, column=col).fill = _BAND_FILL

        slot_cell = ws.cell(row=row, column=_REVIEWERS_SLOT_COL, value=i + 1)
        slot_cell.alignment = Alignment(horizontal="center")

        for col in (_REVIEWERS_NAME_COL, _REVIEWERS_ROLE_COL):
            ws.cell(row=row, column=col).protection = Protection(locked=False)

    ws.column_dimensions[get_column_letter(_REVIEWERS_SLOT_COL)].width = 8
    ws.column_dimensions[get_column_letter(_REVIEWERS_NAME_COL)].width = 28
    ws.column_dimensions[get_column_letter(_REVIEWERS_ROLE_COL)].width = 28
    ws.protection.sheet = True
```

Now wire it into `generate_workbook`. Find:
```python
    _add_executive_summary_sheet(wb, taxonomy, vendors, pending_criteria, headers, top_tier_count)
    for vendor_index, vendor in enumerate(vendors):
```
Replace with:
```python
    _add_executive_summary_sheet(wb, taxonomy, vendors, pending_criteria, headers, top_tier_count)
    _add_reviewers_sheet(wb, reviewer_slots)
    for vendor_index, vendor in enumerate(vendors):
```

- [ ] **Step 2a: Run the Task 4 tests to verify they pass**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py::test_generate_workbook_adds_reviewers_sheet_with_editable_name_role_cells tests/test_stakeholder_workbook.py::test_generate_workbook_reviewer_slot_header_is_a_formula_referencing_reviewers_sheet -v`
Expected: PASS

- [ ] **Step 2b: Update the now-broken existing test**

`test_generate_workbook_adds_merged_reviewer_slot_group_headers` (around line 114) currently asserts the header cell's literal value equals `"Reviewer 1 - {name} - {role/title}"`. That's now a formula string, not literal text. Update it:

Find:
```python
    slot1_cell = ws.cell(row=2, column=slot1_score_col)
    assert slot1_cell.value == "Reviewer 1 - {name} - {role/title}"
    assert slot1_cell.font.bold is True
    assert slot1_cell.fill.fgColor.rgb == "001F4E78"

    slot2_score_col, _, slot2_rationale_col = slot_columns[1]
    slot2_range = f"{get_column_letter(slot2_score_col)}2:{get_column_letter(slot2_rationale_col)}2"
    assert slot2_range in [str(r) for r in ws.merged_cells.ranges]
    assert ws.cell(row=2, column=slot2_score_col).value == "Reviewer 2 - {name} - {role/title}"
```

Replace with:
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

Also update `test_generate_workbook_writes_one_sheet_per_vendor_with_headers` (around line 101):

Find:
```python
    assert wb.sheetnames == ["Executive Summary", "v1"]
```
Replace with:
```python
    assert wb.sheetnames == ["Executive Summary", _REVIEWERS_SHEET_NAME, "v1"]
```

- [ ] **Step 2c: Run the full stakeholder_workbook test file**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all pass.

- [ ] **Step 2d: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add Reviewers sheet, vendor-tab headers formula-link to it"
```

#### Step 3: Update `validate_workbook`'s claimed-slot check

`validate_workbook` (in `core/stakeholder_review.py`) currently detects whether a reviewer slot is "claimed" by reading the vendor tab's merged header cell and comparing its value to `_unclaimed_reviewer_label(slot_number)`. That cell is now a formula, so its stored `.value` (read via `openpyxl.load_workbook` without `data_only=True`) is the formula string, which will never equal the placeholder text — the check needs to read the Reviewers sheet's Name cell for that slot directly instead.

- [ ] **Step 3a: Write the failing tests**

In `tests/test_stakeholder_review.py`, first add a helper right after the existing imports (check current imports with `grep -n "^from\|^import" tests/test_stakeholder_review.py` — add to the `from core.render.stakeholder_workbook import (...)` block, or add a new import line):

```python
from core.render.stakeholder_workbook import (
    HEADER_ROW,
    _REVIEWERS_FIRST_DATA_ROW,
    _REVIEWERS_NAME_COL,
    _REVIEWERS_SHEET_NAME,
    _reviewer_slot_columns,
    generate_workbook,
)
```

(This replaces whatever the current `from core.render.stakeholder_workbook import ...` line is — merge with it rather than duplicating, keeping every name both files already use.)

Add this helper near the other test helpers (e.g. near `_generate_two_reviewer_slots`):

```python
def _claim_slot(wb, slot_number: int, name: str = "Reviewer") -> None:
    ws = wb[_REVIEWERS_SHEET_NAME]
    ws.cell(row=_REVIEWERS_FIRST_DATA_ROW + slot_number - 1, column=_REVIEWERS_NAME_COL, value=name)
```

Now find and update every test that currently "claims" a slot by writing directly to the vendor-tab merged header cell (`grep -n 'column=slot.*_score_col, value=' tests/test_stakeholder_review.py` to find all 3 occurrences). For each:

In `test_validate_workbook_flags_dispute_without_rationale_and_invalid_score` (around line 279), find:
```python
    wb = load_workbook(file_path)
    ws = wb["v1"]
    # Claim both slots before entering test data
    slot1_score_col, _, _ = _reviewer_slot_columns(2)[0]
    slot2_score_col, _, _ = _reviewer_slot_columns(2)[1]
    ws.cell(row=2, column=slot1_score_col, value="Reviewer One")
    ws.cell(row=2, column=slot2_score_col, value="Reviewer Two")
    cols = _column_map(ws)
```
Replace with:
```python
    wb = load_workbook(file_path)
    ws = wb["v1"]
    # Claim both slots before entering test data
    _claim_slot(wb, 1, "Reviewer One")
    _claim_slot(wb, 2, "Reviewer Two")
    cols = _column_map(ws)
```

In `test_validate_workbook_flags_lowercase_dispute_without_rationale` (around line 428), find:
```python
    wb = load_workbook(file_path)
    ws = wb["v1"]
    # Claim the slot before entering test data
    slot1_score_col, _, _ = _reviewer_slot_columns(2)[0]
    ws.cell(row=2, column=slot1_score_col, value="Reviewer One")
    cols = _column_map(ws)
```
Replace with:
```python
    wb = load_workbook(file_path)
    ws = wb["v1"]
    # Claim the slot before entering test data
    _claim_slot(wb, 1, "Reviewer One")
    cols = _column_map(ws)
```

In `test_validate_workbook_does_not_flag_claimed_slot_with_data` (around line 462), find:
```python
def test_validate_workbook_does_not_flag_claimed_slot_with_data(tmp_path):
    file_path = _generate_two_reviewer_slots(tmp_path, "review.xlsx")
    score_letter, _, _ = _slot_letters(1)
    slot1_score_col, _, _ = _reviewer_slot_columns(2)[0]

    wb = load_workbook(file_path)
    ws = wb["v1"]
    # Overwrite the same merged anchor cell generate_workbook wrote
    # "Reviewer 1" into -- this is what "claiming" the slot actually means.
    ws.cell(row=2, column=slot1_score_col, value="Jane Doe (DAST SME)")
    cols = _column_map(ws)
```
Replace with:
```python
def test_validate_workbook_does_not_flag_claimed_slot_with_data(tmp_path):
    file_path = _generate_two_reviewer_slots(tmp_path, "review.xlsx")
    score_letter, _, _ = _slot_letters(1)

    wb = load_workbook(file_path)
    ws = wb["v1"]
    # Claiming a slot means filling in a name on the Reviewers sheet -- the vendor
    # tab's merged header cell just formula-references it, it's not typed directly.
    _claim_slot(wb, 1, "Jane Doe (DAST SME)")
    cols = _column_map(ws)
```

- [ ] **Step 3b: Run tests to verify current state**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_review.py -v`
Expected: `test_validate_workbook_flags_unclaimed_slot_with_data` and the 3 tests just edited still pass or fail in a way consistent with `validate_workbook` not yet reading the Reviewers sheet (the production code hasn't changed yet in this step — the tests use `wb.save(file_path)` after `_claim_slot`, so check each edited test still calls `wb.save(file_path)` after the claim, matching the original pattern). If any assertion around "unclaimed" fails unexpectedly at this point, that confirms `validate_workbook` needs the Step 4 fix below.

- [ ] **Step 4: Implement the `validate_workbook` fix**

In `core/stakeholder_review.py`, find the import block:
```python
from .render.stakeholder_workbook import (
    FIRST_DATA_ROW,
    HEADER_ROW,
    SCORE_VALUES,
    _reviewer_slot_columns,
    _reviewer_slot_count_from_headers,
    _unclaimed_reviewer_label,
)
```
Replace with:
```python
from .render.stakeholder_workbook import (
    FIRST_DATA_ROW,
    HEADER_ROW,
    SCORE_VALUES,
    _REVIEWERS_FIRST_DATA_ROW,
    _REVIEWERS_NAME_COL,
    _REVIEWERS_SHEET_NAME,
    _reviewer_slot_columns,
    _reviewer_slot_count_from_headers,
)
```

Find (inside `validate_workbook`):
```python
def validate_workbook(file_path: Path) -> list[str]:
    wb = load_workbook(file_path)
    issues: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        cols = _column_map(ws)
        if "_criterion_id" not in cols:
            # Not a per-vendor rollup sheet (e.g. the Executive Summary tab).
            continue
        crit_col = cols["_criterion_id"]
        slot_letters = _slot_letters(ws)

        for slot_number, (score_letter, dispute_letter, rationale_letter) in enumerate(slot_letters, start=1):
            group_header_value = ws.cell(row=2, column=_reviewer_slot_columns(len(slot_letters))[slot_number - 1][0]).value
            slot_claimed = group_header_value != _unclaimed_reviewer_label(slot_number)
```
Replace with:
```python
def validate_workbook(file_path: Path) -> list[str]:
    wb = load_workbook(file_path)
    reviewers_ws = wb[_REVIEWERS_SHEET_NAME] if _REVIEWERS_SHEET_NAME in wb.sheetnames else None
    issues: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        cols = _column_map(ws)
        if "_criterion_id" not in cols:
            # Not a per-vendor rollup sheet (e.g. the Executive Summary or Reviewers tab).
            continue
        crit_col = cols["_criterion_id"]
        slot_letters = _slot_letters(ws)

        for slot_number, (score_letter, dispute_letter, rationale_letter) in enumerate(slot_letters, start=1):
            # A slot's identity is claimed on the Reviewers sheet (Name column), not on
            # the vendor tab -- the vendor-tab header is a formula that mirrors it.
            slot_claimed = bool(
                reviewers_ws
                and reviewers_ws.cell(row=_REVIEWERS_FIRST_DATA_ROW + slot_number - 1, column=_REVIEWERS_NAME_COL).value
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /devx/repos/dast-eval && uv run pytest tests/test_stakeholder_review.py -v`
Expected: all pass, including `test_validate_workbook_flags_unclaimed_slot_with_data` (slot never claimed on the Reviewers sheet — still flagged) and `test_validate_workbook_does_not_flag_claimed_slot_with_data` (slot claimed via `_claim_slot` — no longer flagged).

- [ ] **Step 6: Run the full test suite**

Run: `cd /devx/repos/dast-eval && uv run pytest -q`
Expected: all tests pass, no regressions anywhere.

- [ ] **Step 7: Final end-to-end visual check**

```bash
cd /devx/repos/dast-eval
uv run dast-bench stakeholder-review generate --vendor-id invicti --vendor-id veracode --vendor-id nuclei --vendor-id zap --vendor-id stackhawk --reviewer-slots 7 --out reports/stakeholder-review-all.xlsx
mkdir -p /tmp/task4-render
timeout 120 soffice --headless --convert-to pdf --outdir /tmp/task4-render reports/stakeholder-review-all.xlsx
pdftoppm -png -r 150 -f 1 -l 3 /tmp/task4-render/final.pdf /tmp/task4-render/page
```

Read `/tmp/task4-render/page-001.png` (Executive Summary — chart order), `page-002.png` (Reviewers sheet — Slot/Name/Role table, 7 rows), `page-003.png` (first vendor tab — header row not clipped, reviewer-slot header row present) with the Read tool. Confirm everything from Tasks 1-4 together, with no new visual issues.

- [ ] **Step 8: Commit**

```bash
git add core/stakeholder_review.py tests/test_stakeholder_review.py
git commit -m "fix: validate_workbook reads reviewer claims from the Reviewers sheet"
```
