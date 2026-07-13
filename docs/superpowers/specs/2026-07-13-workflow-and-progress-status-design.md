# Workflow Command and Progress Status — Design

## Purpose & Context

Across this session's real dogfood run, the evaluator's own summary of the
experience was: this whole project feels like "a dark room, unconnected but
dependant steps, no easy what's next or progress meter." Six skills exist
(`dast-criteria`, `dast-discovery`, `dast-shortlist`, `dast-scan`,
`dast-onboard-tool`, `dast-report`), each documented in its own `SKILL.md`,
but there is no single place to answer "where am I in the whole pipeline
right now" or "what does each skill actually do" without either already
knowing it or having an LLM read a full skill file to re-derive the answer
every time.

This splits into two genuinely different problems, both fixed here with no
new persisted state and no new dependencies:

1. **"What does each skill do"** should be a static, instantly-available
   fact — it rarely changes, and re-deriving it by reading a `SKILL.md`
   file (an LLM-reasoning cost) every time is wasteful when it's really
   just a lookup.
2. **"Where am I right now"** is dynamic (depends on the actual state of
   `data/*.yaml`), but is fully derivable from data already loaded by the
   existing `dast-bench status` command — it just isn't synthesized into a
   phase-by-phase view today.

## Goals

- A new `dast-bench workflow` command: prints a static table of all six
  skills (name, one-line purpose, what it reads, what it writes) — pure
  string formatting, no data loading, no LLM reasoning required to answer
  "what does this skill do."
- `dast-bench status`'s existing gap-report output (used programmatically
  by `dast-shortlist` and `dast-report` today) stays byte-for-byte
  unchanged — this is a strictly additive change.
- `dast-bench status` gains an appended "Progress:" section: one line per
  phase (Criteria, Discovery, Shortlist, Hands-on scan), each derived
  purely from the same `CriteriaTaxonomy`/`Vendor` data `status` already
  loads — no new persisted state, no new CLI flags.
- A synthesized "Next:" line naming the single most useful next action,
  pulling that skill's one-liner from the same static table `workflow`
  prints — one source of truth, never duplicated.
- Both commands remain pure reads — consistent with this project's
  "deterministic operations don't need an LLM" principle already
  established for `status`/`render`.

## Non-Goals / Out of Scope

- A TUI or any interactive/visual dashboard — explicitly a separate,
  larger, still-deferred roadmap item (`2026-07-11-tui-visualization-roadmap.md`).
  This design is a text-only CLI enhancement.
- Tracking whether `dast-report` has ever been run. `reports/` is
  gitignored and regenerable — there's no reliable signal to persist, and
  regenerating it is cheap/idempotent, so it's always just offered as the
  next action rather than tracked as done/not-done.
- Renaming any of the six skills — considered directly with the evaluator
  and explicitly closed: the names already went through a deliberate
  rename pass earlier this session, and the "hard to tell what things do"
  complaint is what this design actually fixes, not the names themselves.
- Any change to the six skill files' own content, or to
  `dast-shortlist`/`dast-report`'s existing programmatic reliance on
  `status`'s current gap-report output format.

## Architecture

One new module, `core/workflow.py`, holds both new pieces of logic, kept
separate from `core/status.py` (which stays scoped to gap detection
exactly as it is):

- **`SKILLS`**: a static list of dicts (`name`, `purpose`, `reads`,
  `writes`) — the single source of truth both new features draw from.
  Editing a skill's description here never requires touching more than
  one place.
- **`phase_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) ->
  list[str]`**: returns the "Progress:" section's lines plus the "Next:"
  line, computed entirely from the same two arguments `gap_report` already
  takes — no new data loading.

**CLI changes** (`core/cli.py`):
- New `@app.command("workflow")` prints `SKILLS` as a formatted table —
  no `storage` calls at all.
- `status_command` calls `phase_report(taxonomy, vendors)` after its
  existing `gap_report` loop and echoes the returned lines — the existing
  lines and their exact wording are untouched; the new section is strictly
  appended below.

## Data Flow

1. `dast-bench workflow` — loads nothing, formats and prints `SKILLS`
   directly.
2. `dast-bench status` — unchanged: loads `criteria.yaml` and
   `candidates/*.yaml`, runs `gap_report`, prints its lines exactly as
   today. Then, newly: calls `phase_report` with the same two loaded
   values and prints its returned lines.
3. `phase_report` computes, in order:
   - **Criteria**: `not started` (no criteria) / `weights invalid` (via
     the existing `validate_weights()`) / `N criteria, weights sum to 100`.
   - **Discovery**: `no candidates yet`, or `N candidates (S seeded, D
     discovered)` — always informational, never "done."
   - **Shortlist**: `X/Y fully scored` (some vendor missing a score for
     some criterion) → `scored, Z decision(s) pending` (fully scored but
     some vendor still `candidate` status) → `Y/Y scored, F finalists, R
     rejected` (every vendor scored and decided).
   - **Hands-on scan**: among vendors with status `finalist` or
     `evaluated`, `E/T finalists evaluated`; `no finalists yet` if none
     exist.
   - **Next**: walks the same checks in the same order and returns the
     first incomplete phase's recommended skill + its one-liner from
     `SKILLS`; if every phase above is settled, recommends `dast-report`
     unconditionally (per the Non-Goal above, never tracked as done).

## Error Handling

Nothing new to handle — both commands are pure reads over data structures
`status` already loads successfully today (an empty taxonomy or vendor
list already round-trips cleanly through the existing model defaults).

## Testing

Both are real code changes (not skill files), so both get real TDD:
- `core/workflow.py`'s `phase_report` gets unit tests per phase-state
  transition (not started / invalid weights / done for Criteria; empty /
  populated for Discovery; each of the three Shortlist states; each of
  the two Hands-on-scan states; each "Next" branch).
- `core/cli.py`'s new `workflow` command and the appended `status` output
  get CLI-invocation tests, following the existing pattern in
  `tests/test_cli_status.py`/`tests/test_cli_render.py`.
- A regression test confirms `status`'s existing gap-report lines are
  byte-for-byte unchanged when there are no vendors/criteria (guards the
  "strictly additive" constraint directly, since `dast-shortlist` and
  `dast-report` depend on that exact wording).
