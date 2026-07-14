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

Never edit `data/candidates/*.yaml` or `data/research-cache/*.yaml`
directly. Every score or status change happens through `dast-bench
candidate` CLI commands: `record-score`, `set-status`, `list`. Every
research-cache read/write happens through `dast-bench cache` CLI
commands: `show`, `record`, `invalidate`. Reading a vendor's current
record directly (its `data/candidates/<id>.yaml` file) is fine for
inspection — only writes must go through the CLI.

**Score exactly one vendor per invocation.** Do not attempt to score every
candidate in a single run — each invocation researches and scores one
vendor's full set of criteria, then stops (or moves to Step 9 if that
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

For each unscored (or evaluator-flagged-for-revision) criterion, first
check whether cached research already exists and is still valid:

```
dast-bench cache show --vendor-id <id> --criterion-id <criterion-id>
```

**If a cache entry exists and its `stale` flag is `false`:** reuse its
queries/findings directly to compose the score and evidence — no new
`WebSearch`/`WebFetch` call is needed for this criterion. Skip ahead to
scoring it.

**If no cache entry exists, or it's marked `stale`:** do fresh, targeted
research into this specific vendor's actual product — documentation,
product pages, technical write-ups, release notes — specifically to
answer that criterion's rubric. This is not a broad "is this vendor good"
pass like `dast-discovery`'s market research; it is a deliberate,
criterion-by-criterion look at what this vendor actually does, tech-stack
level. Use the vendor's own named product lines/modules captured by
`dast-discovery` (read its observations) as search vocabulary where
relevant — a generic rubric-language search (e.g. "ASPM integration")
surfaces a vendor's own specifically-named product (e.g. "Veracode Risk
Manager") far less reliably than a search that already knows the
product's name.

After fresh research, record what was found so a future re-run can reuse
it:

```
dast-bench cache record --vendor-id <id> --criterion-id <criterion-id> --query "<query used>" [--query "<another query>" ...] --findings-file <path-to-json>
```

`--findings-file` points to a small JSON file you write with the
URLs/snippets found: `[{"url": "...", "snippet": "..."}, ...]`.

If there isn't enough public information to confidently score a criterion
(fresh or cached), say so explicitly in that criterion's evidence text
(e.g. "limited public information; inferred from X") rather than
presenting a falsely confident score.

When a specific, locatable source exists — a blog post, a docs page, a
GitHub repo, a vendor's own materials — cite its actual URL in the
evidence text (e.g. "Source: vendor.com/docs/feature-page"). Rendered
scorecards automatically turn these into clickable links, so a real
citation is more useful evidence than a bare mention of a product or
company name. This is guidance, not a hard requirement — some evidence is
legitimately "inferred, low confidence" with no single citable source,
and that's fine to say plainly instead of manufacturing a citation.

## Step 5: Gap-check weak-scored criteria

Once every criterion has an initial score, identify any that scored
`≤2.5`. For each one, dispatch a **fresh subagent** — with no shared
context from the research that produced the original score — instructed
to independently investigate that specific vendor+criterion pair, using
the vendor's own product terminology from `dast-discovery`'s
observations, holding itself to the same real-citation discipline as the
primary research (never presenting an unverifiable claim as settled
fact).

If the fresh reviewer finds real evidence that changes the picture (a
documented feature the original research missed), record its findings
via `dast-bench cache record --vendor-id <id> --criterion-id
<criterion-id> ... --reviewed-by-gap-check` and prepare a proposed
revised score to present alongside the original in Step 6. If it confirms
the original finding (or finds nothing new), record that confirmation the
same way — via `cache record` with `--reviewed-by-gap-check` — so a
future re-run knows this criterion has already survived independent
scrutiny and doesn't need another gap-check pass by default.

This step applies to every vendor scored from now on, not just a one-time
pass — any criterion landing at `≤2.5` gets this independent second look
before its score is considered final.

## Step 6: Present the complete proposed scoring for review

Present every criterion's proposed score, evidence, and brief rationale
for this vendor together, not one at a time — including any gap-check
revisions from Step 5, clearly marked as such (e.g. "revised after
independent gap-check: X"). Do not call any CLI command yet. Let the
evaluator adjust anything before you persist.

## Step 7: Persist the scores

Once the evaluator confirms, for each criterion:

```
dast-bench candidate record-score --vendor-id <id> --criterion-id <id> --score <score> --evidence <evidence> --confidence paper
```

`--confidence` is always `paper` at this phase.

If any command prints an `error: ...` message (e.g. an unknown criterion
or vendor id, which shouldn't occur given Steps 1–2 but could if the
taxonomy or candidate list changed mid-session), relay it verbatim to the
evaluator and ask how to proceed rather than retrying blindly.

## Step 8: Check whether every candidate is now fully scored

Run `dast-bench status`.

**If gaps remain** (this vendor or others still have missing scores):
confirm this vendor's scoring is complete, and stop here. The evaluator
can invoke you again for the next vendor.

**If there are no gaps at all** — every candidate fully scored against
every criterion — proceed to Step 9. This is the automatic transition
into finalist recommendation; the evaluator does not need to ask for it
separately.

## Step 9: Recommend finalists

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

## Step 10: Summarize

Summarize for the evaluator what was scored this round — including how
many criteria went through gap-check and whether any scores changed as a
result — and, if Step 9 ran, what finalist/rejected decisions were made,
so they have a clear record of what this invocation changed.
