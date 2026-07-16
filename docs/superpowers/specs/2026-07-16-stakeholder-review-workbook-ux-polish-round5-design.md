# Stakeholder Review Workbook — UX Polish Round 5

> Addendum to rounds 1-4 (all implemented and merged). This round re-derives
> several items from an earlier uncommitted ("YOLO mode") attempt that was
> discarded before round 4, plus new items. Everything here goes through
> the normal brainstorm → spec → plan → subagent-driven-development cycle
> this time, including visual verification via LibreOffice headless
> (installed in round 4) for anything chart- or layout-related.

## Context

Eleven items, against the current committed baseline (round 4: chart
category-axis fix on a horizontal bar chart, explicit row heights on 6
rows, `--reviewer-slots` already scales past 5, the Reviewers sheet with
formula-linked vendor-tab headers). Two were investigated with evidence
before being scoped:

- **The chart's "fixed" bar order (round 4) introduced a new bug.**
  Reversing the category axis's `scaling.orientation` on a horizontal
  `BarChart` also moves where Excel anchors the value axis, dragging its
  title ("Weighted Avg Score (0-5)") up to overlap the chart's own title.
  Confirmed via a real Excel-desktop screenshot from the user — this
  didn't reproduce in the LibreOffice renderer, so a further XML-property
  guess (`crosses`/`axPos`) wasn't verifiable. Instead of a third blind
  attempt on the same chart type, the chart switches from horizontal bar
  to vertical column: rank order is then already correct without any
  axis-orientation override at all, eliminating the whole bug class
  (this is now the second distinct bug this exact horizontal-bar +
  reversed-axis combination has produced). Verified clean via a fresh
  LibreOffice render: titles no longer collide, Invicti (rank 1) renders
  leftmost with zero orientation tricks.
- **A pasted content inconsistency was caught and corrected.** The Legend
  text the user provided for the "How This Works" tab included a line
  from an earlier, different design ("Tier accent: gold left border +
  bold criterion name") that doesn't match this round's actual tier
  styling decision (item 1: remove yellow row shading, keep only the
  existing pink-while-empty conditional formatting on top-10 Score
  cells — no border or bold treatment). The Legend line is corrected to
  describe the pink-while-empty behavior instead.

## Explicitly deferred (not part of this round)

Two related ideas came up while scoping item 4's Legend text and were
deliberately parked rather than built, to avoid scope creep on top of an
already-large round:

- **A real auto-pending mechanism.** Hands-on-eligible criteria
  (`detection-accuracy`, `false-positive-rate` today) always present in
  the sheet from the very first Round 1 build, locked/pending until that
  vendor's actual hands-on confidence lands — independent of whether any
  other vendor in the batch has hands-on data yet (the earlier discarded
  round's sibling-comparison approach doesn't work for this, since Round
  1 by definition has zero vendors with hands-on data). Would need a
  `hands_on_eligible: bool` field on `Criterion` rather than hardcoded
  IDs. Revisit if/when Round 2 hands-on workflows become a live need.
- **Carrying reviewer input forward when the vendor list changes
  mid-cycle** (e.g. shortlist 5 vendors, reviewers start scoring, then 2
  more vendors get added later). Investigated and found to mostly already
  work: `merge(new_workbook, old_workbook)` already skips sheets that
  don't exist in the old file, so re-running it after regenerating a
  larger workbook carries forward existing vendors' review data correctly
  (matched by criterion ID). The one gap is the Reviewers sheet not
  merging, which would require reviewers to re-claim their same slot
  number in the regenerated file — judged not worth asking reviewers to
  do, and not worth building tooling for. No action taken; noted here so
  the reasoning isn't lost if it comes up again.

## Design

### 1. Tier shading

Remove `_TIER_FILL`/`_TIER_FILL_ODD` full-row fill application for
top-tier rows entirely. The existing conditional formatting that tints a
top-tier Score cell `_UNFILLED_FILL` (pink, FCE4D6) only while it's empty
stays as-is — no new logic, this already exists and already does what's
being asked ("enough to give some focus").

### 2. Rename "Executive Summary" → "Overview"

Rename `_EXEC_SHEET_NAME` and the sheet's title cell value.

### 3. Overview intro block (rows 1-6)

Row 1: "Overview" (title, 16pt — see item 6). Row 2: blank. Row 3: "About
This Report" (bold section header). Rows 4-6: the three paragraph lines
verbatim as given by the user. This replaces the current Legend-first
layout on this tab (the Legend moves to How This Works — item 4). The
ranked vendor table and chart shift down to make room, same pattern as
the row-numbering approach used in round 4's Reviewers/How-This-Works
sheets (module-level row constants computed from the block length above
them, not hardcoded).

### 4. New "How This Works" tab (last tab)

Title "How This Works" (16pt). Then:
- "Methodology" section header, followed by the 4 paragraph lines the
  user provided verbatim.
- "Legend" section header, followed by the 6 lines the user provided,
  with two corrections:
  - The tier line becomes: *"Tier highlight (pink): top 10 priority Score
    cells are tinted while still empty, as a reminder they still need a
    value."*
  - The "Pending rows" line drops the auto-pending sentence ("A vendor's
    row is marked pending automatically…") — that describes a feature
    from the earlier discarded round that was never rebuilt; pending rows
    are still purely manual (`--pending-criteria`) today. A follow-up
    design for a real auto-pending mechanism (hands-on-eligible criteria
    always present as locked placeholders from the first Round 1 build,
    independent of sibling-vendor state) was discussed and explicitly
    deferred — not part of this round. The line becomes: *"Pending rows:
    dast-scan results not yet available; locked until Round 2 populate
    fills them in. Until then, treat the Overview ranking as
    provisional."* (this also replaces the old per-vendor-tab
    "Provisional…" banner — item 8).

Both sections use the wrap_text + wide-column-A treatment already proven
in round 4's original (later-reverted) How This Works implementation, so
paragraph text doesn't run off the page.

### 5. Chart: horizontal bar → vertical column

```python
chart.type = "col"  # was "bar"
```

Remove the `chart.x_axis.scaling.orientation = "maxMin"` line entirely —
no longer needed, natural category order is already rank order
(`ranked_vendors` is already sorted best-first; a column chart plots the
first category leftmost by default, which is exactly what's wanted).
Everything else about the chart (title, axis titles, single default
legend, default size) is untouched.

### 6. 16pt title in A1 on every tab

Every sheet's row-1 title cell uses a consistent 16pt bold font and a row
height that doesn't clip it (28, matching the ratio round 4 used for its
14pt→26 titles). This applies to: Overview (item 2/3), every vendor tab
(vendor's display name — see item 8), "Reviewers" (currently 14pt/26 from
round 4, bumped to 16pt/28 here for consistency), and "How This Works"
(item 4, new).

### 7. Reviewers-tab caveat note

One line directly under the existing "Claim a slot by filling in your
name and role below…" instruction:

> Please don't overwrite an existing reviewer's name/role — you may be
> reassigning someone else's already-entered scores to yourself.

Plain text, no enforcement — consistent with round 4's explicit decision
against a locking/protection mechanism.

### 8. Remove per-vendor-tab "Provisional…" text

Delete `ws.append(["Provisional — ranking may shift..."])` from the
per-vendor sheet loop; replaced by the vendor-name title (item 6). The
provisional-ranking caveat moves to How This Works (item 4, folded into
the Legend's "Pending rows" line) rather than living on every vendor tab.

### 9. Reviewer placeholder text

`_unclaimed_reviewer_label` changes from `"Reviewer {slot_number} -
{{name}} - {{role/title}}"` to a fixed string with no slot number:
`"Unassigned — see Reviewers tab"`. Every unclaimed slot shows identical
text; disambiguation between slots comes from column position matching
the Reviewers sheet's own Slot-number rows, not from the placeholder text
itself.

### 10. Shared-roster model (no code change)

Documented here for clarity, not a build item: the Reviewers-sheet model
already tolerates a reviewer who only covers a subset of vendors —
claiming a slot binds identity globally (name/role), but that reviewer's
actual Score/Dispute/Rationale entries stay optional per vendor tab. A
partial-coverage reviewer just leaves their columns blank on tabs they
didn't review; their claimed name still displays correctly everywhere via
the existing formula. No "vendors covered" tracking is being added
speculatively.

### 11. Evidence hyperlinks

Re-add the rich-text approach from the earlier (reverted) implementation:
for an "Automated Evidence" cell whose text contains a domain-looking
token, find the first match, set `cell.hyperlink` to `https://<match>`,
and set `cell.value` to a `CellRichText` where only that matched
substring is styled (blue, underlined via `InlineFont`) — the rest of the
cell's text stays plain. On a normal (non-`rich_text=True`) reload,
`cell.value` still reads back as the full original plain-text string
(verified in the earlier implementation), so nothing downstream that
reads evidence text breaks.

## Testing

- `tests/test_stakeholder_workbook.py`: tier shading (no full-row fill,
  pink-only-when-empty still works), Overview sheet renamed + intro block
  row values, How This Works tab structure (Methodology + corrected
  Legend), chart type is `"col"` with no `x_axis` orientation override
  and correct category order, 16pt/28-height titles on every sheet type,
  Reviewers-tab caveat line present, vendor tabs no longer write the
  Provisional banner, `_unclaimed_reviewer_label` returns the new fixed
  string, evidence hyperlink rich-text styling (plain-text round-trip +
  styled-run round-trip via `rich_text=True`).
- `tests/test_stakeholder_review.py`: no expected changes (the reviewer
  placeholder text isn't compared anywhere in this file — `validate_workbook`
  already reads the Reviewers sheet directly per round 4, not the
  placeholder string).
- Regenerate the real workbook and render it with LibreOffice for a final
  visual check of the chart, Overview intro block, and How This Works tab
  before calling this done.
