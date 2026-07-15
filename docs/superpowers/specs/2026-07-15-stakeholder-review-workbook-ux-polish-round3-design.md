# Stakeholder Review Workbook — UX Polish Round 3 (Addendum)

> Addendum to the three prior rounds (base workbook, UX polish rounds 1-2,
> and the self-service reviewer-slots redesign — all implemented and
> merged). This round is a mix of small, independent polish fixes found
> from a hands-on look at the real reviewer-slots output, plus one
> revision to a decision made during the reviewer-slots brainstorm.

## Context

A hands-on review of the reviewer-slots workbook surfaced several gaps,
and one earlier decision needed revisiting once seen in a real 3-slot
layout:

- **Freeze panes stop one column short of useful.** `"D4"` freezes
  Criterion/Category/Weight but not Automated Score/Evidence/Confidence
  — so scrolling right to see a reviewer slot loses the automated
  reference data a reviewer needs alongside their own answer.
- **The pending placeholder text is ambiguous about scope.** "Do not
  edit" could read as "don't edit this one cell" rather than "don't
  score this row at all yet."
- **The rollup block at the bottom of each vendor sheet has no
  section header** — it reads as data trailing off rather than a
  distinct "Summary" section, the same gap the Executive Summary
  legend already solves for that tab but vendor sheets never got.
- **The `"Reviewer N"` placeholder decision from the reviewer-slots
  brainstorm is revised.** That round deliberately kept it terse
  (bare `"Reviewer N"`) to avoid crowding a narrow header. Seeing the
  real 3-column-wide merged cell in practice, there's plenty of room,
  and the driver now wants the full name *and* role visible so
  reviewers on a shared panel can tell who's who — reversing that
  earlier terseness call.
- **Weight's meaning and provenance aren't explained anywhere in the
  workbook** — a reviewer has no way to know it's the same value
  driving the actual weighted score, or that the evaluator (not the
  reviewer) set it during criteria definition.
- **Default reviewer-slot count changes from 3 to 5** — the driver
  wants a larger standing default panel size.
- **Two items raised but explicitly deferred, not part of this round:**
  the yellow tier-highlight still has no in-workbook explanation (the
  driver will explain live for now), and the weight-based row-sort
  algorithm itself stays as-is (confirmed: weight is the same value
  already driving the real score, not an arbitrary editorial choice,
  so no change to `compute_priority_order`).

## Goals

1. Freeze panes extend through column F (Automated Confidence).
2. Pending placeholder text clarifies the whole row is off-limits, not
   just the placeholder cell.
3. Each vendor sheet's rollup block gets a "Summary" header row.
4. The unclaimed reviewer-slot placeholder becomes
   `"Reviewer N - {name} - {role/title}"` (full template, not just the
   slot number).
5. The Executive Summary legend gains one line explaining what Weight
   means and where it comes from.
6. Default `reviewer_slots` changes from 3 to 5 in both
   `generate_workbook` and the CLI's `--reviewer-slots` option.

## Non-goals

- No in-workbook explanation of the yellow tier-highlight color
  (deferred — explained live by the driver for now, may revisit later).
- No change to `compute_priority_order`'s weight-based sort (confirmed
  as-is — weight is the same value driving the real weighted score, not
  a subjective overlay).
- No change to `validate_workbook`'s unclaimed-slot detection *logic* —
  it already does an exact-string comparison against whatever
  `_unclaimed_reviewer_label` returns, so a longer placeholder string
  needs no logic change there, only the constant's format.

## Design

### 1. Freeze panes

`ws.freeze_panes = "D4"` → `ws.freeze_panes = "G4"` in `generate_workbook`
— freezes columns A-F (Criterion, Category, Weight, Automated Score,
Automated Evidence, Automated Confidence) and the header row, same
mechanism as the existing Round 2 fix that extended A-C to A-C+Weight.

### 2. Pending placeholder text

`_PENDING_TEXT` changes from:

> "Pending — dast-scan results not yet available. Do not edit; will be
> populated in Round 2."

to:

> "Pending — dast-scan results not yet available. Do not score or edit
> this row; it will be populated in Round 2."

Explicitly names "this row" rather than leaving "do not edit" scoped
ambiguously to just the cell it's written in.

### 3. Vendor-sheet rollup "Summary" header

`generate_workbook` already writes a single blank spacer row
(`ws.append([])`) between the last criteria row and the first
category-subtotal row — this is the exact row `_rollup_row_numbers`
already accounts for (`first_category_row = last_data_row + 2`) and the
same row the Round 2 border fix draws its top border on. This task
reuses that *same* row — no new row is inserted, so no rollup-row-number
arithmetic changes anywhere (`_rollup_row_numbers`, the Executive
Summary's cross-sheet formulas, and the existing border-placement code
are all unaffected). Instead of leaving that row's column A cell blank,
write `"Summary"` into it, styled with `_HEADER_FONT`/`_HEADER_FILL`
(the same header style already used for the row-3 column headers and
the Executive Summary table header, for visual consistency) so the
rollup block reads as a labeled section rather than a border-separated
continuation of the data rows.

### 4. Reviewer-slot placeholder template

`_unclaimed_reviewer_label(slot_number: int) -> str` changes from
`f"Reviewer {slot_number}"` to
`f"Reviewer {slot_number} - {{name}} - {{role/title}}"` — a literal
string containing the literal substrings `{name}` and `{role/title}` as
a fill-in template (not an actual Python format substitution — there's
no real name yet at generation time). A reviewer claiming the slot
types their own name and role over those bracketed placeholders
directly in the shared file. `validate_workbook`'s unclaimed-slot check
(reviewer-slots Task 4) needs no logic change — it already does an
exact-string comparison against whatever this function returns, so a
longer string is transparent to it. The merged cell is already 3
columns wide with wrap-text enabled via the existing header style, so
no column-width or layout change is needed.

### 5. Weight legend line

Add one new line to `_EXEC_LEGEND_LINES_TEMPLATE` (the Executive
Summary tab's legend block, already rendering 5 lines today):

> "Weight (on each vendor sheet) is each criterion's relative importance
> in the overall weighted score — the same value used in the actual
> score calculation, set by the evaluator when the criteria taxonomy was
> defined, not something a reviewer sets."

This is legend-only (Executive Summary tab), not a new caption on every
vendor sheet — the per-vendor-sheet caption idea from the same
discussion was tied to explaining the tier-highlight color, which is
deferred; Weight's explanation doesn't need a duplicate location.

### 6. Default reviewer-slot count

Correction to how this was originally described: `generate_workbook`'s
`reviewer_slots` parameter has **no default today** — it's a required
parameter followed by other required parameters before
`top_tier_count`'s existing default, so giving it a default would be a
Python syntax error unless every parameter after it also got one, which
is out of scope. The only actual "default" behavior lives in the CLI:
`typer.Option(3, "--reviewer-slots")` becomes
`typer.Option(5, "--reviewer-slots")`. `generate_workbook` itself is
unchanged — every real caller (the CLI, every test) already passes
`reviewer_slots` explicitly. The existing CLI test
`test_cli_stakeholder_review_generate_defaults_to_three_reviewer_slots`
is renamed and its assertion updated to expect 5 slots
(`header.count("Score") == 5`) instead of 3.

## Testing approach

- Freeze panes: assert `ws.freeze_panes == "G4"`.
- Pending text: assert the updated exact string appears in a pending
  row's Automated Evidence cell.
- Summary header: assert a bold, `_HEADER_FILL`-colored cell reading
  `"Summary"` exists at the row immediately before the first
  category-subtotal row (derivable from `_rollup_row_numbers`).
- Reviewer-slot placeholder: assert the merged anchor cell's value is
  exactly `"Reviewer 1 - {name} - {role/title}"` for slot 1 (and the
  equivalent for other slots).
- Legend: assert the new Weight-explanation line's text appears at the
  expected legend row (derivable from `_EXEC_LEGEND_LINES_TEMPLATE`'s
  new length).
- Default slot count: CLI test asserts 5 `"Score"` columns when
  `--reviewer-slots` is omitted entirely.
