# Stakeholder Review Workbook — UX Polish Round 4

> Addendum to rounds 1-3 (all implemented and merged). This round starts
> from a clean revert: a prior uncommitted attempt at rounds covering the
> same ground (reviewer labels, auto-pending, hyperlinks, a Reviewers
> sheet, chart styling, row heights) made the chart and row-height issues
> worse instead of better, with no way to visually verify the fixes. That
> work was discarded (`git checkout --`) rather than debugged further, and
> this round re-derives just the 4 items still open, with root causes
> confirmed by actually rendering the file (LibreOffice headless, newly
> installed in this dev container, converting to PDF/PNG) instead of
> reasoning about OOXML chart XML blind.

## Context

Four items, against the current committed baseline (`_EXEC_LEGEND_*`
Executive Summary tab, plain per-vendor-tab `"Reviewer N - {name} -
{role/title}"` header text, no Reviewers sheet, unstyled default-size bar
chart, no explicit row heights anywhere in the file):

1. **Chart bar order is reversed vs. the ranked table.** Rendered and
   visually inspected the current chart: single legend entry, uniform bar
   color, otherwise clean — but the category (vendor) axis lists worst-to-best
   top-to-bottom, backwards from the Overview table directly above it. A
   prior attempt "fixed" this by enabling `varyColors`, adding per-point
   `dPt` colors, and flipping the wrong axis (`y_axis` instead of
   `x_axis`) — none of which addressed the actual ordering and introduced
   new overlapping text. Root cause, confirmed by rendering: only the
   category axis orientation was ever wrong.
2. **Title/header rows get clipped.** No row in this file ever gets an
   explicit height. The Executive Summary title (14pt bold) sits in an
   unset ~15pt default row — a known Excel-desktop rendering gap (row
   height isn't reliably auto-fit for programmatically-generated files).
3. **Reviewer count is capped at 5 in practice.** Not actually true —
   `--reviewer-slots N` already exists on `stakeholder-review generate`
   and is fully wired through to the workbook. Verified end-to-end with
   `N=8`. No code change; this round just confirms it.
4. **No shared reviewer roster.** Each vendor tab's reviewer-slot header
   is independently free-typed text, so a name has to be retyped
   correctly on every vendor tab, with no way to see at a glance which
   slots are claimed.

## Design

### 1. Chart bar order

One-line fix on the existing `BarChart` in `_add_executive_summary_sheet`:

```python
chart.x_axis.scaling.orientation = "maxMin"
```

Nothing else about the chart changes — no `varyColors`, no per-point
colors, no legend changes, no resize. Verified by rendering before/after
with LibreOffice: bar order now matches the ranked table exactly
(best vendor on top), single legend entry unchanged, no overlap.

### 2. Row height

Audit every row in the workbook that uses a non-default font (title rows,
section/legend headers, column-header rows, the vendor-sheet rollup
block) and give each an explicit `ws.row_dimensions[row].height`, sized
generously relative to that row's font size (roughly 1.5-2x the point
size — a 14pt title gets ~24-26, a 11-12pt bold header gets ~20-22).
This is a straight audit-and-fix of every row using a non-default font in
the current file, not a redesign of font sizes themselves — round 3 and
earlier already chose the font sizes in use today, and this round doesn't
revisit those choices.

Verify with a LibreOffice render before/after, same as the chart fix.
(Caveat: LibreOffice's PDF export does its own layout pass and may not
reproduce every Excel-desktop-specific row-height quirk 1:1, but explicit
`customHeight` is the standard, low-risk fix regardless — safe to apply
even where the render doesn't visibly prove clipping.)

### 3. Reviewer count > 5

No implementation. Confirm in the CLI's `--reviewer-slots` help text /
docs if not already clear, and mention it directly in the follow-up to
the user.

### 4. Reviewers sheet

Reintroduce a dedicated "Reviewers" sheet:

- Title row, a one-line instruction, then a `Slot | Name | Role/Title`
  table with one row per `reviewer_slots` requested.
- `Name`/`Role` cells are unlocked (editable) with the sheet otherwise
  protected, same pattern used elsewhere in this file (e.g. `Automated
  Score` stays locked, reviewer input cells stay unlocked).
- Each vendor tab's merged reviewer-slot header becomes a formula
  referencing that sheet's row for that slot number, e.g.:

  ```
  =IF(Reviewers!B6="","{Reviewer Name} - {Role|Title}",Reviewers!B6&" - "&Reviewers!C6)
  ```

  Claiming a slot once, on the Reviewers sheet, propagates to every
  vendor tab automatically. The vendor-tab header cell itself goes back
  to locked (it's now a formula, not free text — a claim is made on the
  Reviewers sheet, not by editing a vendor tab directly).
- `validate_workbook()`'s existing "unclaimed slot has data" check reads
  the vendor-tab header cell's *value* today; since that becomes a
  formula, the check needs to instead read the Reviewers sheet's Name
  cell for that slot directly (a formula string will never equal the
  literal placeholder text, so the check would otherwise silently stop
  firing).

**No overwrite protection.** Explicitly decided against both candidate
mechanisms (a `lock-reviewers` CLI step to cell-protect already-claimed
rows; extending `merge()` to treat Reviewers-sheet claims with the same
adopt-if-blank/flag-conflict-if-different pattern already used for
scores) — the added process isn't worth it given the actual risk. Anyone
can freely edit any Name/Role cell at any time; rely on people not
overwriting each other's claims rather than building a guardrail for it.

## Testing

- `tests/test_stakeholder_workbook.py`: chart axis orientation; Reviewers
  sheet structure (title, headers, correct row count for a given
  `reviewer_slots`, unlocked Name/Role cells); vendor-tab header formula
  content per slot; row heights on the rows touched in item 2.
- `tests/test_stakeholder_review.py`: `validate_workbook()`'s
  claimed-slot check updated to read the Reviewers sheet, with a test
  confirming it still fires for a genuinely unclaimed slot with data and
  stays quiet for a claimed one.
- Regenerate the real workbook (`dast-bench stakeholder-review
  generate`) and render it with LibreOffice for a final visual check of
  items 1 and 2 before calling this done.
