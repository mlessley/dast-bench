# Stakeholder Review Workbook — UX Polish Round 2 (Addendum)

> Addendum to `docs/superpowers/specs/2026-07-15-stakeholder-review-workbook-ux-polish-design.md`
> (Round 1 — implemented and merged: header/column styling, banding/tab
> colors, the `Dispute?` case-sensitivity fix, the Executive Summary tab
> and its chart). This addendum covers a second review pass — five
> concrete fixes, plus corrections to two items that review feedback
> assumed were already broken or already fixed but weren't quite either.

## Context

A hands-on review of a real generated workbook (5 vendors, all fully
scored) surfaced five real gaps and two factual corrections worth
recording so they aren't re-litigated:

- **The `Dispute?` dropdown offers `"Yes"` only** (blank means
  not-disputed) — reviewed and explicitly confirmed to **stay as-is**.
  Not a defect; recorded here only so a future pass doesn't "fix" it
  into a `Yes`/`No` pair without cause.
- **There is no dedicated "pending row" background fill** in the
  current implementation — pending rows get whichever tier-highlight or
  banding fill their row position would normally receive, plus the
  existing lock and placeholder text. Review feedback referred to
  "pending-cell coloring" as something banding needed to layer under;
  no such coloring exists to layer under, so this addendum's banding fix
  only needs to reconcile with tier-highlight, not a nonexistent pending
  fill. (A distinct pending-row fill was not requested and is out of
  scope here.)
- **Right-alignment on the Executive Summary numeric columns is already
  implemented** (Round 1, Task 4) — confirmed, no change needed.

A reviewer self-service column-claiming feature (generic "Reviewer N"
slots with a merged placeholder header a stakeholder edits directly in a
shared live file) was also raised in the same review pass. It is
explicitly **out of scope for this addendum** — it changes how
`merge`/`validate_workbook`/`populate` address a stakeholder's columns
(from header-text lookup to positional-slot lookup), which is an
architecture change, not a polish fix. It gets its own brainstorm/spec
cycle later; the only decision locked in now is the default slot count
(**3**) for whenever that work starts.

## Goals

Five independently-testable fixes to `core/render/stakeholder_workbook.py`:
1. Freeze panes include the Weight column.
2. Automated Evidence text wraps instead of visually truncating.
3. Row banding is continuous across all 33 criteria rows, including
   inside the tier-highlighted block.
4. The Executive Summary legend reads as a bordered, designed block.
5. The Executive Summary table visually highlights the top-ranked vendor.

## Non-goals

- Reviewer self-service column-claiming (deferred, separate spec cycle;
  default slot count of 3 recorded for that future work).
- Changing the `Dispute?` dropdown to `Yes`/`No` (explicitly confirmed
  to stay `Yes` + blank).
- Adding a new dedicated pending-row background fill (not requested).
- Changing Automated Confidence column width (16 already comfortably
  fits `"hands-on"`; the "barely fitting" observation predates the
  Evidence-column wrap fix and should be re-checked after, not changed
  pre-emptively).

## 1. Freeze panes

Change `ws.freeze_panes = "C4"` to `ws.freeze_panes = "D4"` in
`generate_workbook`. This freezes columns A–C (Criterion, Category,
Weight) instead of just A–B, alongside the header row (row 3, already
frozen by any `freeze_panes` row ≥ 4 — this was not actually broken,
only the column range was incomplete).

## 2. Automated Evidence wrap

In the per-criterion styling loop (Round 1, Task 2), the Automated
Evidence column's data cells currently get `Alignment(horizontal="left")`
with no `wrap_text`. Add `wrap_text=True` specifically for this column
(and, since it's the same underlying problem, the per-stakeholder
`Rationale` columns too — free-text columns that can hold long strings).
Do **not** set an explicit `ws.row_dimensions[row].height` — leave it
unset so Excel auto-expands the row when the file is opened. openpyxl
cannot measure rendered text width/height, so a hardcoded height would
either clip long text or waste space on short text; Excel's own layout
engine handles this correctly once `wrap_text=True` is set and no fixed
height overrides it.

## 3. Continuous row banding under tier-highlight

Currently (Round 1, Task 2), tier-highlighted rows (`i < top_tier_count`)
get a single flat fill (`_TIER_FILL`, `FFF2CC`) and banding is skipped
entirely for those rows (`if`/`elif`, mutually exclusive). This addendum
makes banding continuous across all 33 rows by giving the tier band its
own even/odd pair, mirroring the existing non-tier pair:

- Non-tier rows (unchanged): `F2F2F2` on odd `i`, no fill on even `i`.
- Tier rows (new): `FFF2CC` (existing color, unchanged) on even `i`,
  `F9E79F` (new, slightly more saturated yellow) on odd `i`.

This preserves the "top-priority rows are visually distinct" signal
(both shades are clearly yellow-family, distinct from the gray/white
non-tier pair) while keeping the alternating-stripe scan pattern
unbroken across the whole sheet.

## 4. Executive Summary legend box

Add a border and a light fill around the legend block (`_EXEC_LEGEND_HEADER_ROW`
through the last legend line, i.e. rows 3–8) spanning columns A through
E (five columns — wide enough to read as a block, not a one-column
sliver, and narrower than the full table width so it doesn't compete
with the comparison table below it). Border: thin border on all sides of
the outer edge of that A3:E8 range. Fill: a light neutral gray
(`F2F2F2`, reusing the existing banding color rather than introducing a
new one) on every cell in the range.

## 5. Executive Summary top-vendor highlight

After building the ranked vendor rows (`ranked_vendors`, already sorted
descending by `Weighted Avg Score`), apply bold font and a light fill
(`FFF2CC`, reusing the existing tier-highlight color) across the entire
first data row (`EXEC_TABLE_FIRST_DATA_ROW`, all columns from `Vendor`
through `Total Achieved / Available`). This is a static, one-time
highlight based on the snapshot ranking computed at generation time —
consistent with the existing design note that row order doesn't
auto-resort if scores change later.

## Testing approach

- Freeze panes: assert `ws.freeze_panes == "D4"`.
- Evidence wrap: assert `wrap_text is True` on an Evidence data cell (and
  a Rationale data cell); assert no explicit `row_dimensions[...].height`
  is set (stays `None`).
- Banding: assert the four fill colors (tier-even, tier-odd, band-odd,
  band-even/none) appear on the expected rows for a taxonomy with more
  than `top_tier_count` criteria, so both the tier and non-tier bands are
  exercised in one fixture.
- Legend box: assert border style and fill color on a cell inside the
  A3:E8 range.
- Top-vendor highlight: assert bold font and fill color on the first
  data row of a multi-vendor fixture where the ranking is unambiguous.
