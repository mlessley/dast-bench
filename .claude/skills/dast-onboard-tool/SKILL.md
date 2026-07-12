---
name: dast-onboard-tool
description: Use to wire one new DAST tool into the benchmark CI workflow (or, for platform-orchestrated tools, provide a manual runbook instead) so dast-scan can hands-on test it against a finalist vendor. Re-invocable anytime, one tool per invocation.
---

# dast-onboard-tool

This skill wires a new DAST tool into `.github/workflows/dast-benchmark.yml`
so `dast-scan` can hands-on test it against a finalist vendor's product. It
is the sixth skill, not part of the original five-skill workflow
(`dast-criteria` → `dast-discovery` → `dast-shortlist` → `dast-scan` →
`dast-report`), and the first whose invocations produce real code —
workflow YAML edits, a new normalize script, and tests — rather than
`data/*.yaml` mutations.

It never determines which tier a tool falls into or researches its
integration details from scratch — that's `dast-discovery`'s and
`dast-shortlist`'s job. This skill only reads what's already on the
vendor's record and asks the evaluator directly if that's genuinely
missing.

**One tool per invocation.**

## Step 1: Identify which vendor/tool to onboard

If the evaluator names a specific vendor, use that. Otherwise, run
`dast-bench candidate list` and suggest the first `finalist`-status vendor
still missing `ci_tool_id`.

## Step 2: Get the integration details already captured upstream

Read the vendor's record directly (`data/candidates/<id>.yaml`) for any
observations or evidence noting its deployment tier and concrete
integration details (docker image or CLI invocation, whether an API key or
other secret is needed).

**If found:** use them. Do not re-research the tool's market fit or
technical positioning — that already happened.

**If genuinely missing:** ask the evaluator directly which tier applies —

- **Tier 1** (fully local — a docker image or installable CLI, no
  external calls, no secrets)
- **Tier 2** (a CLI/config step that calls the vendor's cloud and returns
  a result within the same job, needs an API key)
- **Tier 3** (platform-orchestrated — scan scheduling and policy engine
  live on vendor infrastructure; onboarding needs account/platform setup
  outside any single CI step)

— and for Tier 1/2, the concrete invocation details (image name or install
command, CLI flags, output format). If the evaluator can't supply this
either, stop here and say this vendor isn't ready to onboard yet; suggest
gathering it during `dast-discovery`/`dast-shortlist` first.

## Step 3: Check whether the one-time ZAP retrofit is needed

Read `.github/workflows/dast-benchmark.yml`. If the "Run ZAP full scan"
step in either job does **not** already have an `if: inputs.tool == 'zap'`
condition, this is the first tool being onboarded since ZAP — add that
condition to the step in both the `juice-shop` and `vampi` jobs before
proceeding. This makes ZAP structurally identical to every tool onboarded
after it, not a special case. If the condition is already present (a prior
onboarding already did this), skip this step entirely — do not reapply it.

This step only applies to **Tier 1/2** tools. Skip to Step 5 for **Tier
3**.

## Step 4: Wire the new tool into the workflow (Tier 1/2 only)

In `.github/workflows/dast-benchmark.yml`:

1. Add the new tool's value to the `tool` input's `options` list.
2. Add a new step to **both** the `juice-shop` and `vampi` jobs, guarded by
   `if: inputs.tool == '<newtool>'`, that runs the new tool against that
   job's target (`http://localhost:3000` for juice-shop,
   `http://localhost:5000` for vampi) and writes its raw report to a file,
   following the same shape as the existing ZAP step (a `timeout-minutes:
   20` docker/CLI invocation piping output to a report file). For **Tier
   2**, reference the API key as `${{ secrets.<NAME> }}` — never write the
   actual key value; tell the evaluator to add that secret via GitHub
   themselves (Settings → Secrets and variables → Actions) before this
   tool can be dispatched.
3. Extend the existing "Normalize report" and "Upload normalized report"
   steps' `if: inputs.tool == 'zap'` conditions in both jobs to also match
   the new tool (e.g. `if: inputs.tool == 'zap' || inputs.tool ==
   '<newtool>'`), and point the normalize step at the new normalizer script
   for the new tool.
4. Check the existing "Upload raw report" step: it already uses
   `${{ inputs.tool }}` in its artifact name and needs no change — only the
   scan step and the normalize/upload-normalized steps are tool-specific.

## Step 5: Write the normalizer

Create `.github/scripts/normalize/<newtool>.py`, following
`.github/scripts/normalize/zap.py`'s shape exactly: a `main(argv)` entry
point taking a raw report path and an output path, parsing the new tool's
native report format, and writing a JSON array of
`{"vuln_id": ..., "severity": ..., "description": ...}` objects to the
output path.

Research the new tool's own documentation for what vulnerability classes it
detects, and map its native finding identifiers to the existing
ground-truth vocabulary already seeded in `data/benchmarks.yaml` (the ZAP
plugin IDs and `vampi-*` slugs from `dast-scan`) wherever the new tool
detects an equivalent vulnerability class. If the new tool's native report
format can't be determined confidently enough to write a correct parser,
stop and ask the evaluator rather than guessing.

## Step 6: Write tests, TDD

Write the failing tests first, confirm they fail, then make them pass:

- **Normalize script tests** (all tiers): a new
  `tests/test_normalize_<newtool>.py`, mirroring
  `tests/test_normalize_zap.py`'s pattern — invoke the script as a
  subprocess against a small sample raw report, assert the normalized JSON
  output matches expectations (including at least one vuln ID that
  reconciles to the existing ground-truth vocabulary).
- **Structural workflow tests** (Tier 1/2 only): extend
  `tests/test_dast_benchmark_workflow.py` to assert the new tool's value is
  present in the `tool` input's `options`, and that both jobs' new step is
  present and correctly gated.

Run `uv run pytest -v` and confirm everything passes before moving on.

## Step 7: Commit and finish

**Tier 1/2:**
```bash
git add .github/workflows/dast-benchmark.yml .github/scripts/normalize/<newtool>.py tests/test_dast_benchmark_workflow.py tests/test_normalize_<newtool>.py
git commit -m "Onboard <newtool> into the benchmark CI workflow"
```
Then:
```
dast-bench candidate set-ci-tool --id <vendor-id> --tool <newtool>
```
If this prints an `error: ...` message, relay it verbatim and ask the
evaluator how to proceed rather than retrying blindly.

**Tier 3:**
```bash
git add .github/scripts/normalize/<newtool>.py tests/test_normalize_<newtool>.py
git commit -m "Add <newtool> normalizer for manual hands-on scans"
```
Do not set `ci_tool_id` — there is no matching `tool=` value in the
workflow to point at. Instead, present the evaluator a short runbook: run
`<newtool>` yourself against the benchmark target, get its native report,
run `python .github/scripts/normalize/<newtool>.py <raw-report>
<normalized.json>`, then call `dast-bench scan ingest-scan-result
--vendor-id <id> --benchmark-id <target> --file <normalized.json>
--test-id <test-id>` directly.

## Step 8: Summarize

Tell the evaluator what was onboarded, at which tier, and — for Tier 1/2 —
that `dast-scan` can now run this vendor; for Tier 3, that they can follow
the runbook whenever they're ready to hands-on test it.
