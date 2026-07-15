# Stakeholder Review Workbook — Self-Service Reviewer Slots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace driver-specified named stakeholders with generic,
self-claimed reviewer slots (default 3), per
`docs/superpowers/specs/2026-07-15-stakeholder-review-reviewer-slots-design.md`:
a merged `"Reviewer N"` placeholder header per 3-column set, positional
(not header-text) addressing in `merge`/`validate_workbook`/`populate`,
and one new validate check for an unclaimed slot with data.

**Architecture:** `generate_workbook`'s `stakeholders: list[tuple[str |
None, str]]` parameter becomes `reviewer_slots: int` everywhere it flows
— the CLI, the render module, and the review module. Column addressing
for reviewer-slot cells switches from header-text lookup (`_column_map`)
to deterministic column-position math, since sub-headers become
identical, repeated text (`"Score"`/`"Dispute?"`/`"Rationale"`) instead
of unique per-stakeholder strings.

**Tech Stack:** Python, `openpyxl` (merged cells, existing style
constants), `typer` (CLI), `pytest`. No new dependencies.

## Global Constraints

- This is a breaking signature change, not additive. Every existing test
  that builds a workbook via `stakeholders=[...]` is migrated to
  `reviewer_slots=N` as part of this plan — this is expected, sized-in
  work, not incidental scope creep.
- The merged group-header cell (row 2) is **decorative only** for
  `merge` — it never reads, writes, or reconciles that cell's text.
  `validate_workbook` is the one narrow exception: an exact-string
  comparison against the known unclaimed-placeholder text
  (`"Reviewer N"`), purely as a claimed/unclaimed signal — never a parse
  of *what* name was typed in.
- Row 2 (currently blank on every vendor sheet) is reused for the merged
  group-header row — `HEADER_ROW`, `FIRST_DATA_ROW`, and every
  rollup/Executive-Summary row constant are unaffected and must not
  change.
- `openpyxl` color/RGB values round-trip with a leading `00` alpha byte;
  an unfilled cell's `fill.fgColor.rgb` reads back as `"00000000"`.
- `populate`'s unlock-after-fill loop currently iterates `_column_map`'s
  deduplicated `{header_text: column_letter}` dict — with repeated
  `"Score"`/`"Dispute?"`/`"Rationale"` text across slots, that dict
  collapses to one entry per label (last slot wins), so `populate` would
  silently only unlock the *last* reviewer slot after this change unless
  it is also switched to positional addressing. This is a real
  correctness fix bundled into this plan's `core/stakeholder_review.py`
  task, not an unrelated addition.

---

## File Structure

- Modify: `core/render/stakeholder_workbook.py` — signature change,
  generic slot headers, merged group-header row, positional column-math
  helpers shared with `core/stakeholder_review.py`.
- Modify: `core/cli.py` — `--reviewer-slots` replaces `--stakeholder`.
- Modify: `core/stakeholder_review.py` — `merge`/`validate_workbook`/
  `populate` rework to positional addressing; new unclaimed-slot check.
- Modify: `tests/test_stakeholder_workbook.py` (existing file, migrated
  and extended)
- Modify: `tests/test_stakeholder_review.py` (existing file, migrated
  and extended; one obsolete test removed)
- Modify: `tests/test_cli_stakeholder_review.py` (existing file,
  migrated)

---

### Task 1: `generate_workbook` — reviewer slots and the merged group-header row

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Modify: `tests/test_stakeholder_workbook.py` (full-file migration)

**Interfaces:**
- Produces (all used by Task 3's rework of `core/stakeholder_review.py`,
  which imports them):
  - `_REVIEWER_SLOT_SUB_HEADERS: list[str]` = `["Score", "Dispute?", "Rationale"]`
  - `_reviewer_slot_headers(reviewer_slots: int) -> list[str]`
  - `_reviewer_slot_columns(reviewer_slots: int) -> list[tuple[int, int, int]]`
    — 1-indexed `(score_col, dispute_col, rationale_col)` per slot.
  - `_reviewer_slot_count_from_headers(headers: list[str]) -> int` —
    derives slot count from an arbitrary header row read back from a
    file (used by `core/stakeholder_review.py`, which doesn't know
    `reviewer_slots` ahead of time).
  - `_unclaimed_reviewer_label(slot_number: int) -> str` — returns
    `f"Reviewer {slot_number}"`, the exact placeholder text, shared so
    Task 4's validate check compares against the same string this task
    writes.
  - `_all_headers(reviewer_slots: int) -> list[str]` — signature changed
    from taking a stakeholders list to taking an int.
  - `generate_workbook(..., reviewer_slots: int = 3, ...)` — signature
    changed; the `stakeholders` parameter no longer exists.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_stakeholder_workbook.py` with:

```python
from pathlib import Path

from openpyxl import load_workbook

from core.models import (
    Confidence,
    Criterion,
    CriteriaTaxonomy,
    CriterionResearchCache,
    ScoreEntry,
    Vendor,
    VendorResearchCache,
    VendorSource,
)
from openpyxl.utils import get_column_letter

from core.render.stakeholder_workbook import (
    _all_headers,
    _column_index,
    _EXEC_LEGEND_FIRST_ROW,
    _EXEC_LEGEND_HEADER_ROW,
    _EXEC_LEGEND_LINES_TEMPLATE,
    _reviewer_slot_columns,
    _rollup_row_numbers,
    compute_priority_order,
    EXEC_TABLE_FIRST_DATA_ROW,
    EXEC_TABLE_HEADER_ROW,
    generate_workbook,
)


def _taxonomy():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="low-weight", category="Cat", name="Low Weight", description="d", weight=5, rubric="r"),
            Criterion(id="high-weight-confident", category="Cat", name="High Confident", description="d", weight=20, rubric="r"),
            Criterion(id="high-weight-shaky", category="Cat", name="High Shaky", description="d", weight=20, rubric="r"),
        ]
    )


def _vendor():
    vendor = Vendor(id="v1", name="V1", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="low-weight", score=5.0, evidence="e", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="high-weight-confident", score=4.5, evidence="e", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="high-weight-shaky", score=2.0, evidence="e", confidence=Confidence.PAPER))
    return vendor


def test_priority_order_sorts_by_weight_then_needs_attention():
    taxonomy = _taxonomy()
    vendor = _vendor()
    cache = VendorResearchCache(vendor_id="v1")
    order = compute_priority_order(taxonomy, vendor, cache)
    # both weight-20 criteria outrank the weight-5 one; within the
    # weight-20 band, the low-scoring (<=2.5) one sorts first
    assert order == ["high-weight-shaky", "high-weight-confident", "low-weight"]


def test_priority_order_pulls_up_gap_checked_criteria_even_with_high_score():
    taxonomy = _taxonomy()
    vendor = _vendor()
    vendor.scores[-1] = ScoreEntry(criterion_id="high-weight-shaky", score=4.5, evidence="e", confidence=Confidence.PAPER)
    cache = VendorResearchCache(
        vendor_id="v1",
        criteria={"high-weight-shaky": CriterionResearchCache(reviewed_by_gap_check=True)},
    )
    order = compute_priority_order(taxonomy, vendor, cache)
    assert order == ["high-weight-shaky", "high-weight-confident", "low-weight"]


def _taxonomy_two_criteria():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="Coverage One", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="DX One", description="d", weight=40, rubric="r"),
        ]
    )


def _vendor_two_criteria(vendor_id="v1", name="Vendor One"):
    vendor = Vendor(id=vendor_id, name=name, source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="ev2", confidence=Confidence.PAPER))
    return vendor


def test_generate_workbook_writes_one_sheet_per_vendor_with_headers(tmp_path):
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
    assert wb.sheetnames == ["Executive Summary", "v1"]
    ws = wb["v1"]
    header = [c.value for c in ws[3]]
    assert header[:6] == ["Criterion", "Category", "Weight", "Automated Score", "Automated Evidence", "Automated Confidence"]
    assert header.count("Score") == 2
    assert header.count("Dispute?") == 2
    assert header.count("Rationale") == 2
    assert "Resolved Score" in header
    assert "Resolved By" in header
    assert "Resolved Timestamp" in header
    assert "_criterion_id" in header


def test_generate_workbook_adds_merged_reviewer_slot_group_headers(tmp_path):
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

    slot1_score_col, _, slot1_rationale_col = slot_columns[0]
    slot1_range = f"{get_column_letter(slot1_score_col)}2:{get_column_letter(slot1_rationale_col)}2"
    assert slot1_range in [str(r) for r in ws.merged_cells.ranges]
    slot1_cell = ws.cell(row=2, column=slot1_score_col)
    assert slot1_cell.value == "Reviewer 1"
    assert slot1_cell.font.bold is True
    assert slot1_cell.fill.fgColor.rgb == "001F4E78"

    slot2_score_col, _, slot2_rationale_col = slot_columns[1]
    slot2_range = f"{get_column_letter(slot2_score_col)}2:{get_column_letter(slot2_rationale_col)}2"
    assert slot2_range in [str(r) for r in ws.merged_cells.ranges]
    assert ws.cell(row=2, column=slot2_score_col).value == "Reviewer 2"


def test_generate_workbook_with_zero_reviewer_slots_has_no_reviewer_columns(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=0,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    assert "Score" not in header
    assert "Dispute?" not in header
    assert "Rationale" not in header
    assert header[:6] == ["Criterion", "Category", "Weight", "Automated Score", "Automated Evidence", "Automated Confidence"]
    assert header[6] == "Resolved Score"


def test_generate_workbook_orders_rows_by_priority_and_fills_automated_data(tmp_path):
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
    header = [c.value for c in ws[3]]
    crit_col = header.index("Criterion") + 1
    score_col = header.index("Automated Score") + 1
    crit_id_col = header.index("_criterion_id") + 1
    # c2 (weight 40, score 2.0 <= 2.5) outranks c1 (weight 60, score 4.0)
    # under the priority rule -- wait: weight sorts first, so c1 (60)
    # comes before c2 (40) here since neither ties on weight.
    assert ws.cell(row=4, column=crit_col).value == "Coverage One"
    assert ws.cell(row=4, column=score_col).value == 4.0
    assert ws.cell(row=4, column=crit_id_col).value == "c1"
    assert ws.cell(row=5, column=crit_id_col).value == "c2"


def test_generate_workbook_marks_pending_criteria_with_placeholder_and_no_automated_data(tmp_path):
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
    score_col = header.index("Automated Score") + 1
    evidence_col = header.index("Automated Evidence") + 1
    crit_id_col = header.index("_criterion_id") + 1
    pending_col = header.index("_pending") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    assert ws.cell(row=row, column=pending_col).value == 1
    assert "Pending" in ws.cell(row=row, column=evidence_col).value
    assert ws.cell(row=row, column=score_col).value is None
    non_pending_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    assert ws.cell(row=non_pending_row, column=pending_col).value == 0


def test_generate_workbook_adds_score_data_validation_and_locks_pending_rows(tmp_path):
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
    assert len(ws.data_validations.dataValidation) >= 1
    score_col = header.index("Score") + 1
    crit_id_col = header.index("_criterion_id") + 1
    pending_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    non_pending_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    assert ws.cell(row=pending_row, column=score_col).protection.locked is True
    assert ws.cell(row=non_pending_row, column=score_col).protection.locked is False
    assert ws.protection.sheet is True


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


def test_generate_workbook_writes_delta_formula_and_partial_completeness_total(tmp_path):
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
    delta_col = header.index("Automated vs. Resolved Delta") + 1
    crit_id_col = header.index("_criterion_id") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    delta_formula = ws.cell(row=row, column=delta_col).value
    assert delta_formula.startswith("=IF(ISBLANK(")

    total_row = ws.cell(row=ws.max_row, column=1).value
    assert total_row == "Weighted Total"
    total_score_cell = ws.cell(row=ws.max_row, column=header.index("Automated Score") + 1).value
    assert total_score_cell.startswith("=")
    assert "available points" in total_score_cell


def test_generate_workbook_applies_column_widths_freeze_panes_and_header_style(tmp_path):
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
    assert ws.freeze_panes == "D4"
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


def test_generate_workbook_applies_number_formats_banding_border_and_tab_color(tmp_path):
    from core.render.stakeholder_workbook import FIRST_DATA_ROW, _TAB_COLOR_PALETTE

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


def test_generate_workbook_adds_dispute_dropdown(tmp_path):
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
    header = [c.value for c in ws[3]]
    dispute_col_letter = get_column_letter(header.index("Dispute?") + 1)
    dispute_dvs = [dv for dv in ws.data_validations.dataValidation if dv.formula1 == '"Yes"']
    assert len(dispute_dvs) == 1
    assert f"{dispute_col_letter}4" in str(dispute_dvs[0].sqref)


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
        reviewer_slots=1,
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
    vendor_headers = _all_headers(1)
    weight_col = get_column_letter(_column_index(vendor_headers, "Weight"))
    evidence_col = get_column_letter(_column_index(vendor_headers, "Automated Evidence"))
    score_col = get_column_letter(_column_index(vendor_headers, "Automated Score"))

    coverage_row = category_rows["Coverage"]
    expected_coverage_formula = (
        f"=IF('a'!{evidence_col}{coverage_row}=0,\"Pending\","
        f"'a'!{weight_col}{coverage_row}/'a'!{evidence_col}{coverage_row}*5)"
    )
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=2).value == expected_coverage_formula

    expected_avg_formula = (
        f"=IF('a'!{evidence_col}{weighted_total_row}=0,\"Pending\","
        f"'a'!{weight_col}{weighted_total_row}/'a'!{evidence_col}{weighted_total_row}*5)"
    )
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=4).value == expected_avg_formula
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=5).value == f"='a'!{score_col}{weighted_total_row}"


def test_generate_workbook_executive_summary_ranks_by_normalized_average_not_raw_achieved_points(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor_x = Vendor(id="x", name="Vendor X", source=VendorSource.DISCOVERED)
    vendor_x.scores.append(ScoreEntry(criterion_id="c1", score=5.0, evidence="e", confidence=Confidence.PAPER))
    vendor_x.scores.append(ScoreEntry(criterion_id="c2", score=1.0, evidence="e", confidence=Confidence.PAPER))
    vendor_y = Vendor(id="y", name="Vendor Y", source=VendorSource.DISCOVERED)
    vendor_y.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="e", confidence=Confidence.PAPER))
    vendor_y.scores.append(ScoreEntry(criterion_id="c2", score=4.0, evidence="e", confidence=Confidence.PAPER))

    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor_y, vendor_x],
        reviewer_slots=1,
        pending_criteria={"x": {"c2"}},
        research_caches={
            "x": VendorResearchCache(vendor_id="x"),
            "y": VendorResearchCache(vendor_id="y"),
        },
        out_path=out_path,
    )

    ws = load_workbook(out_path)["Executive Summary"]
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1).value == "Vendor X"
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW + 1, column=1).value == "Vendor Y"


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
        reviewer_slots=1,
        pending_criteria={"b": {"c1", "c2"}},
        research_caches={
            "a": VendorResearchCache(vendor_id="a"),
            "b": VendorResearchCache(vendor_id="b"),
        },
        out_path=out_path,
    )

    ws = load_workbook(out_path)["Executive Summary"]
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1).value == "Vendor A"
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW + 1, column=1).value == "Vendor B"


def test_generate_workbook_executive_summary_includes_bar_chart(tmp_path):
    from openpyxl.chart import BarChart

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
    assert len(ws._charts) == 1
    assert isinstance(ws._charts[0], BarChart)


def test_generate_workbook_freeze_panes_include_weight_column(tmp_path):
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
    assert ws.freeze_panes == "D4"


def test_generate_workbook_wraps_evidence_and_rationale_text(tmp_path):
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
    header = [c.value for c in ws[3]]
    evidence_col = header.index("Automated Evidence") + 1
    rationale_col = header.index("Rationale") + 1
    score_col = header.index("Automated Score") + 1

    assert ws.cell(row=4, column=evidence_col).alignment.wrap_text is True
    assert ws.cell(row=4, column=rationale_col).alignment.wrap_text is True
    assert ws.cell(row=4, column=score_col).alignment.wrap_text is not True
    assert ws.row_dimensions[4].height is None


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
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
        top_tier_count=2,
    )
    ws = load_workbook(out_path)["v1"]
    assert ws.cell(row=4, column=1).fill.fgColor.rgb == "00FFF2CC"  # tier, even (i=0)
    assert ws.cell(row=5, column=1).fill.fgColor.rgb == "00F9E79F"  # tier, odd (i=1)
    assert ws.cell(row=6, column=1).fill.fgColor.rgb == "00000000"  # non-tier, even (i=2) -- no fill
    assert ws.cell(row=7, column=1).fill.fgColor.rgb == "00F2F2F2"  # non-tier, odd (i=3) -- banded


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
        reviewer_slots=1,
        pending_criteria={},
        research_caches={
            "a": VendorResearchCache(vendor_id="a"),
            "b": VendorResearchCache(vendor_id="b"),
        },
        out_path=out_path,
    )

    ws = load_workbook(out_path)["Executive Summary"]
    assert ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1).value == "Vendor A"
    top_row_cell = ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW, column=1)
    assert top_row_cell.font.bold is True
    assert top_row_cell.fill.fgColor.rgb == "00FFF2CC"

    second_row_cell = ws.cell(row=EXEC_TABLE_FIRST_DATA_ROW + 1, column=1)
    assert second_row_cell.value == "Vendor B"
    assert second_row_cell.font.bold is not True
    assert second_row_cell.fill.fgColor.rgb == "00000000"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: FAIL — `TypeError: generate_workbook() got an unexpected
keyword argument 'reviewer_slots'` (the source still expects
`stakeholders`)

- [ ] **Step 3: Write minimal implementation**

In `core/render/stakeholder_workbook.py`, replace the existing
`stakeholder_headers` function:

```python
def stakeholder_headers(stakeholders: list[tuple[str | None, str]]) -> list[str]:
    headers: list[str] = []
    for name, role in stakeholders:
        label = f"{name} ({role})" if name else role
        headers += [f"{label} Score", f"{label} Dispute?", f"{label} Rationale"]
    return headers
```

with:

```python
_REVIEWER_SLOT_SUB_HEADERS = ["Score", "Dispute?", "Rationale"]


def _reviewer_slot_headers(reviewer_slots: int) -> list[str]:
    return _REVIEWER_SLOT_SUB_HEADERS * reviewer_slots


def _reviewer_slot_columns(reviewer_slots: int) -> list[tuple[int, int, int]]:
    base = len(_BASE_HEADERS)
    return [
        (base + i * 3 + 1, base + i * 3 + 2, base + i * 3 + 3)
        for i in range(reviewer_slots)
    ]


def _reviewer_slot_count_from_headers(headers: list[str]) -> int:
    count = 0
    idx = len(_BASE_HEADERS)
    while idx + 2 < len(headers) and headers[idx:idx + 3] == _REVIEWER_SLOT_SUB_HEADERS:
        count += 1
        idx += 3
    return count


def _unclaimed_reviewer_label(slot_number: int) -> str:
    return f"Reviewer {slot_number}"


def _write_reviewer_slot_group_headers(ws, reviewer_slots: int) -> None:
    for i, (score_col, _dispute_col, rationale_col) in enumerate(_reviewer_slot_columns(reviewer_slots), start=1):
        ws.merge_cells(start_row=2, start_column=score_col, end_row=2, end_column=rationale_col)
        anchor = ws.cell(row=2, column=score_col, value=_unclaimed_reviewer_label(i))
        anchor.font = _HEADER_FONT
        anchor.fill = _HEADER_FILL
        anchor.border = _HEADER_BORDER
        anchor.alignment = _HEADER_ALIGNMENT
```

Replace:

```python
def _all_headers(stakeholders: list[tuple[str | None, str]]) -> list[str]:
    return _BASE_HEADERS + stakeholder_headers(stakeholders) + _RESOLUTION_HEADERS + _HIDDEN_HEADERS
```

with:

```python
def _all_headers(reviewer_slots: int) -> list[str]:
    return _BASE_HEADERS + _reviewer_slot_headers(reviewer_slots) + _RESOLUTION_HEADERS + _HIDDEN_HEADERS
```

In `generate_workbook`'s signature, replace:

```python
def generate_workbook(
    taxonomy: CriteriaTaxonomy,
    vendors: list[Vendor],
    stakeholders: list[tuple[str | None, str]],
    pending_criteria: dict[str, set[str]],
    research_caches: dict[str, VendorResearchCache],
    out_path: Path,
    top_tier_count: int = 10,
) -> None:
```

with:

```python
def generate_workbook(
    taxonomy: CriteriaTaxonomy,
    vendors: list[Vendor],
    reviewer_slots: int,
    pending_criteria: dict[str, set[str]],
    research_caches: dict[str, VendorResearchCache],
    out_path: Path,
    top_tier_count: int = 10,
) -> None:
```

Still inside `generate_workbook`, replace:

```python
    headers = _all_headers(stakeholders)
```

with:

```python
    headers = _all_headers(reviewer_slots)
```

Replace:

```python
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=HEADER_ROW, column=col_idx)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.border = _HEADER_BORDER
            cell.alignment = _HEADER_ALIGNMENT
```

with:

```python
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=HEADER_ROW, column=col_idx)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.border = _HEADER_BORDER
            cell.alignment = _HEADER_ALIGNMENT
        _write_reviewer_slot_group_headers(ws, reviewer_slots)
```

Replace:

```python
        score_cols = [
            _column_index(headers, h) for h in stakeholder_headers(stakeholders) if h.endswith(" Score")
        ] + [_column_index(headers, "Resolved Score")]
```

with:

```python
        slot_columns = _reviewer_slot_columns(reviewer_slots)
        score_cols = [score_col for score_col, _, _ in slot_columns] + [_column_index(headers, "Resolved Score")]
```

Replace:

```python
        dispute_cols = [
            _column_index(headers, h) for h in stakeholder_headers(stakeholders) if h.endswith(" Dispute?")
        ]
```

with:

```python
        dispute_cols = [dispute_col for _, dispute_col, _ in slot_columns]
```

Replace:

```python
            editable_non_score_cols = [
                _column_index(headers, h) for h in stakeholder_headers(stakeholders) if not h.endswith(" Score")
            ] + [_column_index(headers, h) for h in ("Resolved By", "Resolved Timestamp")]
```

with:

```python
            editable_non_score_cols = [
                col for _, dispute_col, rationale_col in slot_columns for col in (dispute_col, rationale_col)
            ] + [_column_index(headers, h) for h in ("Resolved By", "Resolved Timestamp")]
```

Finally, in `_add_executive_summary_sheet`'s only caller (inside
`generate_workbook`), the call already passes `headers` (a plain list,
unaffected by this rename) — no change needed there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: replace named stakeholders with generic reviewer slots"
```

---

### Task 2: CLI — `--reviewer-slots` replaces `--stakeholder`

**Files:**
- Modify: `core/cli.py`
- Modify: `tests/test_cli_stakeholder_review.py`

**Interfaces:**
- Consumes: `generate_workbook(..., reviewer_slots: int, ...)` (Task 1).
- Produces: no new interfaces — this is the CLI's only consumer of the
  changed signature.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_cli_stakeholder_review.py`
with:

```python
import yaml
from openpyxl import load_workbook
from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()


def _setup_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "candidates").mkdir(parents=True)
    (tmp_path / "data" / "research-cache").mkdir(parents=True)
    criteria = {
        "version": 1,
        "criteria": [
            {"id": "c1", "category": "Coverage", "name": "Coverage One", "description": "d", "weight": 100.0, "rubric": "r"},
        ],
    }
    (tmp_path / "data" / "criteria.yaml").write_text(yaml.safe_dump(criteria))
    vendor = {
        "id": "v1",
        "name": "Vendor One",
        "source": "discovered",
        "status": "finalist",
        "scores": [{"criterion_id": "c1", "score": 4.0, "evidence": "ev1", "confidence": "paper", "timestamp": "2026-01-01T00:00:00"}],
        "hands_on_results": [],
        "observations": [],
    }
    (tmp_path / "data" / "candidates" / "v1.yaml").write_text(yaml.safe_dump(vendor))


def test_cli_stakeholder_review_generate_creates_workbook(tmp_path, monkeypatch):
    _setup_repo(tmp_path, monkeypatch)
    out_path = tmp_path / "review.xlsx"
    result = runner.invoke(
        app,
        [
            "stakeholder-review", "generate",
            "--vendor-id", "v1",
            "--reviewer-slots", "2",
            "--out", str(out_path),
        ],
    )
    assert result.exit_code == 0, result.output
    wb = load_workbook(out_path)
    assert "v1" in wb.sheetnames
    ws = wb["v1"]
    header = [c.value for c in ws[3]]
    assert header.count("Score") == 2


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


def test_cli_stakeholder_review_generate_fails_on_unscored_criterion(tmp_path, monkeypatch):
    _setup_repo(tmp_path, monkeypatch)
    extra_criteria = yaml.safe_load((tmp_path / "data" / "criteria.yaml").read_text())
    extra_criteria["criteria"].append(
        {"id": "c2", "category": "DX", "name": "DX One", "description": "d", "weight": 0.0, "rubric": "r"}
    )
    (tmp_path / "data" / "criteria.yaml").write_text(yaml.safe_dump(extra_criteria))
    result = runner.invoke(
        app,
        [
            "stakeholder-review", "generate",
            "--vendor-id", "v1",
            "--out", str(tmp_path / "review.xlsx"),
        ],
    )
    assert result.exit_code == 1
    assert "error:" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_stakeholder_review.py -v`
Expected: FAIL — `Error: No such option: --reviewer-slots` (CLI still
expects `--stakeholder`)

- [ ] **Step 3: Write minimal implementation**

In `core/cli.py`, remove the `_parse_stakeholder` function entirely (no
longer needed — there's nothing to parse, `--reviewer-slots` is already
an int):

```python
def _parse_stakeholder(raw: str) -> tuple[str | None, str]:
    name, _, role = raw.partition(":")
    return (name or None, role)
```

In `stakeholder_review_generate`, replace:

```python
@stakeholder_review_app.command("generate")
def stakeholder_review_generate(
    vendor_id: list[str] = typer.Option(..., "--vendor-id"),
    stakeholder: list[str] = typer.Option(..., "--stakeholder"),
    pending_criteria: list[str] = typer.Option([], "--pending-criteria"),
    out: Path = typer.Option(...),
) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = []
    for vid in vendor_id:
        path = storage.vendor_path(CANDIDATES_DIR, vid)
        if not path.exists():
            typer.echo(f"error: vendor '{vid}' not found")
            raise typer.Exit(code=1)
        vendor = storage.load_vendor(path)
        for criterion in taxonomy.criteria:
            if vendor.score_for(criterion.id) is None:
                typer.echo(f"error: vendor '{vid}' has no score for criterion '{criterion.id}'")
                raise typer.Exit(code=1)
        vendors.append(vendor)

    stakeholders = [_parse_stakeholder(s) for s in stakeholder]
    pending = _parse_pending_criteria(pending_criteria)
    research_caches = {
        v.id: storage.load_research_cache(storage.research_cache_path(RESEARCH_CACHE_DIR, v.id), v.id)
        for v in vendors
    }
    generate_workbook(taxonomy, vendors, stakeholders, pending, research_caches, out)
    typer.echo(f"generated stakeholder review workbook at {out}")
```

with:

```python
@stakeholder_review_app.command("generate")
def stakeholder_review_generate(
    vendor_id: list[str] = typer.Option(..., "--vendor-id"),
    reviewer_slots: int = typer.Option(3, "--reviewer-slots"),
    pending_criteria: list[str] = typer.Option([], "--pending-criteria"),
    out: Path = typer.Option(...),
) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = []
    for vid in vendor_id:
        path = storage.vendor_path(CANDIDATES_DIR, vid)
        if not path.exists():
            typer.echo(f"error: vendor '{vid}' not found")
            raise typer.Exit(code=1)
        vendor = storage.load_vendor(path)
        for criterion in taxonomy.criteria:
            if vendor.score_for(criterion.id) is None:
                typer.echo(f"error: vendor '{vid}' has no score for criterion '{criterion.id}'")
                raise typer.Exit(code=1)
        vendors.append(vendor)

    pending = _parse_pending_criteria(pending_criteria)
    research_caches = {
        v.id: storage.load_research_cache(storage.research_cache_path(RESEARCH_CACHE_DIR, v.id), v.id)
        for v in vendors
    }
    generate_workbook(taxonomy, vendors, reviewer_slots, pending, research_caches, out)
    typer.echo(f"generated stakeholder review workbook at {out}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_stakeholder_review.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/cli.py tests/test_cli_stakeholder_review.py
git commit -m "feat: replace --stakeholder CLI flag with --reviewer-slots"
```

---

### Task 3: `core/stakeholder_review.py` — positional addressing for `merge`, `validate_workbook`, `populate`

**Files:**
- Modify: `core/stakeholder_review.py`
- Modify: `tests/test_stakeholder_review.py` (full-file migration; one
  obsolete test removed)

**Interfaces:**
- Consumes: `_reviewer_slot_columns`, `_reviewer_slot_count_from_headers`
  (Task 1) from `core.render.stakeholder_workbook`.
- Produces: `merge`/`validate_workbook`/`populate` keep their existing
  signatures (`merge(master_path, from_path) -> str`,
  `validate_workbook(file_path) -> list[str]`, `populate(vendor,
  file_path) -> str`) — only their internal column-addressing changes.
  `merge`'s returned summary string drops the trailing `unrecognized:
  [...]` segment (there's no more concept of an unrecognized stakeholder
  column under positional addressing — master and every returned copy
  always share the identical column layout, since both originate from
  the same `generate` call).

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_stakeholder_review.py` with:

```python
from datetime import date

from openpyxl import load_workbook
from openpyxl.styles import Protection

from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorResearchCache, VendorSource
from core.render.stakeholder_workbook import HEADER_ROW, _reviewer_slot_columns, generate_workbook
from core.stakeholder_review import _column_map, merge, populate, snapshot, validate_workbook


def _taxonomy():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="Coverage One", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="DX One", description="d", weight=40, rubric="r"),
        ]
    )


def _vendor_with_hands_on_c2():
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=1.0, evidence="paper guess", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=3.5, evidence="hands-on: 7/10 detected", confidence=Confidence.HANDS_ON))
    return vendor


def _generate_with_c2_pending(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy()
    vendor = _vendor_with_hands_on_c2()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    return out_path


def _row_for(ws, cols, criterion_id):
    crit_col = cols["_criterion_id"]
    for r in range(4, ws.max_row + 1):
        if ws[f"{crit_col}{r}"].value == criterion_id:
            return r
    raise AssertionError(f"row for {criterion_id} not found")


def test_populate_fills_pending_row_and_unlocks_it(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    vendor = _vendor_with_hands_on_c2()
    summary = populate(vendor, out_path)
    assert "populated 1" in summary

    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    score_col = header.index("Automated Score") + 1
    evidence_col = header.index("Automated Evidence") + 1
    pending_col = header.index("_pending") + 1
    stakeholder_score_col = header.index("Score") + 1
    stakeholder_dispute_col = header.index("Dispute?") + 1
    stakeholder_rationale_col = header.index("Rationale") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    assert ws.cell(row=row, column=score_col).value == 3.5
    assert ws.cell(row=row, column=evidence_col).value == "hands-on: 7/10 detected"
    assert ws.cell(row=row, column=pending_col).value == 0
    assert ws.cell(row=row, column=stakeholder_score_col).protection.locked is False
    assert ws.cell(row=row, column=stakeholder_dispute_col).protection.locked is False
    assert ws.cell(row=row, column=stakeholder_rationale_col).protection.locked is False


def test_populate_unlocks_every_reviewer_slot_not_only_the_last(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy()
    vendor = _vendor_with_hands_on_c2()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=3,
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    populate(vendor, out_path)

    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    for score_col, dispute_col, rationale_col in _reviewer_slot_columns(3):
        assert ws.cell(row=row, column=score_col).protection.locked is False
        assert ws.cell(row=row, column=dispute_col).protection.locked is False
        assert ws.cell(row=row, column=rationale_col).protection.locked is False


def test_populate_leaves_stakeholder_entered_cells_untouched(tmp_path):
    # A stakeholder may pre-fill a Dispute/Rationale note on a PENDING row
    # (e.g. criterion c2) before dast-scan results land. populate() must
    # fill in that same row's Automated Score/Evidence without disturbing
    # the stakeholder-entered cell.
    out_path = _generate_with_c2_pending(tmp_path)
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    rationale_col = header.index("Rationale") + 1
    score_col = header.index("Automated Score") + 1
    evidence_col = header.index("Automated Evidence") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    ws.cell(row=row, column=rationale_col).value = "pre-filled before scan results landed"
    wb = ws.parent
    wb.save(out_path)

    vendor = _vendor_with_hands_on_c2()
    populate(vendor, out_path)

    ws2 = load_workbook(out_path)["v1"]
    assert ws2.cell(row=row, column=rationale_col).value == "pre-filled before scan results landed"
    assert ws2.cell(row=row, column=score_col).value == 3.5
    assert ws2.cell(row=row, column=evidence_col).value == "hands-on: 7/10 detected"


def test_populate_is_a_no_op_when_vendor_has_no_pending_rows(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy()
    vendor = _vendor_with_hands_on_c2()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=1,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    summary = populate(vendor, out_path)
    assert "populated 0" in summary


def _generate_two_reviewer_slots(tmp_path, filename="master.xlsx"):
    out_path = tmp_path / filename
    taxonomy = _taxonomy()
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="ev2", confidence=Confidence.PAPER))
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        reviewer_slots=2,
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    return out_path


def _slot_letters(slot_number: int) -> tuple[str, str, str]:
    from openpyxl.utils import get_column_letter

    score_col, dispute_col, rationale_col = _reviewer_slot_columns(2)[slot_number - 1]
    return get_column_letter(score_col), get_column_letter(dispute_col), get_column_letter(rationale_col)


def test_merge_fills_blank_master_cells_from_a_valid_returned_copy(tmp_path):
    master_path = _generate_two_reviewer_slots(tmp_path, "master.xlsx")
    copy_path = _generate_two_reviewer_slots(tmp_path, "copy.xlsx")
    score_letter, _, rationale_letter = _slot_letters(1)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{score_letter}{row}"] = 4.5
    copy_ws[f"{rationale_letter}{row}"] = "Confirmed with vendor demo"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "merged 1 cell" in summary

    master_ws = load_workbook(master_path)["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    assert master_ws[f"{score_letter}{mrow}"].value == 4.5


def test_merge_flags_conflict_without_overwriting(tmp_path):
    master_path = _generate_two_reviewer_slots(tmp_path, "master.xlsx")
    copy_path = _generate_two_reviewer_slots(tmp_path, "copy.xlsx")
    score_letter, _, _ = _slot_letters(1)

    master_wb = load_workbook(master_path)
    master_ws = master_wb["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    master_ws[f"{score_letter}{mrow}"] = 3.0
    master_wb.save(master_path)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{score_letter}{row}"] = 4.5
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "1 conflict" in summary
    assert load_workbook(master_path)["v1"][f"{score_letter}{mrow}"].value == 3.0


def test_merge_addresses_each_slot_independently(tmp_path):
    master_path = _generate_two_reviewer_slots(tmp_path, "master.xlsx")
    copy_path = _generate_two_reviewer_slots(tmp_path, "copy.xlsx")
    slot1_score, _, _ = _slot_letters(1)
    slot2_score, _, _ = _slot_letters(2)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{slot1_score}{row}"] = 4.5
    copy_ws[f"{slot2_score}{row}"] = 3.5
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "merged 2 cell" in summary

    master_ws = load_workbook(master_path)["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    assert master_ws[f"{slot1_score}{mrow}"].value == 4.5
    assert master_ws[f"{slot2_score}{mrow}"].value == 3.5


def test_merge_flags_conflict_on_rationale_alone_when_score_is_blank(tmp_path):
    master_path = _generate_two_reviewer_slots(tmp_path, "master.xlsx")
    copy_path = _generate_two_reviewer_slots(tmp_path, "copy.xlsx")
    _, _, rationale_letter = _slot_letters(1)

    master_wb = load_workbook(master_path)
    master_ws = master_wb["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    master_ws[f"{rationale_letter}{mrow}"] = "already had a note"
    master_wb.save(master_path)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{rationale_letter}{row}"] = "a totally different note"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "1 conflict" in summary

    master_after = load_workbook(master_path)["v1"]
    assert master_after[f"{rationale_letter}{mrow}"].value == "already had a note"


def test_merge_flags_invalid_score_and_dispute_without_rationale(tmp_path):
    master_path = _generate_two_reviewer_slots(tmp_path, "master.xlsx")
    copy_path = _generate_two_reviewer_slots(tmp_path, "copy.xlsx")
    score_letter, dispute_letter, _ = _slot_letters(1)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{score_letter}{row}"] = 9.0
    row2 = _row_for(copy_ws, cols, "c2")
    copy_ws[f"{dispute_letter}{row2}"] = "Y"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "2 invalid" in summary


def test_validate_workbook_flags_dispute_without_rationale_and_invalid_score(tmp_path):
    file_path = _generate_two_reviewer_slots(tmp_path, "review.xlsx")
    slot1_score, slot1_dispute, _ = _slot_letters(1)
    slot2_score, _, _ = _slot_letters(2)

    wb = load_workbook(file_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c1")
    ws[f"{slot1_dispute}{row}"] = "Y"
    row2 = _row_for(ws, cols, "c2")
    ws[f"{slot2_score}{row2}"] = 9.0
    wb.save(file_path)

    issues = validate_workbook(file_path)
    assert len(issues) == 2


def test_validate_workbook_returns_empty_list_for_clean_file(tmp_path):
    file_path = _generate_two_reviewer_slots(tmp_path, "review.xlsx")
    assert validate_workbook(file_path) == []


def test_validate_workbook_flags_pending_row_with_data_entered(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    from openpyxl.utils import get_column_letter

    score_col, _, _ = _reviewer_slot_columns(1)[0]
    score_letter = get_column_letter(score_col)

    wb = load_workbook(out_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c2")
    # Tamper: enter a score on the pending row without touching its lock.
    ws[f"{score_letter}{row}"] = 3.0
    wb.save(out_path)

    issues = validate_workbook(out_path)
    assert any("tampered" in issue for issue in issues)


def test_validate_workbook_flags_pending_row_with_lock_removed(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    from openpyxl.utils import get_column_letter

    score_col, _, _ = _reviewer_slot_columns(1)[0]
    score_letter = get_column_letter(score_col)

    wb = load_workbook(out_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c2")
    # Tamper: remove the lock but leave the cell blank (no data entered).
    ws[f"{score_letter}{row}"].protection = Protection(locked=False)
    wb.save(out_path)

    issues = validate_workbook(out_path)
    assert any("tampered" in issue for issue in issues)


def test_validate_workbook_does_not_flag_untouched_pending_row(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    issues = validate_workbook(out_path)
    assert not any("tampered" in issue for issue in issues)


def test_validate_workbook_flags_pending_row_with_resolved_score_entered(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    wb = load_workbook(out_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c2")
    # Tamper: enter a Resolved Score on the pending row without touching its lock.
    ws[f"{cols['Resolved Score']}{row}"] = 3.0
    wb.save(out_path)

    issues = validate_workbook(out_path)
    assert any("tampered" in issue for issue in issues)


def test_validate_workbook_flags_pending_row_with_resolved_score_lock_removed(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    wb = load_workbook(out_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c2")
    # Tamper: remove the lock on Resolved Score but leave the cell blank.
    ws[f"{cols['Resolved Score']}{row}"].protection = Protection(locked=False)
    wb.save(out_path)

    issues = validate_workbook(out_path)
    assert any("tampered" in issue for issue in issues)


def test_snapshot_copies_file_into_archive_dir(tmp_path):
    file_path = _generate_two_reviewer_slots(tmp_path, "review.xlsx")
    archive_dir = tmp_path / "archive"
    result = snapshot(file_path, "v1", archive_dir, label="baseline")
    assert result.exists()
    assert result.parent == archive_dir
    assert "v1" in result.name
    assert "baseline" in result.name
    assert result.read_bytes() == file_path.read_bytes()


def test_merge_accepts_case_insensitive_dispute_yes_value(tmp_path):
    master_path = _generate_two_reviewer_slots(tmp_path, "master.xlsx")
    copy_path = _generate_two_reviewer_slots(tmp_path, "copy.xlsx")
    _, dispute_letter, rationale_letter = _slot_letters(1)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{dispute_letter}{row}"] = "yes"
    copy_ws[f"{rationale_letter}{row}"] = "Confirmed with vendor demo"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "merged 1 cell" in summary

    master_ws = load_workbook(master_path)["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    assert master_ws[f"{dispute_letter}{mrow}"].value == "yes"


def test_merge_flags_mixed_case_dispute_without_rationale_as_invalid(tmp_path):
    master_path = _generate_two_reviewer_slots(tmp_path, "master.xlsx")
    copy_path = _generate_two_reviewer_slots(tmp_path, "copy.xlsx")
    _, dispute_letter, _ = _slot_letters(1)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row2 = _row_for(copy_ws, cols, "c2")
    copy_ws[f"{dispute_letter}{row2}"] = "Yes"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "1 invalid" in summary


def test_validate_workbook_flags_lowercase_dispute_without_rationale(tmp_path):
    file_path = _generate_two_reviewer_slots(tmp_path, "review.xlsx")
    _, dispute_letter, _ = _slot_letters(1)

    wb = load_workbook(file_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c1")
    ws[f"{dispute_letter}{row}"] = "yes"
    wb.save(file_path)

    issues = validate_workbook(file_path)
    assert len(issues) == 1
    assert "disputed with no rationale" in issues[0]
```

Note: the previous `test_merge_flags_unrecognized_stakeholder_column_and_does_not_write_it`
test is intentionally **removed**, not migrated — its entire premise
(detecting a returned copy's header text that doesn't match any known
master stakeholder) no longer applies once addressing is positional:
master and every returned copy always originate from the same
`generate` call, so there is nothing to "recognize" by header text
anymore.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: FAIL — multiple failures, since `core/stakeholder_review.py`
still expects unique header text per stakeholder (`KeyError` on
`cols["Score"]` returning the wrong/only-last-slot column, or similar)

- [ ] **Step 3: Write minimal implementation**

Replace the entire contents of `core/stakeholder_review.py` with:

```python
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Protection
from openpyxl.utils import get_column_letter

from .models import Vendor
from .render.stakeholder_workbook import (
    FIRST_DATA_ROW,
    HEADER_ROW,
    SCORE_VALUES,
    _reviewer_slot_columns,
    _reviewer_slot_count_from_headers,
)

_DISPUTE_YES_VALUES = {"y", "yes"}


def _is_dispute_yes(value) -> bool:
    return isinstance(value, str) and value.strip().lower() in _DISPUTE_YES_VALUES


def _column_map(ws) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for cell in ws[HEADER_ROW]:
        if cell.value:
            mapping[cell.value] = cell.column_letter
    return mapping


def _slot_letters(ws) -> list[tuple[str, str, str]]:
    headers = [c.value for c in ws[HEADER_ROW]]
    reviewer_slots = _reviewer_slot_count_from_headers(headers)
    return [
        (get_column_letter(score_col), get_column_letter(dispute_col), get_column_letter(rationale_col))
        for score_col, dispute_col, rationale_col in _reviewer_slot_columns(reviewer_slots)
    ]


def populate(vendor: Vendor, file_path: Path) -> str:
    wb = load_workbook(file_path)
    sheet_name = vendor.id[:31]
    if sheet_name not in wb.sheetnames:
        return f"error: vendor '{vendor.id}' has no sheet in {file_path}"
    ws = wb[sheet_name]
    cols = _column_map(ws)
    crit_id_col = cols["_criterion_id"]
    pending_col = cols["_pending"]
    score_col = cols["Automated Score"]
    evidence_col = cols["Automated Evidence"]
    confidence_col = cols["Automated Confidence"]
    slot_letters = _slot_letters(ws)

    filled = 0
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        criterion_id = ws[f"{crit_id_col}{row}"].value
        if not criterion_id:
            continue
        if ws[f"{pending_col}{row}"].value != 1:
            continue
        entry = vendor.score_for(criterion_id)
        if entry is None:
            continue
        ws[f"{score_col}{row}"] = entry.score
        ws[f"{evidence_col}{row}"] = entry.evidence
        ws[f"{confidence_col}{row}"] = entry.confidence.value
        ws[f"{pending_col}{row}"] = 0
        for score_letter, dispute_letter, rationale_letter in slot_letters:
            for letter in (score_letter, dispute_letter, rationale_letter):
                ws[f"{letter}{row}"].protection = Protection(locked=False)
        filled += 1

    wb.save(file_path)
    return f"populated {filled} pending row(s) for '{vendor.id}'"


def _conflicts(existing, incoming) -> bool:
    return existing is not None and incoming is not None and existing != incoming


def merge(master_path: Path, from_path: Path) -> str:
    master_wb = load_workbook(master_path)
    from_wb = load_workbook(from_path)

    merged = 0
    invalid = 0
    conflicts = 0

    for sheet_name in master_wb.sheetnames:
        if sheet_name not in from_wb.sheetnames:
            continue
        m_ws = master_wb[sheet_name]
        f_ws = from_wb[sheet_name]
        m_cols = _column_map(m_ws)
        f_cols = _column_map(f_ws)

        if "_criterion_id" not in m_cols or "_criterion_id" not in f_cols:
            # Not a per-vendor rollup sheet (e.g. the Executive Summary tab).
            continue

        m_crit_col = m_cols["_criterion_id"]
        f_crit_col = f_cols["_criterion_id"]
        m_pending_col = m_cols["_pending"]

        m_row_by_crit = {
            m_ws[f"{m_crit_col}{r}"].value: r
            for r in range(FIRST_DATA_ROW, m_ws.max_row + 1)
            if m_ws[f"{m_crit_col}{r}"].value
        }
        f_row_by_crit = {
            f_ws[f"{f_crit_col}{r}"].value: r
            for r in range(FIRST_DATA_ROW, f_ws.max_row + 1)
            if f_ws[f"{f_crit_col}{r}"].value
        }

        m_slot_letters = _slot_letters(m_ws)
        f_slot_letters = _slot_letters(f_ws)
        shared_slot_count = min(len(m_slot_letters), len(f_slot_letters))

        for slot_index in range(shared_slot_count):
            score_letter, dispute_letter, rationale_letter = m_slot_letters[slot_index]
            f_score_letter, f_dispute_letter, f_rationale_letter = f_slot_letters[slot_index]
            for criterion_id, f_row in f_row_by_crit.items():
                f_score = f_ws[f"{f_score_letter}{f_row}"].value
                f_dispute = f_ws[f"{f_dispute_letter}{f_row}"].value
                f_rationale = f_ws[f"{f_rationale_letter}{f_row}"].value
                if f_score is None and f_dispute is None and f_rationale is None:
                    continue
                m_row = m_row_by_crit.get(criterion_id)
                if m_row is None or m_ws[f"{m_pending_col}{m_row}"].value == 1:
                    continue
                valid = (f_score is None or f_score in SCORE_VALUES) and (
                    not _is_dispute_yes(f_dispute) or bool(f_rationale)
                )
                if not valid:
                    invalid += 1
                    continue

                existing_score = m_ws[f"{score_letter}{m_row}"].value
                existing_dispute = m_ws[f"{dispute_letter}{m_row}"].value
                existing_rationale = m_ws[f"{rationale_letter}{m_row}"].value
                if (
                    _conflicts(existing_score, f_score)
                    or _conflicts(existing_dispute, f_dispute)
                    or _conflicts(existing_rationale, f_rationale)
                ):
                    conflicts += 1
                    continue
                m_ws[f"{score_letter}{m_row}"] = f_score
                m_ws[f"{dispute_letter}{m_row}"] = f_dispute
                m_ws[f"{rationale_letter}{m_row}"] = f_rationale
                merged += 1

    master_wb.save(master_path)
    return f"merged {merged} cell(s), {invalid} invalid, {conflicts} conflict(s)"


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
            for row in range(FIRST_DATA_ROW, ws.max_row + 1):
                criterion_id = ws[f"{crit_col}{row}"].value
                if not criterion_id:
                    continue
                score = ws[f"{score_letter}{row}"].value
                dispute = ws[f"{dispute_letter}{row}"].value
                rationale = ws[f"{rationale_letter}{row}"].value
                if score is not None and score not in SCORE_VALUES:
                    issues.append(f"{sheet_name}/{criterion_id}: Reviewer {slot_number} score {score!r} is not a valid value")
                if _is_dispute_yes(dispute) and not rationale:
                    issues.append(f"{sheet_name}/{criterion_id}: Reviewer {slot_number} disputed with no rationale")
        resolved_h = "Resolved Score"
        by_h = "Resolved By"
        ts_h = "Resolved Timestamp"
        for row in range(FIRST_DATA_ROW, ws.max_row + 1):
            criterion_id = ws[f"{crit_col}{row}"].value
            if not criterion_id:
                continue
            resolved = ws[f"{cols[resolved_h]}{row}"].value
            resolved_by = ws[f"{cols[by_h]}{row}"].value
            resolved_ts = ws[f"{cols[ts_h]}{row}"].value
            if resolved is not None and not (resolved_by and resolved_ts):
                issues.append(f"{sheet_name}/{criterion_id}: resolved score present without Resolved By/Timestamp")

        pending_col = cols["_pending"]
        for row in range(FIRST_DATA_ROW, ws.max_row + 1):
            criterion_id = ws[f"{crit_col}{row}"].value
            if not criterion_id:
                continue
            if ws[f"{pending_col}{row}"].value != 1:
                continue
            tampered = False
            for score_letter, dispute_letter, rationale_letter in slot_letters:
                for letter in (score_letter, dispute_letter, rationale_letter):
                    cell = ws[f"{letter}{row}"]
                    if cell.value is not None or cell.protection.locked is False:
                        tampered = True
                        break
                if tampered:
                    break
            if not tampered:
                for header in (resolved_h, by_h, ts_h):
                    cell = ws[f"{cols[header]}{row}"]
                    if cell.value is not None or cell.protection.locked is False:
                        tampered = True
                        break
            if tampered:
                issues.append(
                    f"{sheet_name}/{criterion_id}: pending row has been tampered with "
                    "(lock removed or data entered before Round 2)"
                )
    return issues


def snapshot(file_path: Path, vendor_id: str, archive_dir: Path, label: str | None = None) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{label}" if label else ""
    dest = archive_dir / f"{date.today().isoformat()}-{vendor_id}{suffix}.xlsx"
    shutil.copy2(file_path, dest)
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions in `test_stakeholder_workbook.py`
or `test_cli_stakeholder_review.py`

- [ ] **Step 6: Commit**

```bash
git add core/stakeholder_review.py tests/test_stakeholder_review.py
git commit -m "fix: address reviewer-slot columns positionally in merge/validate/populate"
```

---

### Task 4: `validate_workbook` — flag an unclaimed slot with data

**Files:**
- Modify: `core/stakeholder_review.py`
- Modify: `tests/test_stakeholder_review.py`

**Interfaces:**
- Consumes: `_unclaimed_reviewer_label` (Task 1) from
  `core.render.stakeholder_workbook`; `_slot_letters` (Task 3, this
  module).
- Produces: no new public names — extends `validate_workbook`'s issue
  list with one new check.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_stakeholder_review.py`:

```python
def test_validate_workbook_flags_unclaimed_slot_with_data(tmp_path):
    file_path = _generate_two_reviewer_slots(tmp_path, "review.xlsx")
    score_letter, _, _ = _slot_letters(1)

    wb = load_workbook(file_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c1")
    ws[f"{score_letter}{row}"] = 4.0
    wb.save(file_path)

    issues = validate_workbook(file_path)
    assert any("unclaimed" in issue for issue in issues)


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
    row = _row_for(ws, cols, "c1")
    ws[f"{score_letter}{row}"] = 4.0
    wb.save(file_path)

    issues = validate_workbook(file_path)
    assert not any("unclaimed" in issue for issue in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stakeholder_review.py -k unclaimed -v`
Expected: FAIL — `assert any(...)` is `False` (no unclaimed-slot check
exists yet)

- [ ] **Step 3: Write minimal implementation**

In `core/stakeholder_review.py`, add this import alongside the existing
one from `.render.stakeholder_workbook`:

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

Then, in `validate_workbook`, inside the per-slot loop (the one added in
Task 3), change:

```python
        for slot_number, (score_letter, dispute_letter, rationale_letter) in enumerate(slot_letters, start=1):
            for row in range(FIRST_DATA_ROW, ws.max_row + 1):
                criterion_id = ws[f"{crit_col}{row}"].value
                if not criterion_id:
                    continue
                score = ws[f"{score_letter}{row}"].value
                dispute = ws[f"{dispute_letter}{row}"].value
                rationale = ws[f"{rationale_letter}{row}"].value
                if score is not None and score not in SCORE_VALUES:
                    issues.append(f"{sheet_name}/{criterion_id}: Reviewer {slot_number} score {score!r} is not a valid value")
                if _is_dispute_yes(dispute) and not rationale:
                    issues.append(f"{sheet_name}/{criterion_id}: Reviewer {slot_number} disputed with no rationale")
```

to:

```python
        for slot_number, (score_letter, dispute_letter, rationale_letter) in enumerate(slot_letters, start=1):
            group_header_value = ws.cell(row=2, column=_reviewer_slot_columns(len(slot_letters))[slot_number - 1][0]).value
            slot_claimed = group_header_value != _unclaimed_reviewer_label(slot_number)
            for row in range(FIRST_DATA_ROW, ws.max_row + 1):
                criterion_id = ws[f"{crit_col}{row}"].value
                if not criterion_id:
                    continue
                score = ws[f"{score_letter}{row}"].value
                dispute = ws[f"{dispute_letter}{row}"].value
                rationale = ws[f"{rationale_letter}{row}"].value
                if score is not None and score not in SCORE_VALUES:
                    issues.append(f"{sheet_name}/{criterion_id}: Reviewer {slot_number} score {score!r} is not a valid value")
                if _is_dispute_yes(dispute) and not rationale:
                    issues.append(f"{sheet_name}/{criterion_id}: Reviewer {slot_number} disputed with no rationale")
                if not slot_claimed and any(v is not None for v in (score, dispute, rationale)):
                    issues.append(
                        f"{sheet_name}/{criterion_id}: Reviewer {slot_number} has responses but "
                        "the slot was never claimed (header still shows placeholder text)"
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions

- [ ] **Step 6: Commit**

```bash
git add core/stakeholder_review.py tests/test_stakeholder_review.py
git commit -m "feat: flag an unclaimed reviewer slot that has data entered"
```
