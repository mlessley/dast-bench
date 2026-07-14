# Report Disclaimer & Hyperlinks (Skills) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `dast-report` and `dast-shortlist`'s narrative-writing instructions to add vendor-name cross-links, a strengthened draft/sample disclaimer, a rule against narrating criteria-taxonomy revision history, and a soft nudge to cite real source URLs.

**Architecture:** Two independent prompt-file edits (`.claude/skills/dast-report/SKILL.md`, `.claude/skills/dast-shortlist/SKILL.md`) — no application code, no pytest. Verification is grep/diff-based, matching the earlier `dast-report` narrative-template plan.

**Tech Stack:** Markdown prompt files. No new dependencies.

## Global Constraints

- This is Track B (skill instructions) of the disclaimer/hyperlinks spec. Track A (code: `core/render/`) is a separate, already-completed plan.
- No application code, no CLI changes — both files are Claude Code skill prompts read by an LLM at invocation time, not parsed by any script.
- `dast-report`'s frontmatter, intro paragraph, and Steps 1-3 must stay byte-for-byte identical to their pre-edit content — only Step 4 and Step 5 change.
- `dast-shortlist`'s frontmatter, intro paragraph, and every step except Step 4 must stay byte-for-byte identical to their pre-edit content — only Step 4 changes (one new paragraph appended to its existing two).
- Neither skill's read-only contract over `data/criteria.yaml`/`data/candidates/*.yaml` changes.
- Use `uv run pytest` if any test run is needed (it isn't for this track); never modify `uv.lock`.

---

### Task 1: Update `dast-report`'s Step 4/Step 5 — vendor links, no-history rule, disclaimer

**Files:**
- Modify: `.claude/skills/dast-report/SKILL.md` (full-file replacement)

**Interfaces:**
- N/A — standalone prompt-file edit, independent of Task 2.

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
total. Keep this brief — a framing paragraph, not a new analysis section:

```markdown
## Financial Sector Fit

<2-3 sentences naming the dimensions that matter most for the buyer's
risk profile and framing how to read the rankings below in light of it>
```

**2. Overview.** Candidate count, taxonomy size, which vendors reached
which phase, and the weighted-total comparison table — unchanged in
substance from what this section always covered.

**3. Where They Win.** A single table contrasting every finalist/evaluated
vendor (plus any rejected vendor worth a comparison row — evaluator's
judgment) side by side, with each vendor's name linked to its full
scorecard (a relative link, since both files live in the same directory
whether that's `reports/` or `sample-report/`):

```markdown
## Where They Win

| Vendor | Status | Core Strengths / Best For | Critical Enterprise Gaps |
|---|---|---|---|
| [<name>](scorecard-<id>.md) | <status, e.g. "Evaluated" or "Paper only"> | <2-4 named strengths tied to specific criteria/scores> | <2-3 named gaps tied to specific criteria/scores> |
```

Ground every cell in specific evidence already recorded for that vendor (a
criterion name and score, or a specific piece of evidence text) — never a
vague adjective with nothing behind it.

**4. Per-vendor sections.** Keep one section per finalist/evaluated
vendor, with the heading itself linked to that vendor's scorecard, and
write each vendor's content as two bulleted groups instead of dense
paragraphs:

```markdown
## [<Vendor Name>](scorecard-<id>.md) — <one-line status/positioning>

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

Across all of this, describe the criteria taxonomy's *current* state
only — count, categories, weights — never its revision history (e.g.
"expanded from 12 to 29 to 33 criteria," "a senior-architect review added
four criteria," or phrasing a score comparison as "previously tied at
X"). That history is internal process detail with no value to a reader
evaluating the tools, and it undermines the report reading as a finished
artifact rather than a work-in-progress log. This doesn't apply to
methodology caveats that explain how to correctly interpret a score
(e.g. what the benchmark ground truth does and doesn't cover) — those are
legitimate and should stay; the rule targets only narrating how the
taxonomy or process evolved over time.

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
combined with the same draft/sample framing every other generated
artifact carries, e.g.:

```markdown
# Executive Summary

> 🚧 Draft/sample output demonstrating what dast-bench produces — not a
> final vendor recommendation, illustrative of a real evaluation in
> progress. Skill-authored narrative — not regenerated by `dast-bench
> render`; rerun `dast-report` to refresh.
```

## Step 6: Summarize

Tell the evaluator what was rendered, where the artifacts live
(`reports/`), and present the narrative summary.
````

- [ ] **Step 2: Verify the head region (frontmatter/intro/Steps 1-3) is byte-for-byte unchanged**

```bash
git show HEAD:.claude/skills/dast-report/SKILL.md | sed -n '1,/^## Step 4/p' | sed '$d' > /tmp/dr-before-head.md
sed -n '1,/^## Step 4/p' .claude/skills/dast-report/SKILL.md | sed '$d' > /tmp/dr-after-head.md
diff /tmp/dr-before-head.md /tmp/dr-after-head.md
```
Expected: no output (identical — frontmatter, intro, and Steps 1-3 untouched).

- [ ] **Step 3: Verify the new content markers are present**

Run: `grep -c '^## Step' .claude/skills/dast-report/SKILL.md`
Expected: `6`

Run: `grep -c 'scorecard-<id>.md' .claude/skills/dast-report/SKILL.md`
Expected: `3` (the pre-existing Step 2 mention of `reports/scorecard-<id>.md`, plus the two new occurrences: one in the Where They Win table template, one in the per-vendor heading template)

Run: `grep -c "describe the criteria taxonomy's \*current\* state" .claude/skills/dast-report/SKILL.md`
Expected: `1`

Run: `grep -c '🚧 Draft/sample output' .claude/skills/dast-report/SKILL.md`
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dast-report/SKILL.md
git commit -m "Add vendor cross-links, no-history rule, and disclaimer to dast-report narrative"
```

---

### Task 2: Update `dast-shortlist`'s Step 4 — soft nudge to cite real source URLs

**Files:**
- Modify: `.claude/skills/dast-shortlist/SKILL.md` (full-file replacement)

**Interfaces:**
- N/A — standalone prompt-file edit, independent of Task 1.

- [ ] **Step 1: Write the complete new file content**

Replace the entire contents of `.claude/skills/dast-shortlist/SKILL.md` with:

```markdown
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

When a specific, locatable source exists — a blog post, a docs page, a
GitHub repo, a vendor's own materials — cite its actual URL in the
evidence text (e.g. "Source: vendor.com/docs/feature-page"). Rendered
scorecards automatically turn these into clickable links, so a real
citation is more useful evidence than a bare mention of a product or
company name. This is guidance, not a hard requirement — some evidence is
legitimately "inferred, low confidence" with no single citable source,
and that's fine to say plainly instead of manufacturing a citation.

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
```

- [ ] **Step 2: Verify the head region (frontmatter/intro/Steps 1-3) is byte-for-byte unchanged**

```bash
git show HEAD:.claude/skills/dast-shortlist/SKILL.md | sed -n '1,/^## Step 4/p' | sed '$d' > /tmp/ds-before-head.md
sed -n '1,/^## Step 4/p' .claude/skills/dast-shortlist/SKILL.md | sed '$d' > /tmp/ds-after-head.md
diff /tmp/ds-before-head.md /tmp/ds-after-head.md
```
Expected: no output (identical).

- [ ] **Step 3: Verify the tail region (Step 5 onward) is byte-for-byte unchanged**

```bash
git show HEAD:.claude/skills/dast-shortlist/SKILL.md | sed -n '/^## Step 5/,$p' > /tmp/ds-before-tail.md
sed -n '/^## Step 5/,$p' .claude/skills/dast-shortlist/SKILL.md > /tmp/ds-after-tail.md
diff /tmp/ds-before-tail.md /tmp/ds-after-tail.md
```
Expected: no output (identical — only Step 4 changes).

- [ ] **Step 4: Verify the new nudge is present**

Run: `grep -c '^## Step' .claude/skills/dast-shortlist/SKILL.md`
Expected: `9`

Run: `grep -c 'cite its actual URL' .claude/skills/dast-shortlist/SKILL.md`
Expected: `1`

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/dast-shortlist/SKILL.md
git commit -m "Add soft nudge to cite real source URLs in evidence"
```
