# DAST Benchmark CI Pipeline (Hands-On Phase Infrastructure)

## Purpose & Context

The Phase 1 design (`2026-07-10-dast-eval-phase1-design.md`) names an OWASP ZAP
reference adapter for the hands-on phase, driven by the (not-yet-built)
`dast-handson` Claude Code skill directly via Bash/CLI/API. This design
revisits how that driving happens for the **benchmark-target** test
scenario specifically: rather than an LLM improvising a scan invocation in
an interactive session, the tool runs inside a real GitHub Actions CI
pipeline — closer to how these tools are actually used in a real SDLC, and
producing durable, inspectable artifacts (workflow logs, uploaded reports)
that make the eventual scorecard more defensible.

This also directly exercises one of the evaluation criteria named in the
Phase 1 spec itself: CI/CD-native fit is something worth observing, not
just asking about on paper.

**Scope note:** this design covers only the "ephemeral, deliberately
vulnerable benchmark target" scenario (OWASP Juice Shop, VAmPI) — spun up
fresh per run, scored against known ground truth via detection rate. A
second scenario, scanning a production or production-like target for drift
and misconfiguration rather than known vulnerabilities, was discussed and
deliberately deferred; see `2026-07-11-production-safe-scanning-roadmap.md`.

Building the `dast-handson` skill itself (the orchestrator that will
eventually call the pieces this design produces) is explicitly out of
scope — this design produces the CI-side infrastructure that skill will
call into once it exists.

## Goals

- Run each hands-on finalist DAST tool against a fresh, ephemeral,
  deliberately-vulnerable benchmark target inside a real GitHub Actions
  pipeline, rather than an ad hoc interactive session.
- Produce a permanent, inspectable audit trail: every run's raw tool
  output is preserved as a build artifact, regardless of whether
  normalization succeeds.
- Feed normalized findings into the existing `dast-eval handson
  ingest-scan-result` CLI command (already built) without requiring any
  changes to the core library.
- Support adding new tools incrementally: a tool can be tried before a
  permanent normalization script exists for it (via a documented fallback
  path), and "graduate" to a checked-in, unit-tested script once proven
  out.

## Non-Goals / Out of Scope

- The `dast-handson` skill itself (trigger + poll + download + ingest
  orchestration) — deferred, built after this infrastructure exists.
- Production or production-like scanning (drift/misconfiguration
  detection, passive-first/guardrailed posture, post-deploy and scheduled
  triggers) — deferred; see the companion roadmap doc.
- A dual-purpose "reference pipeline your org could adopt for real
  production scanning" — this is an evaluation harness only, not intended
  to be production-hardened or lifted wholesale into a real deployment
  pipeline.
- Any change to the `core` package or its CLI — this design is purely
  additive CI infrastructure that produces inputs for the existing
  `ingest-scan-result` command.

## Architecture

One `workflow_dispatch`-triggered GitHub Actions workflow in this repo:
`.github/workflows/dast-benchmark.yml`.

**Inputs:**
- `tool` (choice: `zap`, extensible as more tools are added)
- `target` (choice: `juice-shop`, `vampi`)

**Job structure:** GitHub Actions cannot conditionally attach a service
container to a single job based on a workflow input, so the workflow
defines **one job per target**, each gated by `if: inputs.target ==
'<target>'` and declaring that target's official Docker image as a
`services:` container. Only the job matching the dispatched `target` input
actually runs; the other is skipped. This keeps the "spin up a fresh
target" requirement satisfied natively by GitHub Actions' service-container
lifecycle (started before the job's steps run, torn down automatically
when the job ends) — no separate deploy/teardown step needed.

**Scan depth:** because the benchmark target is an ephemeral, throwaway
container destroyed at the end of the job, the tool runs a **full active
scan** — the goal here is maximizing detection rate against a target with
known, planted vulnerabilities, not minimizing footprint. This is the
opposite posture from the deferred production-safe scenario, which
explicitly requires a light-touch/passive-first approach against a target
that must not be disrupted.

## Components

1. **`.github/workflows/dast-benchmark.yml`** — the parameterized workflow:
   per-target jobs with service containers, a scan step, an unconditional
   raw-report upload, and a conditional normalization step.
2. **`.github/scripts/normalize/<tool>.py`** — per-tool normalization
   scripts, checked into the repo and versioned like any other code.
   Starts with just `zap.py`. A new tool gets a script written (and
   unit-tested) once its output format has been validated against real
   output — see the Data Flow section for the fallback path used before
   that happens.
3. **The existing `core` CLI's `ingest-scan-result` command** — unchanged.
   This design produces inputs for it; it does not modify it.
4. **The companion roadmap doc** (`2026-07-11-production-safe-scanning-roadmap.md`)
   — not implemented as part of this design, but captures the discussion
   so it isn't lost.

## Data Flow

1. **Trigger:** `gh workflow run dast-benchmark.yml -f tool=zap -f
   target=juice-shop`. This will eventually be issued by the
   `dast-handson` skill, but works standalone via the `gh` CLI today,
   before that skill exists.
2. GitHub Actions runs the matching target's job, brings up the service
   container, and waits for it to report healthy.
3. The tool (ZAP, full active scan) runs against the service container
   over `localhost`, writing its native report (JSON) to the job
   workspace.
4. **The raw report is uploaded as a build artifact unconditionally, every
   run** — the permanent audit trail, independent of whether normalization
   succeeds or even runs.
5. The workflow checks whether a normalization script exists for the
   dispatched `tool` input (`.github/scripts/normalize/<tool>.py`):
   - **If it exists** (true for `zap` from the start): the script runs,
     converting the tool's native report into the generic shape
     `[{vuln_id, severity, description}, ...]`, and that normalized JSON is
     uploaded as a second build artifact.
   - **If it does not exist** (a brand-new tool being tried before a
     script has been written): no normalization step runs; only the raw
     report artifact is produced.
6. The run completes. Whoever triggered it (a human, or eventually the
   `dast-handson` skill) runs `gh run download <run-id>` to pull the
   artifact(s) locally.
7. **If the normalized artifact is present**, it's fed directly to:
   ```
   dast-eval handson ingest-scan-result \
     --vendor-id <id> --benchmark-id <juice-shop|vampi> \
     --file <normalized.json> --test-id <run-id>
   ```
   **If not**, the raw artifact is read and a normalized JSON is produced
   by hand or by an LLM (the fallback path for trying a tool before its
   script exists), then fed to the same command. Once that conversion has
   been validated a few times, it should be turned into a permanent,
   checked-in, unit-tested script under `.github/scripts/normalize/` —
   "graduating" the tool out of the fallback path.

## Error Handling

- **Service container never becomes healthy** (bad image, target app
  crash-loops on startup): the job fails outright with a clear GitHub
  Actions failure status. No report and no artifact are produced — a hard
  stop, not a silent empty result that could be misread as "zero
  findings."
- **Normalization script encounters a report shape it doesn't recognize**
  (the tool changed its output format): the script must exit non-zero with
  a clear stderr message rather than emitting an empty or partial JSON.
  This is the single most dangerous silent-failure path in the whole
  design — an empty normalized JSON is indistinguishable from "the tool
  found nothing," which would silently corrupt the scorecard with a false
  negative. The workflow step running the normalization script must not
  use `continue-on-error: true`; a broken normalizer should fail the run
  visibly.
- **Malformed or missing normalized JSON reaches `ingest-scan-result`
  anyway** (e.g. a hand-written fallback conversion is wrong): already
  handled by existing, tested behavior — `ingest-scan-result` rejects
  malformed input with a clean `error:` message and a non-zero exit
  instead of a raw traceback (hardened during the core library's final
  whole-branch review). No new work required here.

## Testing

- The workflow YAML itself is not unit-testable in the traditional sense.
  Its acceptance test is a real dispatch against both the `juice-shop` and
  `vampi` targets, confirming: the correct job runs, the service container
  becomes healthy, the scan completes, and both the raw and (for `zap`)
  normalized artifacts are produced correctly.
- **The ZAP normalization script gets real unit tests**, same TDD
  discipline as the core library: a checked-in sample ZAP JSON report
  fixture, an assertion that the script produces the exact expected
  `[{vuln_id, severity, description}]` shape, and a dedicated
  fixture/test for the "unrecognized report shape → non-zero exit, no
  silent empty output" error path — the one failure mode from the Error
  Handling section that must never regress silently.
- No changes are required to the existing `core` package's test suite (45
  passing as of this writing) — this design only adds CI-side files and one
  new, independently-tested script.
