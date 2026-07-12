# dast-scan Skill Design

## Purpose & Context

`dast-scan` is Phase 4 of the dast-bench evaluation workflow: for each
**finalist** vendor (decided by `dast-shortlist`), it hands-on tests that
vendor's already-CI-wired tool against the two ephemeral benchmark targets
(OWASP Juice Shop, VAmPI), refines the two objectively-computable criteria
scores (`detection-accuracy`, `false-positive-rate`) with hands-on evidence,
and — once both targets are scanned — drives that finalist to `evaluated`
status. `dast-criteria`, `dast-discovery`, and `dast-shortlist` (all built
2026-07-12) are the precedent this design follows: Claude Code skills (prompt
files, no code of their own) that converse with the evaluator before
persisting anything, mutate data only through the existing `dast-bench` CLI,
and add the smallest CLI/model change needed to close a real gap.

Two real gaps exist today that block this phase:
- `data/benchmarks.yaml` doesn't exist, and no CLI command creates a
  `Benchmark` (ground-truth vulnerability list) — `storage.save_benchmarks`
  exists but nothing calls it outside tests.
- Nothing records which CI workflow `tool` value corresponds to which
  vendor's product — the `dast-benchmark.yml` workflow's `tool` input
  currently supports only `zap`.

## Goals

- For a given finalist, run its already-CI-wired tool against whichever of
  Juice Shop/VAmPI it doesn't yet have a `HandsOnResult` for, in one
  invocation covering both targets.
- Seed Juice Shop's and VAmPI's ground-truth vulnerability lists (a curated,
  sourced baseline — same pattern as `dast-criteria`'s fixed 12-criteria
  baseline) the first time `benchmark list` is empty.
- Persist the CI-tool-to-vendor mapping (`ci_tool_id`) so the evaluator
  doesn't re-answer "which tool is this vendor's product" on every
  invocation.
- Orchestrate the existing `dast-benchmark.yml` workflow end-to-end via the
  `gh` CLI: dispatch, wait for completion, download artifacts, normalize,
  ingest — no manual steps for the evaluator.
- Once a finalist has `HandsOnResult`s for both targets, propose refined
  `detection-accuracy`/`false-positive-rate` scores (aggregated across both
  runs, confidence `hands-on`) for evaluator review before persisting, then
  offer the `evaluated` status transition.
- Capture any qualitative hands-on findings (CI/CD integration friction, a
  manual tweak that was needed, any other caveat) as tagged
  `candidate log-observation` entries — a "subjective" bucket, distinct from
  formal scores, reusing existing infrastructure rather than inventing a new
  one.

## Non-Goals / Out of Scope

- Deciding finalists — `dast-shortlist`'s job.
- Refining any criterion other than `detection-accuracy`/`false-positive-rate`
  with hands-on evidence. Other impressions (e.g. CI/CD integration
  experience) are captured as observations, not formal scores, in this
  skill.
- Wiring a **new** DAST tool into `.github/workflows/dast-benchmark.yml` (new
  workflow step, docker/CLI invocation, auth/licensing handling for
  commercial products, a new normalize script). This is a genuinely
  different shape of task — a code change that happens once per new tool,
  not a YAML-data mutation that happens once per scan — and is deferred to a
  new, separate skill: **`dast-onboard-tool`** (queued as the next
  brainstorm after this plan ships). `dast-scan` only ever runs tools
  already wired in; if a finalist's tool isn't wired yet, it says so and
  points at `dast-onboard-tool`.
- Building a generic, reusable "pipeline observer" abstraction. The
  dispatch → wait → download-artifacts → normalize → ingest pattern here is
  scoped narrowly to the one `dast-benchmark.yml` workflow. A broader,
  cross-project version of this pattern is the concern of a separate project
  (pipeline-lens) the evaluator is also building — not this plan's job to
  generalize toward.

## Architecture

`dast-scan` is a Claude Code skill: a prompt file at
`.claude/skills/dast-scan/SKILL.md`, invoked as `/dast-scan`. It contains no
code — it is instructions for an LLM agent that identifies one finalist to
scan, ensures prerequisite data exists (CI tool mapping, benchmark ground
truth), orchestrates the existing CI workflow via `gh`, ingests results
through the existing `scan ingest-scan-result` command, and — once both
targets are covered — proposes score refinements and an `evaluated` status
transition for evaluator confirmation before persisting anything.

**Small CLI/model additions this plan needs** (all closing gaps identified
above, none discretionary):

1. **`Vendor.ci_tool_id: str | None = None`** on the `Vendor` model — which
   workflow `tool` value this vendor's product corresponds to. New CLI
   command `candidate set-ci-tool --id --tool`, mirroring `candidate
   set-status`'s existing shape exactly.
2. **`benchmark add --id --name --target-type`** — creates a `Benchmark`
   shell (no known vulnerabilities yet). New `benchmark_app` Typer sub-app,
   registered the same way `criteria_app`/`candidate_app`/`scan_app` are.
3. **`benchmark add-vulnerability --benchmark-id --vuln-id --name
   --severity`** — appends one `BenchmarkVulnerability` to an existing
   benchmark's `known_vulnerabilities` list, mirroring `criteria
   add-criterion`'s one-thing-per-call pattern.
4. **`benchmark list`** — prints existing benchmarks (id, name, target type,
   known-vulnerability count), used for revision detection (has this
   already been seeded?) the same way `candidate list`/`criteria list` are
   used by the sibling skills.

All four are small, mechanical additions to `core/models.py`/`core/cli.py`
following patterns already established by three prior plans — no new
architecture, no new persistence mechanism.

**CI orchestration** uses the `gh` CLI directly (already authenticated in
this environment from the earlier live-verification session) — no new
tooling:

```
gh workflow run dast-benchmark.yml -f tool=<ci_tool_id> -f target=<juice-shop|vampi>
gh run list --workflow=dast-benchmark.yml --limit 1 --json databaseId,status
gh run watch <run-id>
gh run download <run-id>
```

`gh run watch` blocks until the run completes, which can take up to the
workflow's 20-minute timeout — longer than a single foreground tool call
should occupy. The skill runs this step in the background and continues once
notified, rather than blocking synchronously. After download: normalize with
the existing `.github/scripts/normalize/zap.py`, then call the existing
`scan ingest-scan-result`.

**Benchmark ground truth** for Juice Shop and VAmPI is a curated, sourced
baseline — drawn from each project's own documented vulnerable-by-design
challenges/endpoints (Juice Shop's official challenge list, VAmPI's README) —
baked into the skill file the same way `dast-criteria`'s 12-criteria baseline
was, rather than researched live on every invocation (unlike `dast-discovery`,
these targets' known vulnerabilities are stable, not a moving market). The
exact curated list is authored during plan-writing, not this design doc.

## Data Flow

1. Skill identifies which finalist to scan — the evaluator can name one
   directly, or the skill suggests the first `finalist`-status vendor still
   missing a `HandsOnResult` for either benchmark target.
2. Skill checks that vendor's `ci_tool_id`. If unset, it tells the evaluator
   this vendor isn't wired into the CI workflow yet and points at
   `dast-onboard-tool` — stops here for this vendor, no further action.
3. Skill runs `benchmark list`. If empty, it seeds Juice Shop's and VAmPI's
   ground-truth vulnerability lists via `benchmark add` +
   `benchmark add-vulnerability` (the baked-in curated baseline).
4. Skill reads the vendor's record directly (`data/candidates/<id>.yaml`) to
   see which targets it already has `HandsOnResult`s for (revision
   detection, same pattern as `dast-shortlist`'s Step 2) — determines which
   of Juice Shop/VAmPI still need a run this invocation.
5. For each target still needed: dispatch via `gh workflow run`, wait via
   `gh run watch` (backgrounded), download artifacts via `gh run download`,
   normalize, then `scan ingest-scan-result`. If anything qualitative comes
   up along the way (setup friction, a manual tweak needed), the skill logs
   it via `candidate log-observation`, tagged appropriately (e.g.
   `hands-on`, `cicd-friction`) — not as a formal score.
6. Once **both** targets have `HandsOnResult`s for this finalist: skill
   computes aggregate detected/known and false-positive counts across both
   results, proposes refined `detection-accuracy`/`false-positive-rate`
   scores against the taxonomy's rubric (`criteria list`), and presents them
   together — nothing persisted yet — for evaluator review, same
   present-before-persist pattern as `dast-shortlist`'s Step 5.
7. Evaluator confirms: skill persists via `candidate record-score
   --confidence hands-on` for those two criteria, then asks whether to
   transition this finalist to `evaluated`; if yes, `candidate set-status
   --id <id> --status evaluated`.
8. Skill summarizes what was scanned, refined, and/or transitioned this
   round.

## Error Handling

- Any `gh` command failure (dispatch, watch, download) or a workflow run
  that fails/times out — relay the error/failure message verbatim, ask the
  evaluator how to proceed (retry, skip this target, investigate) rather
  than retrying blindly, consistent with the three prior skills.
- Normalize script failure (unparseable ZAP report) or `ingest-scan-result`
  erroring on an unknown benchmark/vendor id (shouldn't occur given Steps
  2-3, but possible if data changed mid-session) — relay the error verbatim
  and ask how to proceed.
- Partial completion: if one target's scan succeeds but the other fails,
  the finalist simply isn't ready for the evaluated-gate yet — the skill
  reports which target still needs a rerun and does not block progress on
  the target that did succeed.

## Testing

The four CLI/model additions (`Vendor.ci_tool_id`, `candidate set-ci-tool`,
`benchmark add`, `benchmark add-vulnerability`, `benchmark list`) get real
TDD, following the same pattern as prior plans' CLI additions. The skill
file itself is not unit-tested — reviewed by the evaluator reading it once
written, consistent with `dast-criteria`/`dast-discovery`/`dast-shortlist`.
