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
