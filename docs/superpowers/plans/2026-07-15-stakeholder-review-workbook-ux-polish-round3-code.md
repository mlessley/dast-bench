# Stakeholder Review Workbook — UX Polish Round 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the five fixes from
`docs/superpowers/specs/2026-07-15-stakeholder-review-workbook-ux-polish-round3-design.md`:
extend freeze panes through Automated Confidence, clarify the pending
placeholder text, add a "Summary" header to each vendor sheet's rollup
block, switch the reviewer-slot placeholder to a full name+role
template, add a Weight explanation to the Executive Summary legend, and
bump the default reviewer-slot count from 3 to 5.

**Architecture:** All five fixes are small, independent edits inside
`core/render/stakeholder_workbook.py` (Tasks 1-4) and one CLI default
(Task 5, `core/cli.py`). No new files, no new modules.

**Tech Stack:** Python, `openpyxl`, `typer`, `pytest`. No new dependencies.

## Global Constraints

- No change to `compute_priority_order`'s weight-based sort — confirmed
  as-is, out of scope for this round.
- No in-workbook explanation of the yellow tier-highlight color —
  deferred, out of scope for this round.
- `validate_workbook`'s unclaimed-slot check (already merged) calls
  `_unclaimed_reviewer_label(slot_number)` for its comparison, not a
  hardcoded string — Task 3's format change needs no corresponding
  change in `core/stakeholder_review.py`.
- The Executive Summary's `EXEC_TABLE_HEADER_ROW`/`EXEC_TABLE_FIRST_DATA_ROW`
  constants, and the Round-2 legend-box border/fill loop, are all
  computed from `len(_EXEC_LEGEND_LINES_TEMPLATE)` — appending a new
  legend line (Task 4) automatically shifts them and automatically
  extends the border/fill box to cover the new line. No other code or
  test needs to change to accommodate the new line, since every test
  that depends on these row numbers references the symbolic constants,
  not hardcoded row numbers.
- `openpyxl` color/RGB values round-trip with a leading `00` alpha byte.

---

## File Structure

- Modify: `core/render/stakeholder_workbook.py` — freeze-pane extent,
  pending-text wording, rollup "Summary" header, reviewer-slot
  placeholder format, Executive Summary legend line, default
  `reviewer_slots` value.
- Modify: `core/cli.py` — default `--reviewer-slots` value.
- Modify: `tests/test_stakeholder_workbook.py` (existing file, extended;
  two pre-existing assertions updated)
- Modify: `tests/test_cli_stakeholder_review.py` (existing file; one
  test renamed and its assertion updated)

---

### Task 1: Freeze panes through Automated Confidence + clearer pending text

**Files:**
- Modify: `core/render/stakeholder_workbook.py:16-19,327`
- Modify: `tests/test_stakeholder_workbook.py:298,512` (pre-existing
  assertions need updating, not just new tests)

**Interfaces:**
- No new functions. Pure constant-value changes; no other task depends
  on them.

- [ ] **Step 1: Update the pre-existing tests and add the new ones**

In `tests/test_stakeholder_workbook.py`, change line 298 (inside
`test_generate_workbook_applies_column_widths_freeze_panes_and_header_style`)
from:

```python
    assert ws.freeze_panes == "D4"
```

to:

```python
    assert ws.freeze_panes == "G4"
```

Change line 512 (inside
`test_generate_workbook_freeze_panes_include_weight_column`) from:

```python
    assert ws.freeze_panes == "D4"
```

to:

```python
    assert ws.freeze_panes == "G4"
```

Then append this new test to the file:

```python
def test_generate_workbook_writes_updated_pending_row_scope_text(tmp_path):
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
    header = [c.value for c in ws[3]]
    evidence_col = header.index("Automated Evidence") + 1
    crit_id_col = header.index("_criterion_id") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    assert ws.cell(row=row, column=evidence_col).value == (
        "Pending — dast-scan results not yet available. "
        "Do not score or edit this row; it will be populated in Round 2."
    )
```

- [ ] **Step 2: Run tests to verify the updated/new ones fail**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k "freeze_panes or pending_row_scope" -v`
Expected: FAIL — `assert 'D4' == 'G4'` for the two updated tests, and an
assertion mismatch on the exact pending text for the new one (current
code still says `"Do not edit; will be populated in Round 2."`)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, change lines 16-19 from:

```python
_PENDING_TEXT = (
    "Pending — dast-scan results not yet available. "
    "Do not edit; will be populated in Round 2."
)
```

to:

```python
_PENDING_TEXT = (
    "Pending — dast-scan results not yet available. "
    "Do not score or edit this row; it will be populated in Round 2."
)
```

Change line 327 from:

```python
        ws.freeze_panes = "D4"
```

to:

```python
        ws.freeze_panes = "G4"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "fix: freeze panes through Automated Confidence, clarify pending-row text"
```

---

### Task 2: Vendor-sheet rollup "Summary" header

**Files:**
- Modify: `core/render/stakeholder_workbook.py:454-461`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `_rollup_row_numbers` (existing), `_HEADER_FONT`/`_HEADER_FILL`
  (existing, Round 1).
- Produces: no new public names — extends `generate_workbook`'s
  existing rollup-block code, reusing the same blank spacer row that
  `_rollup_row_numbers` already accounts for (no row-number shift).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stakeholder_workbook.py`:

```python
def test_generate_workbook_rollup_block_has_summary_header(tmp_path):
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
    ws = load_workbook(out_path)["v1"]
    category_rows, _ = _rollup_row_numbers(taxonomy)
    summary_header_row = min(category_rows.values()) - 1

    cell = ws.cell(row=summary_header_row, column=1)
    assert cell.value == "Summary"
    assert cell.font.bold is True
    assert cell.fill.fgColor.rgb == "001F4E78"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k rollup_block_has_summary_header -v`
Expected: FAIL — `assert None == "Summary"` (that row is currently blank)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, inside `generate_workbook`,
change:

```python
        ws.append([])
        category_rows_for_border, _ = _rollup_row_numbers(taxonomy)
        first_rollup_row = category_rows_for_border[_ordered_categories(taxonomy)[0]]
```

to:

```python
        ws.append([])
        summary_header_row = ws.max_row
        summary_cell = ws.cell(row=summary_header_row, column=1, value="Summary")
        summary_cell.font = _HEADER_FONT
        summary_cell.fill = _HEADER_FILL
        category_rows_for_border, _ = _rollup_row_numbers(taxonomy)
        first_rollup_row = category_rows_for_border[_ordered_categories(taxonomy)[0]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add Summary header to vendor-sheet rollup block"
```

---

### Task 3: Reviewer-slot placeholder becomes a name+role template

**Files:**
- Modify: `core/render/stakeholder_workbook.py:286-287`
- Modify: `tests/test_stakeholder_workbook.py:133,140` (pre-existing
  assertions need updating)

**Interfaces:**
- Consumes/modifies: `_unclaimed_reviewer_label(slot_number: int) ->
  str` (existing, from the reviewer-slots plan) — same signature,
  changed return format. `core/stakeholder_review.py`'s
  `validate_workbook` already calls this function for its comparison
  (not a hardcoded string), so it needs no change.

- [ ] **Step 1: Update the pre-existing test**

In `tests/test_stakeholder_workbook.py`, inside
`test_generate_workbook_adds_merged_reviewer_slot_group_headers`,
change:

```python
    slot1_cell = ws.cell(row=2, column=slot1_score_col)
    assert slot1_cell.value == "Reviewer 1"
    assert slot1_cell.font.bold is True
    assert slot1_cell.fill.fgColor.rgb == "001F4E78"

    slot2_score_col, _, slot2_rationale_col = slot_columns[1]
    slot2_range = f"{get_column_letter(slot2_score_col)}2:{get_column_letter(slot2_rationale_col)}2"
    assert slot2_range in [str(r) for r in ws.merged_cells.ranges]
    assert ws.cell(row=2, column=slot2_score_col).value == "Reviewer 2"
```

to:

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

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k merged_reviewer_slot_group_headers -v`
Expected: FAIL — `assert 'Reviewer 1' == 'Reviewer 1 - {name} - {role/title}'`

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, change:

```python
def _unclaimed_reviewer_label(slot_number: int) -> str:
    return f"Reviewer {slot_number}"
```

to:

```python
def _unclaimed_reviewer_label(slot_number: int) -> str:
    return f"Reviewer {slot_number} - {{name}} - {{role/title}}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions in `tests/test_stakeholder_review.py`
(its unclaimed-slot check calls `_unclaimed_reviewer_label` directly,
never a hardcoded string, so it adapts automatically)

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: reviewer-slot placeholder shows a name+role template"
```

---

### Task 4: Executive Summary legend — explain Weight

**Files:**
- Modify: `core/render/stakeholder_workbook.py:92-100`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- No new functions. Appends one string to the existing
  `_EXEC_LEGEND_LINES_TEMPLATE` module constant. `EXEC_TABLE_HEADER_ROW`/
  `EXEC_TABLE_FIRST_DATA_ROW` are derived from `len(_EXEC_LEGEND_LINES_TEMPLATE)`
  and shift automatically — no other code changes.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stakeholder_workbook.py`:

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

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -k legend_explains_weight -v`
Expected: FAIL — `assert None is not None` or a mismatch (that legend
row doesn't exist yet — only 5 lines currently)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, change:

```python
_EXEC_LEGEND_LINES_TEMPLATE = [
    "Pending rows: dast-scan results not yet available; locked until Round 2 populate fills them in.",
    "Tier highlight (light yellow): top {top_tier_count} priority criteria for this round, shown for quick scanning.",
    "Dispute = Yes requires a non-blank Rationale; discuss unresolved disputes before finalizing a score.",
    "Automated Confidence: 'paper' = desk research only; 'hands-on' = verified via dast-scan.",
    "Weighted Avg Score is normalized to a 0-5 scale and is comparable across vendors even when the "
    "number of pending criteria differs. Row order below is fixed when this workbook is generated and "
    "does not auto-resort if scores change later.",
]
```

to:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS (including the pre-existing legend-box-border
test, which automatically covers the new 6th line since its range is
computed from `len(_EXEC_LEGEND_LINES_TEMPLATE)`)

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: explain Weight's meaning and provenance in the Executive Summary legend"
```

---

### Task 5: Default reviewer-slot count changes from 3 to 5

**Files:**
- Modify: `core/cli.py:533`
- Modify: `tests/test_cli_stakeholder_review.py:53-67` (test renamed and
  its assertion updated)

**Interfaces:**
- Consumes: nothing new.
- Produces: no new public names — pure default-value change on the
  CLI's `--reviewer-slots` option only.

**Important correctness note:** `generate_workbook`'s `reviewer_slots`
parameter has **no default today** — it's a required parameter followed
by three other required parameters (`pending_criteria`,
`research_caches`, `out_path`) before `top_tier_count`'s existing
`= 10` default. Giving `reviewer_slots` a default value here would be a
Python `SyntaxError` ("non-default argument follows default argument")
unless every parameter after it also got a default, which is explicitly
out of scope. Every real call site (`core/cli.py` and every test) already
passes `reviewer_slots` explicitly by keyword, so `generate_workbook`
itself doesn't need — and must not get — a default. This task changes
**only** the CLI's own `typer.Option(3, ...)` default, which is where
the actual "what happens if a driver doesn't pass `--reviewer-slots`"
behavior lives.

- [ ] **Step 1: Update the pre-existing test**

In `tests/test_cli_stakeholder_review.py`, change:

```python
def test_cli_stakeholder_review_generate_defaults_to_three_reviewer_slots(tmp_path, monkeypatch):
    _setup_repo(tmp_path, monkeypatch)
    out_path = tmp_path / "review.xlsx"
    result = runner.invoke(
        app,
        [
            "stakeholder-review", "generate",
            "--vendor-id", "v1",
            "--out", str(out_path),
        ],
    )
    assert result.exit_code == 0, result.output
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    assert header.count("Score") == 3
```

to:

```python
def test_cli_stakeholder_review_generate_defaults_to_five_reviewer_slots(tmp_path, monkeypatch):
    _setup_repo(tmp_path, monkeypatch)
    out_path = tmp_path / "review.xlsx"
    result = runner.invoke(
        app,
        [
            "stakeholder-review", "generate",
            "--vendor-id", "v1",
            "--out", str(out_path),
        ],
    )
    assert result.exit_code == 0, result.output
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    assert header.count("Score") == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_stakeholder_review.py -k defaults_to_five -v`
Expected: FAIL — `assert 3 == 5` (source still defaults to 3)

- [ ] **Step 3: Write minimal implementation**

Do **not** modify `core/render/stakeholder_workbook.py` in this task —
`generate_workbook`'s `reviewer_slots` parameter stays exactly as it is
(no default), per the correctness note above.

In `core/cli.py`, change:

```python
    reviewer_slots: int = typer.Option(3, "--reviewer-slots"),
```

to:

```python
    reviewer_slots: int = typer.Option(5, "--reviewer-slots"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_stakeholder_review.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions (this is the last task in the
plan)

- [ ] **Step 6: Commit**

```bash
git add core/render/stakeholder_workbook.py core/cli.py tests/test_cli_stakeholder_review.py
git commit -m "feat: bump default reviewer-slot count from 3 to 5"
```
