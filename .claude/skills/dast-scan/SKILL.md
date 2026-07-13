---
name: dast-scan
description: Use to hands-on test a finalist vendor's tool against the ephemeral benchmark targets (Juice Shop, VAmPI) via the CI workflow, or manually against the public Juice Shop demo instance if the vendor isn't CI-wired, refine detection-accuracy/false-positive-rate scores with the results, and — once available — drive that finalist to evaluated status. Re-invocable anytime, one finalist per invocation.
---

# dast-scan

This skill fills in **hands-on evidence** for a finalist vendor — it runs
that vendor's tool against Juice Shop and VAmPI, either automatically (via
the already-built `dast-benchmark.yml` CI workflow, for tools wired in) or
manually (for tools that aren't, and aren't worth wiring in for a single
data point), records the results, and refines the two criteria whose
scores are directly computable from detection results:
`detection-accuracy` and `false-positive-rate`. It never decides finalists
(`dast-shortlist`'s job) and never wires a *new* tool into the CI workflow
for repeated automated use (`dast-onboard-tool`'s job — still the right
choice instead of the manual path if this vendor will be tested
repeatedly). Any other hands-on impression (CI/CD integration friction, a
manual tweak that was needed, any other caveat) belongs in `candidate
log-observation`, tagged, not in a formal score — that criterion-level
judgment stays out of this skill's scope.

Never edit `data/candidates/*.yaml` or `data/benchmarks.yaml` directly.
Every change happens through `dast-bench` CLI commands: `candidate
set-ci-tool`, `candidate record-score`, `candidate set-status`, `candidate
log-observation`, `benchmark add`, `benchmark add-vulnerability`, `scan
ingest-scan-result`. Reading a vendor's current record directly
(`data/candidates/<id>.yaml`) is fine for inspection — only writes must go
through the CLI.

**Score exactly one finalist per invocation.** Cover whichever benchmark
target(s) that finalist doesn't yet have a result for in this one pass —
both Juice Shop and VAmPI for a CI-automated vendor, or Juice Shop only
for a manually-tested one, since VAmPI has no public instance to manually
test against yet.

## Step 1: Identify which finalist to scan

If the evaluator names a specific vendor, use that. Otherwise, run
`dast-bench candidate list` and suggest the first `finalist`-status vendor
that doesn't yet have hands-on results for both Juice Shop and VAmPI (check
via Step 4's direct read).

## Step 2: Check the vendor is wired into the CI workflow

Read the vendor's record directly (`data/candidates/<id>.yaml`) and check
`ci_tool_id`. The CI workflow currently supports `tool=zap` and
`tool=nuclei`.

**If `ci_tool_id` is already set to a value the workflow supports:**
proceed to Step 3.

**If `ci_tool_id` is unset or isn't a value the workflow supports:** ask
the evaluator directly which of two paths they want for this vendor:

- **Full CI automation** — worth it if this vendor's tool will be tested
  repeatedly, is self-hostable/scriptable, and the evaluator wants it
  wired into `.github/workflows/dast-benchmark.yml` for good. That's
  `dast-onboard-tool`'s job, not this skill's — point them there and stop
  here for this invocation; do not attempt to edit the workflow yourself.
- **A single manual data point, right now** — no CI wiring, no normalize
  script, appropriate for a vendor you may only ever hands-on test once.
  Proceed to Step 3, then Step 6 instead of Step 5.

If `ci_tool_id` was already set from a prior invocation but still isn't a
workflow-supported value (e.g. someone answered this before but chose not
to onboard it), ask again rather than assuming last time's answer still
holds.

## Step 3: Ensure benchmark ground truth exists

Run `dast-bench benchmark list`. If it's empty, seed both targets with their
curated, sourced ground-truth vulnerability lists before continuing:

```
dast-bench benchmark add --id juice-shop --name "OWASP Juice Shop" --target-type spa
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 40018 --name "SQL Injection" --severity high
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 40012 --name "Cross-Site Scripting (Reflected)" --severity high
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 40014 --name "Cross-Site Scripting (Persistent)" --severity high
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 10202 --name "Absence of Anti-CSRF Tokens" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 10003 --name "Vulnerable JS Library (Known Vulnerable Component)" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 10038 --name "Content Security Policy Header Not Set" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 10023 --name "Information Disclosure - Debug Error Messages" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 10037 --name "Server Leaks Information via X-Powered-By Header" --severity low
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 40036 --name "JSON Web Token (JWT) Weaknesses" --severity high
dast-bench benchmark add-vulnerability --benchmark-id juice-shop --vuln-id 10062 --name "PII Disclosure" --severity high

dast-bench benchmark add --id vampi --name "VAmPI" --target-type api
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id 40018 --name "SQL Injection" --severity high
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id 40036 --name "JWT Authentication Bypass (weak signing key)" --severity high
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id 10062 --name "Excessive Data Exposure via /users/v1/_debug" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id vampi-bola --name "Broken Object Level Authorization (view other users' book secrets)" --severity high
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id vampi-mass-assignment --name "Mass Assignment via user update endpoint" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id vampi-user-enum --name "User and Password Enumeration via differing error responses" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id vampi-regexdos --name "RegexDOS via crafted input to a vulnerable regex" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id vampi-rate-limiting --name "Lack of Resources and Rate Limiting" --severity medium
dast-bench benchmark add-vulnerability --benchmark-id vampi --vuln-id vampi-unauthorized-password-change --name "Unauthorized Password Change without re-authentication" --severity high
```

Two ID schemes are deliberately mixed here: numeric IDs (`40018`, `10202`,
etc.) are real ZAP plugin IDs — vulnerabilities a generic ZAP scan can
actually detect, matching `.github/scripts/normalize/zap.py`'s output
verbatim (it uses ZAP's own `pluginid` as `vuln_id`). The `vampi-*` slugs are
business-logic flaws (broken object-level authorization, mass assignment,
enumeration, rate limiting) that no generic ZAP rule targets — they are
expected to always show as undetected by ZAP, which honestly reflects a real
limitation of generic scanners rather than a scoring bug. If this list is
already seeded (non-empty `benchmark list`), skip this step entirely — do
not re-seed or duplicate entries.

## Step 4: Check existing hands-on results (revision detection)

Read the vendor's record directly (`data/candidates/<id>.yaml`) to see which
of Juice Shop/VAmPI it already has a `HandsOnResult` for. Only the targets
missing a result get scanned this invocation. If both already have results,
tell the evaluator so and ask whether they want a fresh rerun of either
target before proceeding — do not silently rerun or silently skip. A
manually-tested vendor will never have a VAmPI result — that's expected
(see Step 7), not something to keep asking about.

## Step 5: Run the CI workflow for each target still needed (CI-automated path)

Skip this step entirely if you're on the manual path from Step 2 — go to
Step 6 instead.

For each target (`juice-shop`, `vampi`) missing a result, using this
vendor's `ci_tool_id` as `tool`:

```
gh workflow run dast-benchmark.yml -f tool=<ci_tool_id> -f target=<target>
gh run list --workflow=dast-benchmark.yml --limit 1 --json databaseId --jq '.[0].databaseId'
```

Then wait for it — a full scan can take up to the workflow's 20-minute
timeout, longer than a single foreground tool call should block on, so run
the wait in the background and continue once notified:

```
gh run watch <run-id> --exit-status
```

If this reports a failed run, relay the failure verbatim (e.g. via
`gh run view <run-id> --log-failed`) and ask the evaluator how to proceed —
retry, skip this target, or investigate — rather than retrying blindly. If
one target fails but the other succeeds, continue with the one that
succeeded; this finalist just isn't ready for Step 7 yet.

On success, download the workflow's already-normalized artifact directly —
the workflow itself runs the tool's normalize script and uploads the
result, so there is no need to normalize again locally:

```
gh run download <run-id> --name normalized-<ci_tool_id>-<target> --dir /tmp/dast-scan-<vendor-id>-<target>
```

Then ingest it:

```
dast-bench scan ingest-scan-result --vendor-id <id> --benchmark-id <target> --file /tmp/dast-scan-<vendor-id>-<target>/normalized.json --test-id scan-<run-id>-<target> --description "CI scan run <run-id>"
```

If anything qualitative comes up along the way — setup friction, a manual
tweak that was needed, an unexpected caveat — log it, tagged, rather than
folding it into a formal score:

```
dast-bench candidate log-observation --vendor-id <id> --context "dast-scan: <target>" --note "<what happened>" --tags hands-on
```

## Step 6: Manual hands-on path (no CI wiring)

Only reached if the evaluator chose this at Step 2. Skip this step
entirely for the CI-automated path.

Confirm the evaluator has trial/account access to the vendor's tool. If
not, say so plainly and stop here for this vendor — there's nothing to
test without it.

Tell the evaluator to point the vendor's tool at
`https://demo.owasp-juice.shop` — OWASP's own officially-hosted public
Juice Shop demo instance, maintained explicitly for this kind of
practice/testing, so a cloud-based scanner has something publicly
reachable without needing new infrastructure. VAmPI has no equivalent
public instance, so this path only ever covers Juice Shop — that's
expected, not a gap to fix here (see Step 7).

Once the evaluator has the vendor's own findings report (however the
vendor's tool exports it — dashboard, CSV, JSON, whatever), hand-author
the generic findings JSON yourself: for each finding, decide whether it's
the same real vulnerability as one of the entries already in
`data/benchmarks.yaml`'s `juice-shop` list — if so, use that entry's
existing `vuln_id` (not the vendor's own internal ID for it); if not, give
it a descriptive slug of your own and leave it alone, matching nothing
(correctly). State explicitly to the evaluator if a finding's
classification is uncertain, rather than guessing confidently. Then:

```
dast-bench scan ingest-scan-result --vendor-id <id> --benchmark-id juice-shop --file <hand-authored.json> --test-id manual-<date> --description "Manual hands-on test, no CI wiring"
```

If anything qualitative comes up (setup friction getting the vendor's
scan running, an unexpected caveat), log it the same way Step 5 does:

```
dast-bench candidate log-observation --vendor-id <id> --context "dast-scan: manual" --note "<what happened>" --tags hands-on
```

## Step 7: Propose refined scores once available

**CI-automated path:** once the vendor has `HandsOnResult`s for **both**
Juice Shop and VAmPI, read both results' `outcome` text (e.g. "detected
8/10 known vulnerabilities, 2 false positive(s)"), aggregate the
detected/known counts and false-positive counts across both.

**Manual path:** once the vendor has a Juice-Shop `HandsOnResult` (VAmPI
will never have one for a manually-tested vendor — that's expected, not
something to wait for), use that single result's numbers directly. The
evidence you write for the refined scores must explicitly state that this
is based on Juice Shop only and VAmPI wasn't covered — this caveat is
mandatory, not optional, so a reader of the eventual scorecard understands
the evidence is narrower than a CI-tested vendor's.

Either way: run `dast-bench criteria list` to get the current rubric text
for `detection-accuracy` and `false-positive-rate`. Propose a refined
score for each against that rubric, citing the numbers (and, for the
manual path, the Juice-Shop-only caveat) as evidence. Present both
proposed scores together — nothing persisted yet — for the evaluator to
review and adjust.

If the CI-automated path hasn't finished both targets yet, stop here
instead — confirm what was scanned this round and that the other target
remains outstanding.

## Step 8: Persist confirmed scores and offer the evaluated transition

Once the evaluator confirms:

```
dast-bench candidate record-score --vendor-id <id> --criterion-id detection-accuracy --score <score> --evidence <evidence> --confidence hands-on
dast-bench candidate record-score --vendor-id <id> --criterion-id false-positive-rate --score <score> --evidence <evidence> --confidence hands-on
```

Then ask the evaluator whether to transition this finalist to `evaluated`.
If yes:

```
dast-bench candidate set-status --id <id> --status evaluated
```

If any command prints an `error: ...` message, relay it verbatim and ask how
to proceed rather than retrying blindly.

## Step 9: Summarize

Summarize for the evaluator what was scanned, what scores were refined
(and with what evidence), and whether the vendor was transitioned to
`evaluated`, so they have a clear record of what this invocation changed.
