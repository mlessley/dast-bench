# Stakeholder Review Workbook — UX Polish (Addendum)

> Addendum to `docs/superpowers/specs/2026-07-15-stakeholder-review-workbook-design.md`.
> That spec and its implementation plan are complete and merged (Tasks 1–8
> plus two post-implementation spec-gap fixes). This addendum covers a
> second pass: making the generated workbook look and feel professional,
> plus one real correctness bug found along the way.

## Context

The first implementation is functionally complete but visually bare:
`openpyxl` defaults for column width (text truncates everywhere), no
header styling, no freeze panes, and no way to compare vendors without
opening every sheet. The client for this evaluation runs their interview
process over MS Teams, so this pass assumes **Microsoft Excel is the only
real target** — no hedging for Google Sheets/LibreOffice fidelity on
charts or cross-sheet formulas, even though the base spec's "Collection
modes" section mentions Google Sheets as a hypothetical equivalent
platform.

## Goals

- Every vendor sheet should be legible and navigable without a stakeholder
  needing to ask what a color or column means.
- Add one new "start here" tab that lets a reviewer compare vendors without
  opening per-vendor sheets.
- Fix a real correctness bug in the `Dispute?` column found during this
  review (case-sensitive matching silently drops valid stakeholder input).

## Non-goals

- No change to existing scoring formulas from the base spec (delta,
  partial-completeness rollup) — this pass adds a new tab that *reads*
  those values and re-styles existing sheets; it doesn't change what they
  compute.
- No Google Sheets/LibreOffice rendering guarantees for the new chart or
  cross-sheet formulas — Excel-only is the assumed target for this
  engagement.
- No true column auto-fit (`openpyxl` has no native equivalent) — fixed,
  generous per-column-type widths instead.
- No `--all-eligible-vendors` convenience flag on `generate` in this pass.
  Worth doing later so an omitted vendor is never silent, but it's a
  separate, smaller change from visual polish — deferred, not required
  here.

## A. Vendor sheet styling

- **Column widths** (fixed, by column type, in `openpyxl` width units):
  `Criterion` 32, `Category` 16, `Weight` 10, `Automated Score` 14,
  `Automated Evidence` 45, `Automated Confidence` 16, each stakeholder
  `... Score` 12 / `... Dispute?` 12 / `... Rationale` 40, `Resolved Score`
  14, `Resolved By` 16, `Resolved Timestamp` 18,
  `Automated vs. Resolved Delta` 14. Hidden helper columns are unaffected.
- **Freeze panes** at `C4` — header row and the Criterion/Category columns
  stay visible while scrolling.
- **Header row** (row 3): bold white text, solid dark-navy fill
  (`1F4E78`), thin border on all sides, `wrap_text=True` so long headers
  like `Automated vs. Resolved Delta` wrap instead of truncating.
- **Number formats:** `Weight`, `Automated Score`, every stakeholder
  `Score`, `Resolved Score`, and `Automated vs. Resolved Delta` get
  `number_format="0.0"` and right alignment. Every text column
  (`Criterion`, `Category`, evidence/rationale, `Automated Confidence`,
  `Dispute?`, `Resolved By`) stays left-aligned.
- **Row banding:** alternating fill (`FFFFFF` / `F2F2F2`) across the data
  rows, applied directly per row at generation time (not a conditional-
  formatting rule — the row parity is already known when the row is
  written). Existing tier-fill (`FFF2CC`) on top-priority rows takes
  precedence — skip banding fill on tier rows so the tier color stays the
  dominant signal there.
- **Visual break before the rollup block:** a medium-weight top border
  across all columns on the first category-subtotal row, so the rollup
  block doesn't read as data trailing off the bottom of the sheet.
- **Tab color:** each vendor tab gets a distinct color from a small fixed
  palette (cycling if there are more vendors than palette entries),
  assigned in the order vendors were passed to `generate`.

## B. `Dispute?` correctness fix

**Bug (confirmed by reading the code, not guessed):** `validate_workbook`
and `merge` both require the `Dispute?` cell to equal the exact string
`"Y"`. A stakeholder typing `y`, `yes`, or `Yes` fails the "disputed
without rationale" check in `validate_workbook`, and in `merge` is
silently treated as an invalid entry — with nothing in the sheet itself
telling them what's expected.

**Fix:**
- Normalize the comparison to case-insensitive, accepting `"Y"`, `"y"`,
  `"Yes"`, `"YES"`, `"yes"` as an affirmative dispute flag, everywhere
  `validate_workbook` and `merge` currently check `== "Y"` / `!= "Y"`.
- Add a native Excel dropdown (`DataValidation`, list `"Yes",""`) on every
  stakeholder `Dispute?` column, same pattern as the existing score
  dropdown, so entry is guided rather than free text.
- Existing tests that use exactly `"Y"` must continue to pass — this is a
  strictly wider acceptance set, not a breaking change.

## C. New "Executive Summary" tab

One new sheet, always inserted as the **first** tab regardless of vendor
order, named `Executive Summary`, tab-colored to match the header fill
(`1F4E78`) so it visually reads as "start here." The sheet is fully
protected (`ws.protection.sheet = True`, no unlocked cells) — it's pure
computed output, never manually edited.

**Legend block** (rows 1–~6, plain bold-labeled text): explains what a
`Pending` placeholder means, what the tier-band fill color means, what
`Dispute? = Yes` requires (a non-blank rationale), and what `Automated
Confidence` values (`paper` / `hands-on`) mean.

**Comparison table**, one row per vendor, below the legend:

| Vendor | `<Category 1>` | `<Category 2>` | ... | Weighted Avg Score | Total Achieved / Available |

Design decision worth calling out explicitly, since it would otherwise be
an easy mistake: **the comparison metric is a normalized average score
(0–5), not the raw "achieved points" number.** The existing per-vendor
rollup row (Task 4 of the base plan) computes, per category and overall:
`achieved = SUMPRODUCT(weight, effective_score, (1-pending)) / 5` and
`available = SUMPRODUCT(weight, (1-pending))` — reusing the `Weight`
column of that rollup row to hold `achieved` and the `Automated Evidence`
column to hold `available` (that's the existing Task 4 layout; it's an
unusual column reuse but already in place and not being changed here).
`achieved` is **not** directly comparable across vendors whose pending
sets differ in size — a vendor with more pending criteria has a smaller
`available` denominator and thus a smaller `achieved` number even if
every scored criterion is equally strong. `achieved / available * 5`
cancels that out and yields the weighted-average score (1–5 scale) across
whatever's currently known, which *is* fairly comparable regardless of
how much is still pending. Each category column and the overall column
both use this ratio, computed via a direct cross-sheet cell reference to
that vendor's rollup row, not `INDEX`/`MATCH` — the exact row numbers are
already known in Python at generation time from the same rollup-row
layout Task 4 built. The all-pending/`available = 0` edge case (every
criterion in a category, or in the whole taxonomy, marked pending for
that vendor) must show the text `"Pending"` rather than `0` — a bare `0`
would misread as "this vendor scored zero" rather than "nothing scored
yet," which is a materially different and misleading signal on a
vendor-comparison tab. E.g.
`=IF('zap'!H12=0,"Pending",'zap'!G12/'zap'!H12*5)`. This means the
`Weighted Avg Score` column can hold text in this edge case; the
descending sort at generation time (see Row order, below) treats any such
vendor as sorting last, since "unknown" shouldn't outrank a real score.

The rightmost `Total Achieved / Available` column shows the existing
per-vendor "X/Y available points" framing for context (so a stakeholder
can see *how much* is currently known, not just the resulting average).

**Row order** is a one-time snapshot at generation time, sorted
descending by overall `Weighted Avg Score` — consistent with the base
spec's existing philosophy that structural layout (e.g. priority order)
is computed once at `generate` time and not continuously live-resorted.
The cell *values* stay live (formulas), but the *row order* does not
re-sort itself if underlying scores change later — worth a one-line note
in the legend block so this isn't a surprise.

**Chart:** one native embedded `openpyxl.chart.BarChart`, vendor names on
the category axis, `Weighted Avg Score` as the single series (the same
fairness reasoning applies to the chart as to the table — it must not
plot raw achieved points), placed to the right of the table.

## D. Workbook-level polish

- Vendor tab order matches the order vendors were passed to `generate`;
  `Executive Summary` is always tab index 0 regardless.
- No change to existing pending/lock behavior. The `Executive Summary`
  tab simply reflects whatever each vendor's rollup formulas currently
  evaluate to, including partial-completeness cases — it never overrides
  or duplicates that logic, only reads it.

## Testing approach

- Vendor sheet styling: read the produced file back with `openpyxl` and
  assert column widths, freeze panes, header font/fill/border, number
  formats and alignment on representative columns, banding fill on two
  adjacent data rows, and tab color.
- `Dispute?` fix: extend existing `validate_workbook`/`merge` fixtures
  with lowercase/mixed-case dispute values and assert they're now
  accepted equivalently to `"Y"`; assert the dropdown data validation
  exists on the `Dispute?` columns.
- Executive Summary tab: generate a small multi-vendor fixture with
  different pending sets per vendor, assert the tab exists at index 0,
  assert its formulas reference the correct vendor-sheet cells, assert
  row order matches descending `Weighted Avg Score` (verified by
  evaluating the known input scores by hand in the test, since `openpyxl`
  doesn't evaluate formulas), and assert a chart object is present.
