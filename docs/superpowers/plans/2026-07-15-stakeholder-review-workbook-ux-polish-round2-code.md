# Stakeholder Review Workbook — UX Polish Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the five fixes from
`docs/superpowers/specs/2026-07-15-stakeholder-review-workbook-ux-polish-round2-design.md`:
freeze the Weight column, wrap long Evidence/Rationale text, make row
banding continuous under the tier-highlight, box the Executive Summary
legend, and highlight the top-ranked vendor's row.

**Architecture:** All five fixes are small, independent edits inside the
same two functions from Round 1 — `generate_workbook` (Tasks 1-3) and
`_add_executive_summary_sheet` (Tasks 4-5) — both in
`core/render/stakeholder_workbook.py`. No new files, no new modules, no
CLI changes.

**Tech Stack:** Python, `openpyxl`, `pytest`. No new dependencies.

## Global Constraints

- No new dedicated pending-row fill color — not requested, out of scope.
- No change to the `Dispute?` dropdown (stays `"Yes"` + blank) — confirmed,
  do not touch `dispute_dv` or `_is_dispute_yes`.
- No change to Automated Confidence column width.
- `openpyxl` color/RGB values round-trip with a leading `00` alpha byte
  (e.g. `"F2F2F2"` reads back as `"00F2F2F2"`); an unfilled cell's
  `fill.fgColor.rgb` reads back as `"00000000"`.
- Do not set an explicit `row_dimensions[...].height` anywhere — Excel
  auto-expands wrapped rows on open as long as height is left unset;
  hardcoding a height is guesswork `openpyxl` cannot verify.

---

## File Structure

- Modify: `core/render/stakeholder_workbook.py` — freeze-pane column,
  wrap-text on two column types, a second tier-fill shade, a legend
  border/fill box, and a top-vendor-row highlight.
- Modify: `tests/test_stakeholder_workbook.py` (existing file, extended;
  one pre-existing assertion updated in Task 1)

---

### Task 1: Freeze the Weight column

**Files:**
- Modify: `core/render/stakeholder_workbook.py:279`
- Modify: `tests/test_stakeholder_workbook.py:246` (pre-existing
  assertion needs updating, not just a new test)

**Interfaces:**
- No new functions. Pure constant-value change; no other task depends on it.

- [ ] **Step 1: Update the pre-existing test and add the new one**

In `tests/test_stakeholder_workbook.py`, change line 246 from:

```python
    assert ws.freeze_panes == "C4"
```

to:

```python
    assert ws.freeze_panes == "D4"
```

Then append this new test to the file:

```python
def test_generate_workbook_freeze_panes_include_weight_column(tmp_path):
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
    assert ws.freeze_panes == "D4"
```

- [ ] **Step 2: Run tests to verify the updated assertion fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k freeze_panes -v`
Expected: FAIL — `assert 'C4' == 'D4'` (the pre-existing test's updated
assertion doesn't match the current, un-fixed code yet)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, change line 279 from:

```python
        ws.freeze_panes = "C4"
```

to:

```python
        ws.freeze_panes = "D4"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "fix: include Weight column in vendor sheet freeze panes"
```

---

### Task 2: Wrap Automated Evidence and Rationale text

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Produces: `_is_wrapped_text(header_name: str) -> bool` — private helper,
  used only inside `generate_workbook`'s per-cell alignment block; no
  other task depends on it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stakeholder_workbook.py`:

```python
def test_generate_workbook_wraps_evidence_and_rationale_text(tmp_path):
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
    evidence_col = header.index("Automated Evidence") + 1
    rationale_col = header.index("DAST SME Rationale") + 1
    score_col = header.index("Automated Score") + 1

    assert ws.cell(row=4, column=evidence_col).alignment.wrap_text is True
    assert ws.cell(row=4, column=rationale_col).alignment.wrap_text is True
    assert ws.cell(row=4, column=score_col).alignment.wrap_text is not True
    assert ws.row_dimensions[4].height is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k wraps_evidence -v`
Expected: FAIL — `assert None is True` (Evidence cell's `wrap_text` isn't set)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, add this helper right after
`_is_right_aligned_numeric` (currently at line 219-223):

```python
def _is_wrapped_text(header_name: str) -> bool:
    return header_name == "Automated Evidence" or header_name.endswith(" Rationale")
```

Then, in `generate_workbook`'s per-cell alignment block (currently):

```python
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

change the final `else` branch to:

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "fix: wrap Automated Evidence and Rationale text instead of truncating"
```

---

### Task 3: Continuous row banding under the tier highlight

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Produces: `_TIER_FILL_ODD` module constant — used only inside
  `generate_workbook`'s per-criterion fill block; no other task depends
  on it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stakeholder_workbook.py`:

```python
def test_generate_workbook_bands_continuously_under_tier_highlight(tmp_path):
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
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
        top_tier_count=2,
    )
    ws = load_workbook(out_path)["v1"]
    # All four scores are equal (4.0) and above the needs-attention
    # threshold, so priority order is purely descending weight:
    # c1 (row 4), c2 (row 5), c3 (row 6), c4 (row 7).
    assert ws.cell(row=4, column=1).fill.fgColor.rgb == "00FFF2CC"  # tier, even (i=0)
    assert ws.cell(row=5, column=1).fill.fgColor.rgb == "00F9E79F"  # tier, odd (i=1)
    assert ws.cell(row=6, column=1).fill.fgColor.rgb == "00000000"  # non-tier, even (i=2) -- no fill
    assert ws.cell(row=7, column=1).fill.fgColor.rgb == "00F2F2F2"  # non-tier, odd (i=3) -- banded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k bands_continuously -v`
Expected: FAIL — `assert '00FFF2CC' == '00F9E79F'` (row 5 currently gets
the same flat tier fill as row 4, since banding is skipped entirely for
tier rows today)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, add this constant right after
`_TIER_FILL`/`_UNFILLED_FILL` (currently lines 31-32):

```python
_TIER_FILL_ODD = PatternFill(start_color="F9E79F", end_color="F9E79F", fill_type="solid")
```

Then, in `generate_workbook`'s per-criterion loop, change:

```python
            if i < top_tier_count:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _TIER_FILL
            elif i % 2 == 1:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _BAND_FILL
```

to:

```python
            if i < top_tier_count:
                tier_fill = _TIER_FILL_ODD if i % 2 == 1 else _TIER_FILL
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = tier_fill
            elif i % 2 == 1:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _BAND_FILL
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: make row banding continuous under the tier highlight"
```

---

### Task 4: Executive Summary legend box

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `_BAND_FILL`, `_HEADER_BORDER` (both already defined, Round 1);
  `_EXEC_LEGEND_HEADER_ROW`, `_EXEC_LEGEND_FIRST_ROW`,
  `_EXEC_LEGEND_LINES_TEMPLATE` (already defined, Round 1).
- Produces: no new public names — extends `_add_executive_summary_sheet`'s
  body only.

- [ ] **Step 1: Write the failing test**

Add these imports to `tests/test_stakeholder_workbook.py`'s existing
`from core.render.stakeholder_workbook import (...)` block (which
currently includes `_all_headers`, `_column_index`, `_rollup_row_numbers`,
`compute_priority_order`, `EXEC_TABLE_FIRST_DATA_ROW`,
`EXEC_TABLE_HEADER_ROW`, `generate_workbook`), adding two more names:

```python
from core.render.stakeholder_workbook import (
    _all_headers,
    _column_index,
    _EXEC_LEGEND_FIRST_ROW,
    _EXEC_LEGEND_HEADER_ROW,
    _EXEC_LEGEND_LINES_TEMPLATE,
    _rollup_row_numbers,
    compute_priority_order,
    EXEC_TABLE_FIRST_DATA_ROW,
    EXEC_TABLE_HEADER_ROW,
    generate_workbook,
)
```

Then append this test:

```python
def test_generate_workbook_executive_summary_legend_has_border_and_fill(tmp_path):
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
    legend_last_row = _EXEC_LEGEND_FIRST_ROW + len(_EXEC_LEGEND_LINES_TEMPLATE) - 1

    top_left = ws.cell(row=_EXEC_LEGEND_HEADER_ROW, column=1)
    assert top_left.fill.fgColor.rgb == "00F2F2F2"
    assert top_left.border.top.style == "thin"

    bottom_right = ws.cell(row=legend_last_row, column=5)
    assert bottom_right.fill.fgColor.rgb == "00F2F2F2"
    assert bottom_right.border.bottom.style == "thin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k legend_has_border -v`
Expected: FAIL — `assert '00000000' == '00F2F2F2'` (no fill applied to
the legend block yet)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, inside `_add_executive_summary_sheet`,
right after the legend-lines loop:

```python
    for i, line in enumerate(_EXEC_LEGEND_LINES_TEMPLATE):
        ws.cell(row=_EXEC_LEGEND_FIRST_ROW + i, column=1, value=line.format(top_tier_count=top_tier_count))
```

add:

```python
    legend_last_row = _EXEC_LEGEND_FIRST_ROW + len(_EXEC_LEGEND_LINES_TEMPLATE) - 1
    for row in range(_EXEC_LEGEND_HEADER_ROW, legend_last_row + 1):
        for col in range(1, 6):
            cell = ws.cell(row=row, column=col)
            cell.fill = _BAND_FILL
            cell.border = _HEADER_BORDER
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: box the Executive Summary legend with border and fill"
```

---

### Task 5: Highlight the top-ranked vendor's row

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `ranked_vendors`, `table_headers` (both already computed
  locals inside `_add_executive_summary_sheet`); `_TIER_FILL` (Round 1).
- Produces: no new public names — final extension to
  `_add_executive_summary_sheet` in this plan.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stakeholder_workbook.py`:

```python
def test_generate_workbook_executive_summary_highlights_top_vendor_row(tmp_path):
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

    ws = load_workbook(out_path)["Executive Summary"]
    # Vendor A scored higher on every criterion, so it ranks first (row EXEC_TABLE_FIRST_DATA_ROW).
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1).value == "Vendor A"
    top_row_cell = ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1)
    assert top_row_cell.font.bold is True
    assert top_row_cell.fill.fgColor.rgb == "00FFF2CC"

    second_row_cell = ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW + 1, column=1)
    assert second_row_cell.value == "Vendor B"
    assert second_row_cell.font.bold is not True
    assert second_row_cell.fill.fgColor.rgb == "00000000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k highlights_top_vendor -v`
Expected: FAIL — `assert None is True` (`top_row_cell.font.bold` is
`None`, no highlight applied yet)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, inside `_add_executive_summary_sheet`,
right after the vendor-ranking loop and its trailing column-width loop:

```python
    for col_idx, header_name in enumerate(table_headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 40 if header_name == "Vendor" else 20

    ws.protection.sheet = True
```

insert the highlight block between them, so it reads:

```python
    for col_idx, header_name in enumerate(table_headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 40 if header_name == "Vendor" else 20

    if ranked_vendors:
        for col in range(1, len(table_headers) + 1):
            top_cell = ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=col)
            top_cell.font = Font(bold=True)
            top_cell.fill = _TIER_FILL

    ws.protection.sheet = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions (should be 172 pre-existing + 6
new/updated from this plan)

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: highlight the top-ranked vendor's row in Executive Summary"
```
