# dast-onboard-tool Skill Design

## Purpose & Context

`dast-onboard-tool` is a sixth skill, not part of the original five-skill
dast-bench workflow: it wires one new DAST tool into
`.github/workflows/dast-benchmark.yml` so `dast-scan` can hands-on test it
against a finalist vendor. It exists because real DAST tools span a genuine
spectrum of CI/CD integration models — not a binary "automatable or not" —
and trying to force every tool through the same automation path risks
dast-bench becoming an integration platform in its own right rather than
staying focused on its actual value: a rigorous, evidence-backed evaluation
methodology.

That spectrum, established during design discussion:

| Tier | Example | How it runs | Secrets? |
|---|---|---|---|
| 1 — fully local | ZAP, Dastardly | Docker container in the job, no external calls | None |
| 2 — CLI-triggered, cloud-backed | StackHawk | A CLI/config step in the job calls the vendor's cloud and waits for a result within the same job | Yes — an API key |
| 3 — platform-orchestrated | GitLab DAST, Invicti, Veracode, Checkmarx, Endor Labs, Fortify WebInspect (in its heavier deployment modes) | Scan scheduling/policy engine lives on vendor infrastructure; onboarding (repo connections, policy config) happens outside any single CI step | Deep account/platform setup, not just a key |

Which tier a given tool falls into — and its concrete integration details
(docker image, CLI invocation, whether a secret is needed) — is a technical
fact established during `dast-discovery`/`dast-shortlist` research, not
something this skill re-derives. This skill only reads what's already on
the vendor's record and asks the evaluator directly if it's genuinely
missing.

A related question surfaced during design — whether "incumbency" (a vendor
already licensed/deployed in-house, existing staff familiarity) should be a
weighted scoring factor — was resolved as **out of scope for the scored
taxonomy entirely**: `dast-criteria`'s rubric-scored, evidence-cited model
is for objective technical facts; incumbency is a subjective business
judgment. It belongs in `Observation`s (freeform, tagged, e.g.
`incumbency`/`business-context`), surfaced through `dast-report`'s
narrative for executives/finance to weigh themselves — not blended into
the technical weighted score. This applies to `dast-criteria`/`dast-report`,
not this skill directly, but is recorded here since it shaped this skill's
scope (deployment tier stays a technical fact captured upstream, same
treatment).

## Goals

- Wire one new DAST tool into the CI workflow at the tier already
  established by earlier research — read from the vendor's record, not
  reassessed here.
- **Tier 1** (fully local, no secrets): full automation — new workflow
  branch, new normalize script, tests, and the final `candidate
  set-ci-tool` hookup.
- **Tier 2** (CLI + cloud, needs an API key): same automation as Tier 1,
  except the skill only ever references `${{ secrets.<NAME> }}` in the
  workflow — it tells the evaluator to add the actual secret via GitHub
  themselves, never handling credential material.
- **Tier 3** (platform-orchestrated, heavy onboarding): no workflow edit at
  all — just the normalizer and a manual runbook ending in the evaluator
  running `scan ingest-scan-result` themselves.
- One-time retrofit: the first time a second tool is onboarded, guard the
  previously-unconditional ZAP scan step with `if: inputs.tool == 'zap'` in
  both jobs, so every tool (ZAP included) follows the same uniform
  per-tool-step pattern going forward. Subsequent onboardings check this is
  already done and skip re-applying it.
- Every normalizer, any tier, reconciles the new tool's native finding
  identifiers against the ground-truth vocabulary already seeded in
  `data/benchmarks.yaml` (the ZAP plugin IDs and `vampi-*` slugs from
  `dast-scan`'s work) — sourced from the new tool's own documentation of
  what it detects, the same curation discipline used for ZAP's ground
  truth.
- Enforce this project's TDD discipline on whatever code this skill
  produces: tests written first, confirmed failing, then passing, before
  any commit — structural workflow tests (Tier 1/2, mirroring
  `test_dast_benchmark_workflow.py`) and normalize-script tests (all tiers,
  mirroring `test_normalize_zap.py`).
- One tool per invocation.

## Non-Goals / Out of Scope

- Determining which tier a tool falls into, or researching its concrete
  integration details from scratch — `dast-discovery`/`dast-shortlist`'s
  job. This skill reads what's already captured; it doesn't investigate a
  tool's market positioning or technical fit.
- Any new formal criterion for deployment tier/control-locality, or for
  incumbency — both were discussed and explicitly deferred: deployment
  tier as a possible future `dast-criteria` addition (separate task, not
  solved here), incumbency as an `Observation`, never a scored criterion.
- Handling actual credential values for Tier 2 tools — the skill only ever
  writes a `${{ secrets.<NAME> }}` reference; provisioning the real secret
  in GitHub is the evaluator's action, outside this skill's write scope.
- Running or verifying the newly-onboarded tool end-to-end — that's
  `dast-scan`'s job once `ci_tool_id` is set (Tier 1/2) or the manual
  runbook is followed (Tier 3).
- A generic, tool-agnostic "pipeline observer" abstraction — same reasoning
  as `dast-scan`'s design: this stays scoped to
  `.github/workflows/dast-benchmark.yml` specifically, not a reusable
  cross-project framework (that's a separate project, pipeline-lens, not
  dast-bench's concern).

## Architecture

`dast-onboard-tool` is a Claude Code skill: a prompt file at
`.claude/skills/dast-onboard-tool/SKILL.md`, invoked as
`/dast-onboard-tool`. It is the first skill in this project whose
invocations produce real code rather than YAML-data mutations —
`.github/workflows/dast-benchmark.yml` edits (Tier 1/2), a new
`.github/scripts/normalize/<tool>.py` (all tiers), and corresponding tests.

**The one-time ZAP retrofit.** Both jobs' "Run ZAP full scan" step is
currently unconditional — `tool`'s only current value is `zap`, so nothing
gates it. Before adding a second tool, this skill must first add
`if: inputs.tool == 'zap'` to that step in both jobs, exactly as it will
guard the new tool's step. This makes ZAP structurally identical to every
tool onboarded after it — not a special case preserved going forward, a
one-time historical cleanup. Example (both jobs get this treatment):

```yaml
- name: Run ZAP full scan
  if: inputs.tool == 'zap'          # newly added
  timeout-minutes: 20
  run: |
    docker run --network host -v "$(pwd)":/zap/wrk/:rw \
      zaproxy/zap-stable:2.17.0 zap-full-scan.py \
      -t http://localhost:3000 -J raw-report.json || true

- name: Run <newtool> scan            # newly added step
  if: inputs.tool == '<newtool>'
  timeout-minutes: 20
  run: |
    <newtool's own invocation>
```

**Per tier:**
- **Tier 1/2:** add the new value to the workflow's `tool` choice list; add
  the new guarded step in both jobs; extend the normalize/upload steps'
  `if: inputs.tool == '...'` conditionals to include the new tool. Tier 2's
  new step references `${{ secrets.<NAME> }}` for its API key; the skill
  never generates, guesses, or stores the actual secret value — it
  instructs the evaluator to add it via GitHub themselves. Finish with the
  already-existing `dast-bench candidate set-ci-tool --id <vendor-id>
  --tool <newtool>` (no new CLI command needed — this was built during
  `dast-scan`'s plan specifically for this handoff).
- **Tier 3:** no workflow edit. Write the normalizer and a manual runbook;
  the evaluator runs the tool themselves, gets its native report, runs the
  normalizer, and calls `scan ingest-scan-result` directly — which needs no
  `ci_tool_id` at all, so Tier 3 vendors correctly never get one set
  (there's no matching `tool=` value in the workflow to point at).

**Every normalizer** (regardless of tier) follows `zap.py`'s existing shape
(`main(argv)`, raw report path in, generic findings JSON list out:
`{vuln_id, severity, description}`), with vuln IDs mapped to the existing
ground-truth vocabulary wherever the new tool detects an equivalent
vulnerability class — curated from that tool's own documentation, not
guessed.

**No new CLI commands or model changes.** `candidate set-ci-tool` (built
during `dast-scan`) already covers the one data-linking step this skill
needs.

## Data Flow

1. Skill identifies which vendor/tool to onboard — the evaluator names one
   directly, or the skill checks `dast-bench candidate list` for finalists
   still missing `ci_tool_id`.
2. Reads that vendor's record directly for integration details already
   captured upstream (observations/evidence noting deployment tier, docker
   image or CLI command, whether a secret is needed). If genuinely
   missing, asks the evaluator directly for tier + concrete integration
   details rather than researching it itself.
3. **Tier 1/2:** checks whether the existing tool step(s) are already
   guarded by `if: inputs.tool == '...'` (skips the one-time retrofit if a
   prior onboarding already applied it); adds the new value to the `tool`
   choice list; adds a new guarded step in both jobs; extends the
   normalize/upload conditionals.
   **Tier 3:** no workflow edit.
4. Writes the normalizer (`.github/scripts/normalize/<tool>.py`, all
   tiers) — native format to generic findings JSON, vuln IDs reconciled
   against the existing ground-truth vocabulary, sourced from the new
   tool's own documentation.
5. Writes/extends tests: structural workflow tests (Tier 1/2 only,
   mirroring `test_dast_benchmark_workflow.py`'s pattern of parsing the
   YAML and asserting job/step structure) and normalize-script tests (all
   tiers, mirroring `test_normalize_zap.py`'s subprocess-based pattern).
   Runs them, confirms passing, before committing anything.
6. **Tier 1/2:** commits the workflow + normalizer + tests, then
   `dast-bench candidate set-ci-tool --id <id> --tool <newtool>`.
   **Tier 3:** commits the normalizer + tests only, then presents a manual
   runbook to the evaluator; `ci_tool_id` is never set for this vendor.
7. Skill summarizes what was onboarded; for Tier 1/2, tells the evaluator
   `dast-scan` can now run this vendor.

## Error Handling

- If integration details are missing from the vendor's record and the
  evaluator can't supply them either, the skill stops and explains this
  vendor isn't ready to onboard yet — suggesting that information be
  gathered during `dast-discovery`/`dast-shortlist` first, rather than
  researching it itself.
- If the new tool's native report format can't be determined confidently
  enough to write a correct normalizer, the skill stops and asks, rather
  than guessing a parser and silently producing wrong detection counts.
- Standard TDD: tests must pass before any commit; a failing test blocks
  the commit step, same as every other code-producing task in this
  project.

## Testing

This plan produces one skill file — no changes to the existing test suite
are needed to build it. But because this skill's own future invocations
produce real code (unlike every other skill in this project), its content
must explicitly instruct TDD for whatever it writes each time it runs, per
the Goals/Data Flow above. The skill file itself is not unit-tested —
reviewed by the evaluator reading it once written, consistent with every
prior skill.
