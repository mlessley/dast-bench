# dast-report Skill Design

## Purpose & Context

`dast-report` is Phase 5, the final skill of the original dast-bench
workflow: it renders the SSoT (`criteria.yaml` plus every
`candidates/*.yaml`) into presentation artifacts and surfaces any gaps
before doing so. `dast-bench render` and `dast-bench status` are already
fully built and deterministic — the original Phase 1 design doc explicitly
notes both "don't need an LLM and can be run directly from bash." The real
design question for this skill is not how to render (already solved) but
what an LLM-driven skill adds on top of a bare CLI invocation.

Two things: a **gap-aware gate** (check for gaps first, ask the evaluator
whether to proceed or fix them, rather than silently rendering an
incomplete comparison) and a **narrative summary** — a written
interpretation of the results, focused on the vendors that actually matter
for a decision, which a deterministic render fundamentally cannot produce.

`dast-shortlist` (built 2026-07-12) is the closest precedent: like it, this
plan needs zero new CLI commands or model changes — everything it needs
already exists.

## Goals

- Before rendering, run `dast-bench status`; if gaps exist (missing scores,
  weight-total warnings), tell the evaluator plainly and ask whether to
  proceed anyway or hold off until they're fixed — never render an
  incomplete comparison silently.
- Render via the existing `dast-bench render` (unchanged, deterministic).
- Write a narrative summary (`reports/executive-summary.md`) interpreting
  the results: who's leading and why (citing specific evidence, not just
  weighted-total numbers), and notable trade-offs.
- Scope the narrative's depth to finalist/evaluated vendors — the ones that
  actually matter for a decision. Rejected/still-candidate vendors get at
  most a one-line mention, not equal analytical treatment. (The raw
  comparison matrix produced by `dast-bench render` still includes every
  vendor regardless of status — only the narrative layer is scoped.)
- If the evaluator chose to proceed despite gaps, the summary must include
  an explicit caveats section naming exactly which gaps were outstanding at
  render time.
- Handle the edge cases of zero vendors, or zero finalist/evaluated
  vendors specifically, by saying so plainly rather than forcing narrative
  commentary onto an empty or premature comparison.

## Non-Goals / Out of Scope

- Re-implementing or modifying rendering itself — `dast-bench render`
  (`core/render/{markdown,xlsx,html}.py`) is unchanged, already
  deterministic, and already tested.
- Deciding criteria, candidates, scores, or finalists — every earlier
  skill's job. `dast-report` only reads and interprets what's already
  there.
- Any new CLI command or data model change — this plan is prompt-file-only,
  same as `dast-shortlist`.

## Architecture

`dast-report` is a Claude Code skill: a prompt file at
`.claude/skills/dast-report/SKILL.md`, invoked as `/dast-report`. It
contains no code. Everything it needs already exists: `dast-bench status`,
`dast-bench render`, `dast-bench candidate list`, `dast-bench criteria
list`, plus direct `Read` of each finalist/evaluated vendor's
`data/candidates/<id>.yaml` for full evidence (scores, evidence text,
hands-on results, observations) — richer than the rendered matrix's bare
numbers, since it lets the narrative cite specific reasons.

**One new artifact, written directly by the skill, not through the CLI:**
`reports/executive-summary.md`. This is a deliberate, scoped exception to
the "mutate only through the CLI" rule that governs every other skill in
this project — that rule protects `data/*.yaml`, the SSoT. `reports/` is
already regenerable output that `dast-bench render` itself writes directly
from Python, not through any further indirection; the skill's summary file
follows that same "generated output" pattern, just authored by narrative
judgment rather than a deterministic template. The file's own header, and
the skill's instructions, both state plainly that it is skill-authored and
not part of `dast-bench render`'s deterministic output — a bare re-run of
`render` alone doesn't regenerate or imply staleness of this file.

## Data Flow

1. Skill runs `dast-bench status` to check for gaps.
2. **If gaps exist:** presents them plainly and asks the evaluator whether
   to proceed anyway or hold off until they're fixed. If "hold off," the
   skill stops here — no render, no summary.
3. Skill runs `dast-bench render` (writes `comparison-matrix.md/.xlsx`,
   per-vendor scorecards, and `dashboard.html` to `reports/`,
   deterministically, exactly as it does today).
4. Skill runs `dast-bench candidate list` to identify which vendors are
   `finalist`/`evaluated` vs `candidate`/`rejected`.
5. For each finalist/evaluated vendor, reads its
   `data/candidates/<id>.yaml` directly (full evidence) — inspection only,
   no writes.
6. Reads `dast-bench criteria list` (rubric/weight context) and the
   freshly-written `reports/comparison-matrix.md` (so the narrative's
   weighted-total numbers match the deterministic render exactly, not a
   re-derived figure).
7. Composes the narrative: who's leading and why (citing specific
   evidence), notable trade-offs among finalists/evaluated vendors, a
   one-line mention of rejected/still-candidate vendors, and — if gaps
   existed and the evaluator chose to proceed anyway — an explicit
   caveats section naming exactly which gaps were outstanding at render
   time.
8. Writes `reports/executive-summary.md` directly.
9. Summarizes for the evaluator: what was rendered, where the artifacts
   live, and presents the narrative.

## Error Handling

- Any CLI command that errors or exits nonzero — relay the output
  verbatim, ask the evaluator how to proceed, consistent with every other
  skill in this project.
- Zero vendors at all, or zero finalist/evaluated vendors specifically
  (e.g. still mid-`dast-shortlist`) — the skill says so plainly rather
  than forcing narrative commentary onto an empty or premature comparison.

## Testing

Zero code changes — no new CLI commands or model changes, matching
`dast-shortlist`'s precedent. The skill file itself is not unit-tested —
reviewed by the evaluator reading it once written.
