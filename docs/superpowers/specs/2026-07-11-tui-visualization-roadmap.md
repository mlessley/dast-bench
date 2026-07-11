# TUI / Visualization Layer — Roadmap (Deferred, Not Yet Designed)

**Status: parking-lot notes, not a validated design.** Raised mid-brainstorm
while designing the `dast-criteria` skill, deliberately deferred so that
brainstorm could stay focused. Revisit as its own brainstorm once it feels
useful, not on a fixed schedule.

## The concern

Everything in this project today is CLI + YAML: you see state by reading
files or running `dast-bench status`/`list`/`render`. That's workable, but
as more phases (`dast-criteria`, `dast-discovery`, `dast-shortlist`,
`dast-scan`, `dast-report`) come online and there's more state to track —
which vendors are in which status, which criteria have gaps, current
weight distribution — a live view of structure/state/available-actions
becomes more valuable than reading YAML by hand.

## Why this is NOT a Phase 2 concern

This doesn't require the planned Phase 2 port (AWS Strands / a proper agent
runtime) or a web GUI. It's a **read-only viewer** over the exact same
data the CLI already reads:
- `dast-bench render` already produces `reports/dashboard.html` — a
  self-contained, sortable comparison table, no server needed.
- `dast-bench status` already produces the textual gap report.
- A TUI (e.g. Python [Textual](https://textual.textualize.io/)) would just
  read the same `data/*.yaml` files these commands already read — no new
  data model, no architecture change, nothing that competes with or
  needs to anticipate the Phase 2 port. If anything it's easier to build
  now, while the data model is small, than after a Phase 2 migration.

## Rough shape (not designed)

A `dast-bench dashboard` (or similar) command/script showing, live:
- Current criteria taxonomy (categories, weights, whether they sum to 100)
- Vendor list with status (`candidate` / `finalist` / `rejected` /
  `evaluated`) and at-a-glance score/gap summary per vendor
- The same gap report `status` already computes, but browsable rather
  than a flat printed list
- Possibly: suggested next actions (e.g. "3 vendors missing scores for
  criterion X — run dast-shortlist" ) — genuinely a stretch goal, not
  a given

## Explicitly not decided yet

- Read-only viewer vs. something that can trigger actions (e.g. dispatch
  the CI pipeline, kick off a skill) from within the TUI
- Whether it lives in `core/` as an optional extra, or as a fully separate
  tool that just happens to read the same `data/` directory
- Exact library/approach (Textual was the one raised, not committed to)

## Next step

Come back to this "as soon as it makes sense" (user's words) — likely once
there's enough real data (candidates, scores) flowing through the system
that reading YAML by hand starts to feel limiting, or once several of the
five skills exist and there's real multi-phase state to track. Per
[[feedback_proactive_followup]], resurface this unprompted when relevant
rather than waiting to be asked.
