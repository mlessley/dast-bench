# Stakeholder Review Workbook — Self-Service Reviewer Slots — Design

> Builds on `docs/superpowers/specs/2026-07-15-stakeholder-review-workbook-design.md`
> (base workbook), `...-ux-polish-design.md` and `...-ux-polish-round2-design.md`
> (styling passes, both implemented and merged). This is an architecture
> change, not a polish fix — it changes what `generate`/`merge`/`validate`
> address and how, not just how the sheet looks.

## Context

Every prior round of this feature assumed the driver knows each
stakeholder's name and role *before* running `generate` (`--stakeholder
"Jane Doe:DAST SME"`), and bakes that identity directly into each
column's header text (`"Jane Doe (DAST SME) Score"`). Hands-on review of
a real generated workbook surfaced that this doesn't match how the
workbook will actually be used: it lives as a shared, live M365 file, and
reviewers should be able to self-claim a slot by typing their own
name/role directly into the file — no pre-assignment, and never a fake
placeholder name (e.g. `"Jane Doe"`) baked into a distributed template.

The driver also confirmed the primary usage mode is the shared live
document; the distributed-copies-plus-`merge` fallback is an edge case
they'd likely reconcile by hand if it ever came up, not something this
design needs to make bulletproof.

## Goals

- `generate` provisions a fixed number of generic reviewer slots (default
  3) instead of driver-specified named stakeholders.
- Each slot is visually grouped under one merged, bold header cell
  reading `"Reviewer N"` (N = 1, 2, 3, ...) spanning its 3 columns
  (Score, Dispute?, Rationale) — a reviewer claims a slot by typing their
  own name/role over that placeholder directly in the shared file.
- `merge`, `validate_workbook`, and `populate` continue to work
  correctly once sub-headers are generic and repeated across slots.

## Non-goals

- No identity validation or cross-copy reconciliation of *who* claimed a
  slot. `merge` never reads or writes the group-header cell at all —
  it addresses slots by column position only, exactly as confirmed in
  review. `validate_workbook` is the one narrow exception: it does an
  exact-string-equality check against the known unclaimed-placeholder
  text (`"Reviewer N"`) purely as a binary "was this slot claimed at
  all" signal — it never parses, compares, or reconciles *what* name a
  reviewer typed in, only whether the placeholder is still there
  unchanged.
- No conflict detection for two different returned copies claiming the
  same slot with different names — out of scope, per the same decision
  (distributed-copies mode is a rare fallback, not the target workflow).
- No change to `populate` — it only ever touches Automated
  Score/Evidence/Confidence columns, never the reviewer-slot columns, so
  nothing about this design affects it.
- No change to row layout beyond reusing the existing blank row 2 —
  `HEADER_ROW`, `FIRST_DATA_ROW`, the rollup-row math, and every
  Executive Summary row constant are untouched.
- No backward-compatible dual mode (`--stakeholder` list *and*
  `--reviewer-slots` count). `generate`'s signature changes cleanly;
  every existing test that constructs a workbook via the old
  `stakeholders=[...]` parameter needs updating as part of this work,
  not preserved as a legacy path.

## Design

### A. Workbook structure

Row 2 of every vendor sheet (currently blank — a spacer between the row
1 "Provisional" note and the row 3 column headers) becomes the merged
group-header row. For each of `reviewer_slots` slots, in order:

- `ws.merge_cells(start_row=2, start_column=<slot start col>, end_row=2,
  end_column=<slot start col + 2>)` — one merge per slot, spanning its
  Score/Dispute?/Rationale columns.
- The merged range's top-left cell (the only one `openpyxl` allows
  writing to) gets the value `f"Reviewer {slot_number}"` (1-indexed),
  `_HEADER_FONT` (bold white), `_HEADER_FILL` (navy, same as row 3) —
  reusing Round 1's existing header style constants rather than
  inventing new ones, so row 2 and row 3 read as one continuous styled
  header block.
- Row 3's three sub-header cells under each slot become the literal,
  identical strings `"Score"`, `"Dispute?"`, `"Rationale"` — no name or
  role text anywhere in the header row.

### B. `generate_workbook` / CLI signature change

`generate_workbook`'s `stakeholders: list[tuple[str | None, str]]`
parameter is replaced with `reviewer_slots: int` (default 3, matching
the earlier slot-count decision). `stakeholder_headers()` is replaced
with a function that builds `reviewer_slots * 3` generic header strings
instead of one named triple per driver-specified stakeholder.
`generate_workbook`'s `top_tier_count` parameter and everything else
about its signature is unchanged.

The CLI's `dast-bench stakeholder-review generate` command drops
`--stakeholder name:role` (repeatable) and gains `--reviewer-slots`
(single int, default 3).

This is a breaking change to both the function and the CLI, not an
additive one. Every existing test across `tests/test_stakeholder_workbook.py`,
`tests/test_stakeholder_review.py`, and `tests/test_cli_stakeholder_review.py`
that currently builds a workbook via `stakeholders=[...]` or
`--stakeholder ...` must be updated to use `reviewer_slots=N` /
`--reviewer-slots N` instead — this is expected migration churn from the
design, not incidental scope creep, and the implementation plan should
size tasks accordingly (updating existing fixtures is part of the work,
not a side effect to minimize).

### C. Addressing rework (`merge`, `validate_workbook`)

Today, `_column_map(ws)` builds a `{header_text: column_letter}` dict
from row `HEADER_ROW`, and `merge`/`validate_workbook` look up a
stakeholder's three columns by that stakeholder's unique header text
(e.g. `"Jane Doe (DAST SME) Score"`). With generic, repeated sub-headers,
that dict would collide — three "Score" columns overwriting each other's
entry, so only the last slot would ever be found correctly.

Both functions switch to **positional slot addressing** for the
reviewer-slot columns specifically: slot *i*'s three columns are
computed the same deterministic way `generate_workbook` lays them out
(base-header count + `(i - 1) * 3` offset), not looked up by text at
all. `_column_map` may still exist and be used for the *other* columns
that remain uniquely named (`Automated Score`, `Resolved Score`,
`_criterion_id`, etc.) — only the reviewer-slot triple needs the new
positional path.

`merge(master_path, from_path)`: for each slot number 1..`reviewer_slots`
present in both files (master and every returned copy always originate
from the same `generate` call, so slot counts and layout are identical —
no reconciliation needed), merge that slot's Score/Dispute?/Rationale
cells using the same blank-fill / conflict / invalid-value rules already
in place today, just addressed by slot position instead of header text.
The group-header cell (row 2) is never read or written by `merge`.

`validate_workbook(file_path)`: gains one new check per slot — if the
slot's group-header cell (row 2) still reads the literal unclaimed
placeholder (`f"Reviewer {slot_number}"`) but any of that slot's
Score/Dispute?/Rationale cells (row `FIRST_DATA_ROW` onward) is non-blank,
report an issue string (e.g. `"Reviewer {slot_number}: has responses but
slot was never claimed (header still shows placeholder text)"`). This
reuses the existing `issues: list[str]` return shape — no new return
type.

### D. `populate`

No change. It only reads/writes `Automated Score`, `Automated Evidence`,
`Automated Confidence`, and `_pending` — none of which are reviewer-slot
columns.

## Testing approach

- `generate_workbook`: assert the merged-cell range and its value/style
  for each slot; assert row 3's sub-headers are the plain repeated
  strings; assert `reviewer_slots=0` produces a workbook with no
  reviewer columns at all (base + resolution + hidden headers only) as
  a degenerate-but-valid case.
- `merge`: fixtures with 2+ slots, confirming slot 2's data merges
  independently of slot 1's and slot 3's, addressed correctly even
  though all three slots share identical sub-header text.
- `validate_workbook`: a fixture with an unclaimed slot that has
  Score/Rationale data filled in, asserting the new issue string
  appears; a fixture with a claimed slot (header text changed from the
  placeholder) and data present, asserting no such issue is raised.
- CLI: update the existing `test_cli_stakeholder_review.py` fixtures to
  pass `--reviewer-slots` instead of `--stakeholder`, confirming
  `generate` still produces a valid file end to end.
