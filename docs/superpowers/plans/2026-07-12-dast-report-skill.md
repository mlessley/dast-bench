# dast-report Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the `dast-report` Claude Code skill file, per `docs/superpowers/specs/2026-07-12-dast-report-skill-design.md`, and refresh the README's `## Status` section, which has drifted significantly stale (it still describes the CI pipeline as unverified and four now-built skills as "not yet built").

**Architecture:** A single prompt file — no code, no CLI changes, no model changes. Every command it instructs an agent to call already exists (`dast-bench status`, `dast-bench render`, `candidate list`, `criteria list`). This is the second plan (after `dast-shortlist`) to need zero new CLI commands.

**Tech Stack:** None — this plan produces one Markdown skill file and a documentation edit.

## Global Constraints

- No placeholder/TODO content.
- The skill must never instruct direct edits to `data/criteria.yaml` or `data/candidates/*.yaml` — those stay read-only in this skill (every mutation there is some earlier skill's job).
- `reports/executive-summary.md` is the one exception: the skill writes it directly, not through the CLI, since `reports/` is regenerable output, not the source of truth — the same way `dast-bench render` already writes directly there.
- If gaps are reported by `dast-bench status`, the skill must ask the evaluator whether to proceed or hold off — never render silently past a reported gap.
- The narrative must focus on finalist/evaluated vendors; rejected/still-candidate vendors get at most a one-line mention.
- If the evaluator proceeds despite gaps, the summary must include an explicit caveats section naming them.

---

### Task 1: The `dast-report` skill file, plus a README status refresh

**Files:**
- Create: `.claude/skills/dast-report/SKILL.md`
- Modify: `README.md` (the `## Status` section — stale since before `dast-criteria`/`dast-discovery`/`dast-shortlist`/`dast-scan` were built)

**Interfaces:**
- Consumes: `dast-bench {status, render, candidate list, criteria list}` (all already exist) — the skill only ever calls these via Bash, plus direct `Read` of vendor YAML files and the rendered `reports/comparison-matrix.md` (inspection only, no writes to `data/`), and a direct `Write` of `reports/executive-summary.md` (the one documented exception to CLI-only mutation, since `reports/` isn't the source of truth).
- Produces: nothing consumed by another task — this is the only deliverable of this plan, and the final skill of the original five-skill dast-bench workflow.

- [ ] **Step 1: Create the directory and write the complete skill file**

Create `.claude/skills/dast-report/SKILL.md` with exactly this content:

````markdown
---
name: dast-report
description: Use to check for scoring/weight gaps, render the SSoT into presentation artifacts, and write a narrative summary of the results focused on finalist/evaluated vendors. Re-invocable anytime.
---

# dast-report

This skill renders the single source of truth (`criteria.yaml` plus every
`candidates/*.yaml`) into presentation artifacts, and adds two things a bare
CLI invocation can't: it checks for gaps first and asks before rendering an
incomplete comparison, and it writes a narrative summary interpreting the
results — the one thing a deterministic render can't produce. It never
decides criteria, candidates, scores, or finalists — every earlier skill's
job.

Never edit `data/criteria.yaml` or `data/candidates/*.yaml` directly — this
skill only reads them. The one file it writes directly, rather than
through the CLI, is `reports/executive-summary.md` (see Step 5) —
`reports/` is regenerable output, not the source of truth, and
`dast-bench render` already writes directly there too. If any command
exits with an `error: ...` message, relay it verbatim and ask the evaluator
how to proceed, rather than retrying blindly.

## Step 1: Check for gaps

Run `dast-bench status`.

**If gaps are reported** (missing scores for any vendor, or a weight-total
warning): present them to the evaluator and ask whether to proceed with
rendering anyway, or hold off until they're fixed. If the evaluator says
hold off, stop here — do not render, do not write a summary.

**If no gaps:** proceed to Step 2.

## Step 2: Render

Run `dast-bench render`. This writes `reports/comparison-matrix.md`,
`reports/comparison-matrix.xlsx`, `reports/scorecard-<id>.md` per vendor,
and `reports/dashboard.html` — deterministically, unchanged by this skill.

## Step 3: Identify finalist/evaluated vendors

Run `dast-bench candidate list`. Note which vendors are `finalist` or
`evaluated` — the narrative in Step 4 focuses on these. Vendors still
`candidate` or `rejected` get at most a one-line mention, not equal
analytical treatment.

## Step 4: Compose the narrative

For each finalist/evaluated vendor, read its record directly
(`data/candidates/<id>.yaml`) for full evidence: scores, evidence text,
hands-on results, observations. Run `dast-bench criteria list` for rubric
and weight context, and read the freshly-written
`reports/comparison-matrix.md` so the narrative's weighted-total numbers
match the deterministic render exactly, not a re-derived figure.

Write a narrative that explains, in prose, who's leading and why — citing
specific evidence, not just the weighted-total number — and any notable
trade-offs among finalist/evaluated vendors (e.g. one leads on detection
accuracy but another has a much lower false-positive rate). Mention
rejected/still-candidate vendors in one line each (e.g. "excluded: X
(insufficient API coverage), Y (still being scored)"), not with the same
depth as finalist/evaluated vendors.

If the evaluator chose to proceed despite gaps in Step 1, include an
explicit caveats section naming exactly which gaps were outstanding at
render time — do not bury or omit this.

If there are zero vendors at all, or zero finalist/evaluated vendors
specifically (e.g. still mid-`dast-shortlist`), say so plainly instead of
forcing commentary onto an empty or premature comparison — skip Step 5's
file write and tell the evaluator why, rather than writing an empty or
vacuous summary.

## Step 5: Write the narrative summary

Write the composed narrative to `reports/executive-summary.md` directly
(not via the CLI). Begin the file with a one-line header noting it is
skill-authored and not part of `dast-bench render`'s deterministic output,
e.g.:

```markdown
# Executive Summary

_Skill-authored narrative — not regenerated by `dast-bench render`. Rerun
`dast-report` to refresh._
```

## Step 6: Summarize

Tell the evaluator what was rendered, where the artifacts live
(`reports/`), and present the narrative summary.
````

- [ ] **Step 2: Verify the file is valid, complete Markdown with YAML frontmatter**

Run: `head -5 .claude/skills/dast-report/SKILL.md`
Expected output starts with:
```
---
name: dast-report
description: Use to check for scoring/weight gaps, render the SSoT into presentation artifacts, and write a narrative summary of the results focused on finalist/evaluated vendors. Re-invocable anytime.
---
```

Run: `grep -c '^## Step' .claude/skills/dast-report/SKILL.md`
Expected: `6` (one per numbered step — confirms none were dropped while writing the file).

- [ ] **Step 3: Refresh the README's Status section**

The README's `## Status` section is significantly stale — it predates
`dast-criteria`, `dast-discovery`, `dast-shortlist`, and `dast-scan`, and
still describes the CI pipeline as not yet dispatched (it was
live-verified against both targets during the `dast-scan` work). The
current text (`README.md` lines 23-44) reads:

```markdown
## Status

**Phase 1 core library and CLI: done.** Five command groups (`criteria`,
`candidate`, `scan`, `status`, `render`), YAML round-tripping via Pydantic,
and Markdown/XLSX/HTML report rendering are implemented and tested (55
tests passing).

**DAST benchmark CI pipeline: built, not yet live-verified.** A GitHub
Actions `workflow_dispatch` pipeline
(`.github/workflows/dast-benchmark.yml`) spins up OWASP Juice Shop or VAmPI
as an ephemeral service container, runs a ZAP full active scan, and uploads
both the raw and (for ZAP) normalized report as build artifacts. It hasn't
been dispatched against a real GitHub-hosted run yet — see the plan's
manual-verification note.

**Not yet built:**
- The `dast-scan` Claude Code skill (the orchestrator that will trigger
  the CI pipeline above, download its artifacts, and call `ingest-scan-result`).
- The `dast-criteria`, `dast-discovery`, `dast-shortlist`, `dast-report` skills.
- Production-safe scanning (drift/misconfiguration detection against a real
  or staging target, as opposed to the ephemeral benchmark targets above) —
  deliberately deferred; see the roadmap doc.
```

Replace it with:

```markdown
## Status

**Phase 1 core library and CLI: done.** Six command groups (`criteria`,
`candidate`, `scan`, `benchmark`, `status`, `render`), YAML round-tripping
via Pydantic, and Markdown/XLSX/HTML report rendering are implemented and
tested (69 tests passing).

**DAST benchmark CI pipeline: built and live-verified.** A GitHub Actions
`workflow_dispatch` pipeline (`.github/workflows/dast-benchmark.yml`) spins
up OWASP Juice Shop or VAmPI as an ephemeral service container, runs a ZAP
full active scan, and uploads both the raw and (for ZAP) normalized report
as build artifacts. Dispatched against both targets on GitHub: Juice Shop
found 12 real findings, VAmPI found 4.

**Four of five Claude Code skills built:** `dast-criteria` (criteria
taxonomy), `dast-discovery` (candidate vendor list), `dast-shortlist`
(scoring + finalist decisions), and `dast-scan` (hands-on benchmark
scanning + evaluated-status transition) are all implemented. `dast-report`
(final presentation/narrative layer) completes the original five-skill
workflow.

**Not yet built:**
- `dast-onboard-tool` — a sixth skill (not part of the original five) for
  wiring a *new* DAST tool into the CI pipeline above; a code-change task
  distinct from the others' YAML-data-mutation shape.
- Production-safe scanning (drift/misconfiguration detection against a real
  or staging target, as opposed to the ephemeral benchmark targets above) —
  deliberately deferred; see the roadmap doc.
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dast-report/SKILL.md README.md
git commit -m "Add dast-report skill and refresh README status"
```

---

## Self-Review Notes

- **Spec coverage:** the design doc's Goals (gap-aware gate, deterministic
  render unchanged, narrative summary focused on finalist/evaluated
  vendors, caveats section on proceed-despite-gaps, empty/premature-state
  handling), Non-Goals (no render reimplementation, no criteria/candidate/
  score/finalist decisions), Architecture (zero new CLI, the one
  direct-write exception for `reports/executive-summary.md`), Data Flow
  (all 6 steps present, 1:1 with the skill file's 6 numbered steps), Error
  Handling (verbatim relay, empty-state handling), and Testing (no code,
  not unit-tested) are all covered.
- **Placeholder scan:** no TODO/TBD markers; the skill file's content is
  complete, including the exact header text for the summary file.
- **Type consistency:** the CLI commands and flags referenced
  (`dast-bench status`, `dast-bench render`, `dast-bench candidate list`,
  `dast-bench criteria list`) all exist unchanged in `core/cli.py` — no new
  flags invented, matching the "zero code changes" architecture decision.
