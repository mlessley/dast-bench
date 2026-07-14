# dast-report Narrative Template Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Step 4 of `.claude/skills/dast-report/SKILL.md` with a restructured narrative-composition process that adds a Financial Sector Fit framing block, a "Where They Win" vendor comparison table, per-category takeaways, and Wins/Gaps bulleted formatting for per-vendor sections.

**Architecture:** Single prompt-file edit, full-file replacement. Frontmatter, the intro paragraph, and Steps 1-3/5-6 stay byte-for-byte unchanged; only Step 4's body is replaced with a six-part composition sequence.

**Tech Stack:** Markdown prompt file (`.claude/skills/dast-report/SKILL.md`) — no application code, no pytest. Verification is content-based (grep/diff against the pre-edit file via git).

## Global Constraints

- This is a prompt-file edit, not application code — there is no TDD/pytest cycle. Verification steps use `grep`/`diff` to confirm structural content, not a test runner.
- Frontmatter, the intro paragraph, and Steps 1, 2, 3, 5, and 6 of `.claude/skills/dast-report/SKILL.md` must remain byte-for-byte identical to their current committed content — only Step 4's body changes.
- `dast-report` remains strictly read-only over `data/criteria.yaml`/`data/candidates/*.yaml` — this plan does not touch that contract.
- No changes to `core/render/`, any CLI command, or `reports/`'s gitignore policy.
- Actually re-invoking the `dast-report` skill against real data to see the new format in action is a follow-up the evaluator can request afterward — it is explicitly not a task in this plan (see Testing in the design spec).

---

### Task 1: Replace Step 4 with the restructured narrative-composition process

**Files:**
- Modify: `.claude/skills/dast-report/SKILL.md` (full-file replacement)

**Interfaces:**
- N/A — this is a standalone prompt-file edit with no other task depending on it, and no function signatures involved.

- [ ] **Step 1: Write the complete new file content**

Replace the entire contents of `.claude/skills/dast-report/SKILL.md` with:

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
`reports/comparison-matrix.md` so the narrative's weighted-total numbers,
and its Category Breakdown numbers, match the deterministic render
exactly, not a re-derived figure.

Compose the summary in this order:

**1. Financial Sector Fit.** Before any vendor-specific content, write 2-3
sentences anchoring the whole report to the evaluator's actual buyer
context (Fortune 500 financial services, unless the evaluator has
specified a different context) — name the 2-3 dimensions that matter most
for that risk profile (e.g. regulatory compliance mapping, business-logic/
authorization testing, data-residency control) and note that a tool's
ranking should be read through that lens, not just the raw weighted
total. Keep this brief — a framing paragraph, not a new analysis section.

**2. Overview.** Candidate count, taxonomy size, which vendors reached
which phase, and the weighted-total comparison table — unchanged in
substance from what this section always covered.

**3. Where They Win.** A single table contrasting every finalist/evaluated
vendor (plus any rejected vendor worth a comparison row — evaluator's
judgment) side by side:

```markdown
## Where They Win

| Vendor | Status | Core Strengths / Best For | Critical Enterprise Gaps |
|---|---|---|---|
| <name> | <status, e.g. "Evaluated" or "Paper only"> | <2-4 named strengths tied to specific criteria/scores> | <2-3 named gaps tied to specific criteria/scores> |
```

Ground every cell in specific evidence already recorded for that vendor (a
criterion name and score, or a specific piece of evidence text) — never a
vague adjective with nothing behind it.

**4. Per-vendor sections.** Keep one section per finalist/evaluated
vendor, but write each vendor's content as two bulleted groups instead of
dense paragraphs:

```markdown
## <Vendor Name> — <one-line status/positioning>

**The Wins:**
- <specific strength, citing a criterion/score/evidence>
- <specific strength, citing a criterion/score/evidence>

**The Gaps:**
- <specific weakness, citing a criterion/score/evidence>
- <specific weakness, citing a criterion/score/evidence>
```

Still cite specific evidence, not just the weighted-total number, and
still cover notable trade-offs among finalist/evaluated vendors — only the
formatting changes (bullets under bold prefixes instead of prose
paragraphs), not the depth or rigor of the analysis.

**5. Category Takeaways.** One bullet per category, in the same order
`dast-bench criteria list` reports them, each naming the category's weight
and either which vendor(s) lead it and why, or a market-wide gap if every
vendor scores low on it:

```markdown
## Category Takeaways

- **<Category Name> (<weight>):** <one-sentence interpretive takeaway,
  grounded in the Category Breakdown numbers from comparison-matrix.md>
```

**6. Trade-offs worth flagging.** Cross-cutting caveats about scoring
methodology (e.g. false-positive-rate's coarseness), not per-vendor or
per-category content — same purpose this section always served.

Mention rejected/still-candidate vendors in one line each (in the Overview
or the Where They Win table — evaluator's judgment on which reads better
for a given evaluation), e.g. "excluded: X (insufficient API coverage), Y
(still being scored)", not with the same depth as finalist/evaluated
vendors.

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

- [ ] **Step 2: Verify the top-level step structure is unchanged**

Run: `grep -c '^## Step' .claude/skills/dast-report/SKILL.md`
Expected: `6` (still exactly six top-level steps — the new content lives as numbered sub-items *inside* Step 4, not as new top-level steps)

Run: `grep -n '^## Step' .claude/skills/dast-report/SKILL.md`
Expected:
```
24:## Step 1: Check for gaps
35:## Step 2: Render
41:## Step 3: Identify finalist/evaluated vendors
48:## Step 4: Compose the narrative
```
(followed by the new, longer Step 4 body, then `## Step 5: Write the narrative summary` and `## Step 6: Summarize` — exact line numbers for Steps 5/6 will differ from the original since Step 4 is now longer; only Steps 1-4's line numbers must match the original file exactly, confirming nothing was inserted before Step 4.)

- [ ] **Step 3: Verify the new Step 4 sub-structure is present**

Run: `grep -c '^\*\*[1-6]\. ' .claude/skills/dast-report/SKILL.md`
Expected: `6` (the six numbered sub-items: Financial Sector Fit, Overview, Where They Win, Per-vendor sections, Category Takeaways, Trade-offs worth flagging)

Run: `grep -c '^## Where They Win$' .claude/skills/dast-report/SKILL.md`
Expected: `1`

Run: `grep -c '^## Category Takeaways$' .claude/skills/dast-report/SKILL.md`
Expected: `1`

Run: `grep -c '\*\*The Wins:\*\*' .claude/skills/dast-report/SKILL.md`
Expected: `1`

Run: `grep -c '\*\*The Gaps:\*\*' .claude/skills/dast-report/SKILL.md`
Expected: `1`

- [ ] **Step 4: Verify the unchanged regions are byte-for-byte identical to the pre-edit file**

Use git to compare the frontmatter/intro/Steps 1-3 region and the Step 5-6 region against the committed pre-edit version (`HEAD`, before this task's commit):

```bash
git show HEAD:.claude/skills/dast-report/SKILL.md | sed -n '1,/^## Step 4/p' | sed '$d' > /tmp/before-head.md
sed -n '1,/^## Step 4/p' .claude/skills/dast-report/SKILL.md | sed '$d' > /tmp/after-head.md
diff /tmp/before-head.md /tmp/after-head.md
```
Expected: no output (files identical — frontmatter, intro paragraph, and Steps 1-3 are untouched)

```bash
git show HEAD:.claude/skills/dast-report/SKILL.md | sed -n '/^## Step 5/,$p' > /tmp/before-tail.md
sed -n '/^## Step 5/,$p' .claude/skills/dast-report/SKILL.md > /tmp/after-tail.md
diff /tmp/before-tail.md /tmp/after-tail.md
```
Expected: no output (files identical — Step 5 and Step 6 are untouched)

If either `diff` produces output, the full-file replacement introduced an unintended change to a region that must stay byte-for-byte identical — fix it and re-run both checks before proceeding.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/dast-report/SKILL.md
git commit -m "Restructure dast-report narrative: Financial Sector Fit framing, Where They Win table, Category Takeaways, Wins/Gaps formatting"
```

---

## Follow-up (not a task in this plan)

Once this is merged, the true acceptance test is re-invoking the `dast-report` skill against the real current data (33 criteria, 3 candidates) and inspecting the regenerated `reports/executive-summary.md` — the grep/diff checks above only confirm the instructions are structurally present, not that a real invocation produces sensible output. That real re-invocation is a separate, subsequent action for the evaluator to request; it is intentionally not a task here, per the design spec's Testing section.
