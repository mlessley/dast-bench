# dast-shortlist Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the `dast-shortlist` Claude Code skill file, per `docs/superpowers/specs/2026-07-12-dast-shortlist-skill-design.md`.

**Architecture:** A single prompt file — no code, no CLI changes, no model changes. Every command it instructs an agent to call already exists (`candidate record-score`, `candidate set-status`, `candidate list`, `criteria list`, `dast-bench status`, `dast-bench render`). This is the smallest of the three skill plans so far (`dast-criteria` needed two new CLI commands; `dast-discovery` needed one CLI relocation; this one needs neither).

**Tech Stack:** None — this plan produces one Markdown file.

## Global Constraints

- No placeholder/TODO content.
- Every *mutation* to `data/candidates/*.yaml` must go through the `dast-bench candidate` CLI — the skill file must never instruct direct YAML edits. Reading a vendor's current record directly (`Read data/candidates/<id>.yaml`) for inspection is fine and does not violate this — only writes must go through the CLI.
- `--confidence` in every `record-score` call this skill instructs must be `paper` — `hands-on` confidence only ever comes from `dast-scan`.
- The skill must score exactly one vendor per invocation, with fresh, targeted research per criterion — never a broad pass, never reused `dast-discovery` notes presented as a formal score's evidence.
- Once every candidate is fully scored (no gaps per `dast-bench status`), the skill must drive the finalist/rejected decision to completion for every candidate — nobody left undecided.

---

### Task 1: The `dast-shortlist` skill file

**Files:**
- Create: `.claude/skills/dast-shortlist/SKILL.md`

**Interfaces:**
- Consumes: `dast-bench candidate {list, record-score, set-status}`, `dast-bench criteria list`, `dast-bench status`, `dast-bench render` (all already exist) — the skill only ever calls these via Bash, plus direct `Read` of a single vendor's YAML file for inspection (not mutation). Also consumes the `WebSearch`/`WebFetch` tools available in any Claude Code session.
- Produces: nothing consumed by another task — this is the only deliverable of this plan. Not unit-tested (a prompt file); reviewed by the evaluator reading it.

- [ ] **Step 1: Create the directory and write the complete skill file**

Create `.claude/skills/dast-shortlist/SKILL.md` with exactly this content:

````markdown
---
name: dast-shortlist
description: Use to research one candidate vendor against every criterion in the taxonomy, record scores with evidence, and — once every candidate is fully scored — drive the finalist/rejected decision to completion. Re-invocable anytime, one vendor per invocation.
---

# dast-shortlist

This skill fills in the **scorecard** — it researches one candidate vendor
against every criterion in the taxonomy (built by `dast-criteria`) and
records a score with evidence for each. Once every candidate in the list
(built by `dast-discovery`) is fully scored, it surfaces the weighted
comparison so the evaluator can decide finalists for `dast-scan`'s
hands-on phase. It never builds or revises the taxonomy or the candidate
list themselves.

Never edit `data/candidates/*.yaml` directly. Every score or status change
happens through `dast-bench candidate` CLI commands: `record-score`,
`set-status`, `list`. Reading a vendor's current record directly (its
`data/candidates/<id>.yaml` file) is fine for inspection — only writes
must go through the CLI.

**Score exactly one vendor per invocation.** Do not attempt to score every
candidate in a single run — each invocation researches and scores one
vendor's full set of criteria, then stops (or moves to Step 6 if that
completes the whole list).

## Step 1: Identify which vendor to score

If the evaluator names a specific vendor, use that. Otherwise, run
`dast-bench status` to see which candidates have missing scores, and
`dast-bench candidate list` to see current statuses, then suggest the
first `candidate`-status vendor with missing scores.

## Step 2: Check for existing scores (revision detection)

Read that vendor's record directly (`data/candidates/<id>.yaml`) to see
whether any scores already exist for it.

**If none exist (first time for this vendor):** proceed to Step 3 to
score every criterion.

**If some already exist (a revision):** show the evaluator what's already
recorded (criterion, score, evidence) and ask what should change — do not
silently re-research and overwrite scores the evaluator hasn't flagged.

## Step 3: Get the current taxonomy

Run `dast-bench criteria list` to get every criterion (category, name,
weight, rubric) this vendor needs to be scored against.

## Step 4: Research each criterion

For each unscored (or evaluator-flagged-for-revision) criterion, do fresh,
targeted research into this specific vendor's actual product —
documentation, product pages, technical write-ups, release notes —
specifically to answer that criterion's rubric. This is not a broad
"is this vendor good" pass like `dast-discovery`'s market research; it is
a deliberate, criterion-by-criterion look at what this vendor actually
does, tech-stack level.

If there isn't enough public information to confidently score a
criterion, say so explicitly in that criterion's evidence text (e.g.
"limited public information; inferred from X") rather than presenting a
falsely confident score.

## Step 5: Present the complete proposed scoring for review

Present every criterion's proposed score, evidence, and brief rationale
for this vendor together, not one at a time. Do not call any CLI command
yet. Let the evaluator adjust anything before you persist.

## Step 6: Persist the scores

Once the evaluator confirms, for each criterion:

```
dast-bench candidate record-score --vendor-id <id> --criterion-id <id> --score <score> --evidence <evidence> --confidence paper
```

`--confidence` is always `paper` at this phase.

If any command prints an `error: ...` message (e.g. an unknown criterion
or vendor id, which shouldn't occur given Steps 1–2 but could if the
taxonomy or candidate list changed mid-session), relay it verbatim to the
evaluator and ask how to proceed rather than retrying blindly.

## Step 7: Check whether every candidate is now fully scored

Run `dast-bench status`.

**If gaps remain** (this vendor or others still have missing scores):
confirm this vendor's scoring is complete, and stop here. The evaluator
can invoke you again for the next vendor.

**If there are no gaps at all** — every candidate fully scored against
every criterion — proceed to Step 8. This is the automatic transition
into finalist recommendation; the evaluator does not need to ask for it
separately.

## Step 8: Recommend finalists

Run `dast-bench render` to produce the weighted comparison (Markdown,
XLSX, and HTML dashboard under `reports/`). Present the ranked comparison
to the evaluator and ask them to decide finalist/rejected status for
**every** candidate — not just the obvious top performers. Nobody should
be left in `candidate` status once this step completes; resolving that is
the entire point of this phase.

For each decision:

```
dast-bench candidate set-status --id <id> --status finalist
```

or

```
dast-bench candidate set-status --id <id> --status rejected
```

## Step 9: Summarize

Summarize for the evaluator what was scored this round, and — if Step 8
ran — what finalist/rejected decisions were made, so they have a clear
record of what this invocation changed.
````

- [ ] **Step 2: Verify the file is valid, complete Markdown with YAML frontmatter**

Run: `head -5 .claude/skills/dast-shortlist/SKILL.md`
Expected output starts with:
```
---
name: dast-shortlist
description: Use to research one candidate vendor against every criterion in the taxonomy, record scores with evidence, and — once every candidate is fully scored — drive the finalist/rejected decision to completion. Re-invocable anytime, one vendor per invocation.
---
```

Run: `grep -c '^## Step' .claude/skills/dast-shortlist/SKILL.md`
Expected: `9` (one per numbered step — confirms none were dropped while writing the file).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/dast-shortlist/SKILL.md
git commit -m "Add dast-shortlist skill"
```

---

## Self-Review Notes

- **Spec coverage:** the design doc's Architecture section (no new CLI, direct-read-for-inspection allowed), Data Flow (all 9 steps present, 1:1 with the skill file's 9 numbered steps — no condensing needed this time since the design doc's flow was already skill-file-shaped), Error Handling (relay `error:` verbatim, uncertain research stated explicitly, evaluator adjustments happen pre-persistence), and Testing (no code, not unit-tested, matching `dast-criteria`/`dast-discovery` precedent) are all covered.
- **Placeholder scan:** no TODO/TBD markers; the skill file's content is complete, including exact CLI invocation syntax for every command it instructs.
- **Type consistency:** `--confidence paper` matches the `Confidence` enum's actual value (`PAPER = "paper"` in `core/models.py:22`) exactly — verified against the real enum, not assumed. `record-score`'s flag names (`--vendor-id`, `--criterion-id`, `--score`, `--evidence`, `--confidence`) and `set-status`'s (`--id`, `--status`) match the existing, already-implemented and already-tested commands exactly — no new flags invented.
