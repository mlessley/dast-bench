# dast-report Narrative Template Update — Design

## Purpose & Context

A senior-architect-style review of `dast-bench`'s output artifacts flagged
five gaps. Two were already built this session as a code change to
`core/render/markdown.py` (rubric/weight display, numeric category
roll-up — commits `a573578`/`51a2a85`). A fourth (four new taxonomy
criteria) was completed directly via the `dast-criteria`/`dast-shortlist`
skills (`data/criteria.yaml` now has 33 criteria, all three candidates
fully re-scored). This design covers the three remaining items, all
scoped to `.claude/skills/dast-report/SKILL.md`'s narrative-writing
instructions — a prompt file, not application code, so no
`core/render/`, model, or CLI changes are involved:

1. **Category-level "Enterprise Takeaway" narrative** — the numeric
   Category Breakdown table already renders in `comparison-matrix.md` and
   every scorecard; this adds the interpretive one-liner per category that
   was deliberately kept out of the deterministic code (judgment, not
   math).
2. **"Where They Win" vendor comparison table** — a structured,
   side-by-side table (Vendor / Status / Core Strengths / Critical
   Enterprise Gaps), replacing the current all-prose format for a
   scannable first pass.
3. **Format polish** — dense per-vendor paragraphs become `**The Wins:**`
   / `**The Gaps:**` bulleted groups; a new `## Financial Sector Fit`
   framing block anchors the whole report to the buyer's actual risk
   profile before any vendor-specific content.

## Goals

- Restructure `dast-report`'s Step 4 (compose the narrative) to produce,
  in this order: Financial Sector Fit → Overview (unchanged) → Where They
  Win table → per-vendor sections (Wins/Gaps bullet format) → Category
  Takeaways → Trade-offs worth flagging (unchanged) → methodology/taxonomy
  notes (unchanged).
- Every new piece of content stays grounded in specific evidence already
  recorded for a vendor (a criterion name, a score, an evidence string) —
  never a vague adjective with nothing behind it. This is a formatting and
  structuring change, not a license to invent new analysis.
- Category Takeaways read their numbers from the already-shipped Category
  Breakdown table in `reports/comparison-matrix.md` (read, not
  re-derived) — same "match the deterministic render exactly" principle
  `dast-report` already applies to the Weighted Total figure.
- Steps 1, 2, 3, 5, and 6 of the skill are unchanged. Only Step 4's body
  is replaced.

## Non-Goals / Out of Scope

- No changes to `core/render/markdown.py`, `core/render/xlsx.py`, or
  `core/render/html.py` — those already shipped their two items this
  session and are not touched again here.
- No changes to `data/criteria.yaml`, `data/candidates/*.yaml`, or any
  CLI command — `dast-report` remains strictly read-only over the SSoT,
  same contract as today.
- No automatic refresh of `sample-report/` — that stays a manual step the
  evaluator owns, exactly as established when `sample-report/` was built.
- No new persisted state, no new CLI flags, no change to
  `reports/`'s gitignore policy.
- The existing "Trade-offs worth flagging" and methodology/taxonomy-note
  sections are cross-cutting caveats about scoring methodology, not
  per-vendor or per-category content — they are not restructured into
  Wins/Gaps format and Category Takeaways does not duplicate them.

## Architecture

Single-file change: `.claude/skills/dast-report/SKILL.md`'s Step 4 is
replaced in full. Steps 1-3, 5, 6 and the skill's frontmatter/intro
paragraph are untouched.

**New Step 4 structure** (six numbered composition steps, replacing the
current single free-prose paragraph):

1. **Financial Sector Fit** — 2-3 sentences, written before any
   vendor-specific content, naming the 2-3 dimensions that matter most
   for the evaluator's actual buyer context (Fortune 500 financial
   services by default, unless the evaluator has specified otherwise) and
   noting that rankings should be read through that lens, not just the
   raw weighted total.
2. **Overview** — unchanged: candidate count, taxonomy size, phase
   reached per vendor, weighted-total comparison table.
3. **Where They Win** — one table contrasting every finalist/evaluated
   vendor (plus any rejected vendor worth a comparison row, evaluator's
   judgment) with exactly these four columns: `Vendor | Status | Core
   Strengths / Best For | Critical Enterprise Gaps`. Every cell cites a
   specific criterion/score/evidence, never an unsupported adjective.
4. **Per-vendor sections** — same one-section-per-finalist/evaluated-
   vendor structure as today, but each vendor's body is two bulleted
   groups under bold prefixes (`**The Wins:**` / `**The Gaps:**`) instead
   of dense prose paragraphs. Same depth/rigor requirement as before
   (cite specific evidence, cover notable cross-vendor trade-offs) —
   only the formatting changes.
5. **Category Takeaways** — one bullet per category, in the same order
   `dast-bench criteria list` reports them, each naming the category's
   weight and either which vendor(s) lead it and why, or a market-wide
   gap if every vendor scores low on it.
6. **Trade-offs worth flagging** — unchanged from today: cross-cutting
   scoring-methodology caveats, not restated per-vendor or per-category
   content.

The skill's existing rules carry forward unchanged and apply within this
new structure: rejected/still-candidate vendors get one line each (now
placed in Overview or the Where They Win table, evaluator's judgment on
which reads better for a given evaluation), not equal depth; an explicit
caveats section is still mandatory if gaps were outstanding at render
time; a zero-vendor or zero-finalist/evaluated state still skips Step 5's
file write entirely with a plain explanation, rather than forcing
commentary onto an empty comparison.

## Data Flow

1. Step 3 (unchanged) identifies finalist/evaluated vendors via
   `dast-bench candidate list`.
2. Step 4 reads each finalist/evaluated vendor's record directly
   (`data/candidates/<id>.yaml`), runs `dast-bench criteria list` for
   rubric/weight/category context, and reads the freshly-rendered
   `reports/comparison-matrix.md` for both the Weighted Total figures
   (as today) and the newly-shipped Category Breakdown figures (new) —
   so every number quoted in the Overview, Where They Win table, and
   Category Takeaways sections matches the deterministic render exactly.
3. Step 5 (unchanged) writes the composed result to
   `reports/executive-summary.md` directly, with the same fixed
   skill-authored header as today.

## Error Handling

Nothing new. All existing error-handling rules (gaps in Step 1, zero
vendors, zero finalist/evaluated vendors, caveats-if-proceeded-despite-
gaps) carry forward unchanged into the new Step 4 structure — see
Architecture above for exactly where each now lives.

## Testing

This is a prompt-file change, not application code — no pytest applies.
Verification is content-based: after the file is rewritten, grep-based
checks confirm the new section headers exist in the right order (`##
Financial Sector Fit`, `## Overview`, `## Where They Win`, `## Category
Takeaways`, `## Trade-offs worth flagging` — in that relative order via
line-number comparison) and that the six numbered composition steps are
all present under Step 4. This mirrors how this session's earlier
`dast-scan` manual-path `SKILL.md` rewrite was verified (grep for exact
section markers, not a test suite).

Real-world verification: after the plan is implemented, actually
re-invoking `dast-report` against the current real data (33 criteria, 3
candidates) and inspecting the regenerated `reports/executive-summary.md`
is the true acceptance test — grep checks only confirm the instructions
are structurally present, not that a real invocation produces sensible
output. That real re-invocation is expected to happen as a natural
follow-up once this plan is implemented, not as a task within the plan
itself (the plan's scope is the skill-file edit; actually running the
skill is a separate, subsequent action the evaluator can request).
