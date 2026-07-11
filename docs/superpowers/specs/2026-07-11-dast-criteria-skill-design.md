# dast-criteria Skill Design

## Purpose & Context

`dast-criteria` is Phase 1 of the dast-bench evaluation workflow: it builds
and revises the **criteria taxonomy** — the list of criteria (category,
name, description, weight, rubric) that every vendor will later be scored
against. It is not the scorecard itself. The taxonomy is the equivalent of
designing a spreadsheet's column headers, their relative importance
(weight), and what a 1/3/5 score means for each column — before any vendor
has a row filled in. The scorecard (the filled comparison matrix) is a
separate, already-built artifact (`dast-bench render`), produced later by
combining this taxonomy with each vendor's recorded scores.

Per the Phase 1 design spec, this skill is "re-invocable anytime" — the
expected shape is heavy use up front while the taxonomy stabilizes, then
infrequent revision later (adding a criterion that was missed, adjusting a
weight, removing one that didn't pan out).

## Goals

- Scaffold a criteria taxonomy from a fixed, reviewed industry-standard
  baseline on first invocation (not live web research — deterministic and
  reviewable ahead of time; still fully editable afterward).
- Support real revision on later invocations: add, remove, reweight, and
  edit any field of an existing criterion — not just append-and-reweight.
- Keep every category from the Phase 1 spec's named priorities
  represented as first-class, not afterthoughts: API/SPA coverage,
  shadow/zombie API discovery, safe production scanning with low
  instrumentation overhead, and developer-experience-focused capabilities
  (triage, remediation guidance, auto-PR, noise/signal quality).
- Never touch `data/criteria.yaml` directly — every mutation goes through
  the `dast-bench criteria` CLI, consistent with the rest of this project.

## Non-Goals / Out of Scope

- Building the scorecard/comparison-matrix rendering — already built
  (`dast-bench render`), untouched by this design.
- Live web research for the baseline — deliberately a fixed, baked-in
  starting point (see Architecture).
- A bulk `criteria import` command — considered and rejected in favor of
  small, discrete, auditable CLI calls per criterion, consistent with
  every other command in this project.
- Automatically backfilling scores for existing vendors when a new
  criterion is added — that's `dast-shortlist`'s/`dast-scan`'s job. This
  skill's responsibility ends at "the taxonomy is valid"; gap detection
  for who's missing a score is already handled by the existing
  `dast-bench status` command.

## Architecture

`dast-criteria` is a Claude Code skill: a markdown prompt file at
`.claude/skills/dast-criteria/`, invoked as `/dast-criteria`. It contains
no code of its own — it is instructions for an LLM agent that (a) knows
the fixed baseline taxonomy below, (b) converses with the evaluator to
agree on changes, and (c) persists every agreed change by shelling out to
the `dast-bench criteria` CLI. It never writes YAML directly.

Two small CLI additions are needed to make real revision possible — today
the CLI only supports adding a criterion and adjusting its weight, with no
way to remove or edit other fields:

- **`criteria remove-criterion --id <id>`** — errors
  (`error: criterion '<id>' not found`, exit 1) if the id doesn't exist;
  otherwise removes it and saves. If any candidate has an existing score
  against that criterion, prints an informational warning that those
  scores are now orphaned (not deleted — they remain in the vendor's YAML,
  simply invisible to reports that only iterate current-taxonomy
  criteria).
- **`criteria update-criterion --id <id> [--category] [--name]
  [--description] [--weight] [--rubric]`** — all fields but `--id` are
  optional; only fields explicitly passed are changed. Errors the same way
  as `set-weight` on an unknown id. `set-weight` stays as-is (a convenience
  shorthand for the single most common edit) even though `update-criterion
  --weight` can now do the same thing.

## Baseline Taxonomy Content

The fixed starting taxonomy, baked into the skill's prompt (5 categories,
12 criteria, weights summing to 100):

| Category (weight) | Criterion | Weight |
|---|---|---|
| **Coverage** (30) | API/SPA Coverage — REST/GraphQL + JS-rendered SPA content | 15 |
| | Shadow/Zombie API Discovery — finds undocumented/forgotten endpoints | 10 |
| | Authentication & Session Handling — navigates login flows, holds auth state through a scan | 5 |
| **Detection Quality** (25) | Detection Accuracy — true-positive rate against known benchmarks | 15 |
| | Noise / False-Positive Rate — triage overhead the findings create | 10 |
| **Production Safety & Operability** (20) | Safe Production Scanning — passive/non-destructive modes, rate limiting, low instrumentation overhead | 12 |
| | CI/CD-Native Fit — drivable headlessly via CLI/API, not just GUI | 8 |
| **Developer Experience** (20) | Triage & Remediation Guidance — explains how to fix, not just what's wrong | 8 |
| | Auto-Remediation / Auto-PR | 5 |
| | Setup & Onboarding Friction — time/complexity to first useful scan | 7 |
| **Reporting & Extensibility** (5) | Reporting Quality / Exportability — dashboards, exports, Jira/Slack integration | 3 |
| | Extensibility / Custom Rules | 2 |

Weighting reflects that Coverage and Detection Quality are the core "does
it actually work" questions (55 combined), while Production Safety and DX
are weighted as genuinely first-class per the spec (20 each) rather than
token afterthoughts, with Reporting/Extensibility as a light-weight
nice-to-have category (5).

Each criterion needs a full rubric (what a 1/3/5 score means) written out
in the actual skill file — the table above is the category/name/weight
shape, not the final rubric text, which is an implementation-time
authoring detail.

## Data Flow

1. Skill runs `dast-bench criteria list` to check current state.
2. **First run (empty):** presents the baseline above, grouped by
   category with weights and per-category subtotals, and asks what should
   change before persisting anything.
3. **Revision (non-empty):** presents the current taxonomy back
   conversationally (summarized, not a raw dump) and asks what changed.
4. Evaluator and skill iterate in chat until agreed — no YAML is touched
   during this back-and-forth.
5. Skill applies the agreed changes as a sequence of individual CLI
   calls — `add-criterion` per new criterion, `update-criterion` per
   edit, `remove-criterion` per deletion, `set-weight` for quick
   weight-only tweaks — each a discrete, auditable, individually
   reproducible Bash invocation.
6. Skill re-runs `criteria list` to show the final persisted state,
   including any `warning: weights sum to X, expected 100.00` from the
   existing `validate_weights()` check.
7. If that warning appears, the skill treats the phase as unresolved and
   returns to step 4 — a taxonomy whose weights don't sum to 100 is
   exactly the condition `validate_weights()` exists to catch, and this
   skill must not declare success while it's failing.

## Error Handling

- `add-criterion` on a duplicate id, and `update-criterion` /
  `remove-criterion` / `set-weight` on an unknown id: existing
  `error: ...` + exit 1 pattern, extended identically to the two new
  commands. The skill relays these messages verbatim if one occurs rather
  than swallowing them.
- Weight-sum mismatches are a warning, not a hard CLI error (a taxonomy
  can be transiently unbalanced mid-edit), but the skill must not consider
  the phase complete while one is showing.
- Removing a criterion with existing vendor scores is not an error — an
  informational warning only. Orphaned historical scores are an
  acceptable, non-destructive outcome, consistent with this project's
  git-native audit-trail philosophy (nothing gets silently deleted from a
  vendor's record).

## Testing

`remove-criterion` and `update-criterion` get real TDD unit tests via
`CliRunner`, identical in shape and rigor to the existing
`tests/test_cli_criteria.py` tests — not-found errors, successful
removal/update, and the orphaned-score warning message. The skill prompt
file itself is not unit-testable (same reasoning the original core-library
plan used to defer all skill testing) — it is reviewed by the evaluator
reading the file once written, not by an automated test.
