# dast-shortlist Skill Design

## Purpose & Context

`dast-shortlist` is Phase 3 of the dast-bench evaluation workflow: it
researches each candidate vendor (built by `dast-discovery`) against every
criterion in the taxonomy (built by `dast-criteria`), records a score with
evidence for each, and — once every candidate is fully scored — surfaces
the weighted comparison so the evaluator can decide which vendors become
finalists for `dast-scan`'s hands-on phase. It fills in the scorecard;
`dast-criteria` and `dast-discovery` built the taxonomy and the candidate
list respectively, and neither of them touches vendor scores.

`dast-criteria` and `dast-discovery` (both built 2026-07-12) are the
precedent this design follows: Claude Code skills (prompt files, no code
of their own) that converse with the evaluator before persisting anything,
mutate data only through the existing `dast-bench` CLI, and — where a
gap in the CLI blocks the skill's job — add the smallest CLI change that
closes it. `dast-shortlist` needs no such change: `candidate record-score`,
`candidate set-status`, `candidate list`, `criteria list`,
`dast-bench status`, and `dast-bench render` already cover everything this
phase requires.

## Goals

- Score exactly one vendor per invocation against every criterion in the
  current taxonomy, with fresh, targeted research per criterion — not
  reused, loosely-related notes from discovery, and not a single broad
  "is this vendor good" pass.
- Every score's evidence must be specific and defensible: what the rubric
  actually says a 1/3/5 means, and what was found (or not found) for this
  vendor against that specific rubric.
- Support revision: if invoked for a vendor that already has some or all
  scores recorded, show the evaluator what's already there and ask what
  should change, rather than blindly re-researching everything.
- Once every candidate is fully scored (no gaps per `dast-bench status`),
  automatically surface the weighted comparison and drive the
  finalist/rejected decision to completion for every vendor — the whole
  point of this phase is that nobody is left undecided at the end of it.
- Never touch the criteria taxonomy or the candidate list itself — those
  are `dast-criteria`'s and `dast-discovery`'s jobs.

## Non-Goals / Out of Scope

- Building or revising the criteria taxonomy — `dast-criteria`'s job.
- Building or revising the candidate list — `dast-discovery`'s job.
- Hands-on testing of finalists — `dast-scan`'s job.
- Any new CLI command or data model change — this plan is prompt-file-only
  (see Architecture).

## Architecture

`dast-shortlist` is a Claude Code skill: a prompt file at
`.claude/skills/dast-shortlist/SKILL.md`, invoked as `/dast-shortlist`. It
contains no code — it is instructions for an LLM agent that identifies one
vendor to score, researches that vendor against every criterion, presents
the complete proposed scoring for evaluator review before persisting
anything, records scores via the CLI, and — once every candidate is fully
scored — drives the finalist decision to completion.

**No new CLI commands are needed.** `candidate record-score`,
`candidate set-status`, `candidate list`, `criteria list`,
`dast-bench status`, and `dast-bench render` already provide everything
this phase requires. Reading a vendor's current record directly
(`data/candidates/<id>.yaml`, via `Read`) for inspection — to check what's
already scored before deciding what needs research this round — is fine
and does not violate the CLI-only rule, which governs *mutation*, not
inspection; every other existing command in this codebase that reads
state (`status`, `render`) does so by reading YAML directly too, not
through some indirect API.

## Data Flow

1. Skill identifies which vendor to score this round — the evaluator can
   name one directly, or if not specified, the skill suggests the first
   `candidate`-status vendor that `dast-bench status` shows has missing
   scores.
2. Skill reads that vendor's current record directly
   (`data/candidates/<id>.yaml`) to see whether any scores already exist.
   If some criteria are already scored, this is a revision: the skill
   shows what's there and asks what should change, rather than
   re-researching everything from scratch.
3. Skill runs `dast-bench criteria list` to get the full taxonomy
   (categories, criteria, weights, rubrics) to score against.
4. For each unscored (or evaluator-flagged-for-revision) criterion, the
   skill does fresh, targeted research into that vendor's actual product
   — documentation, product pages, technical write-ups — specifically to
   answer that criterion's rubric, not a broad market-positioning pass.
5. Skill presents the complete set of proposed scores, evidence, and
   rationale for this vendor — every criterion at once, not one at a
   time — for the evaluator to review and adjust. Nothing is persisted
   yet.
6. Once confirmed: `dast-bench candidate record-score --vendor-id <id>
   --criterion-id <id> --score <score> --evidence <evidence> --confidence
   paper` for each criterion. `--confidence` is always `paper` at this
   phase — `hands-on` confidence only comes from `dast-scan`.
7. Skill runs `dast-bench status`. If gaps remain anywhere (this vendor or
   others), it confirms this vendor's scoring is complete and stops there.
   If `status` reports no gaps at all — every candidate fully scored
   against every criterion — it automatically moves into finalist
   recommendation: runs `dast-bench render`, presents the weighted
   comparison to the evaluator, and asks them to decide finalist/rejected
   status for every candidate, not leaving any undecided.
8. For each decision: `dast-bench candidate set-status --id <id> --status
   finalist` or `--status rejected`.
9. Skill summarizes what was scored and/or decided as confirmation.

## Error Handling

- `record-score`/`set-status` reporting an unknown criterion or vendor id
  — shouldn't occur given the flow reads current state first, but if it
  happens, relay the `error: ...` message verbatim and ask the evaluator
  how to proceed, consistent with `dast-criteria`/`dast-discovery`.
- Research uncertainty: if there isn't enough public information to
  confidently score a criterion, the skill says so explicitly in the
  evidence text (e.g. "limited public information; inferred from X") and
  flags it during the Step 5 review, rather than presenting a falsely
  confident score.
- Evaluator disagreement with a proposed score is handled entirely within
  Step 5's review — nothing has been persisted at that point, so this is
  conversation, not a rollback.

## Testing

No code changes in this plan — zero new CLI commands, zero model changes.
The skill file itself is not unit-tested (same reasoning as
`dast-criteria` and `dast-discovery`) — reviewed by the evaluator reading
it once written, not by an automated test.
