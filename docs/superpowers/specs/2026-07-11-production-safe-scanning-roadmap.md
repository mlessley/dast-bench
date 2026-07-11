# Production-Safe Scanning — Roadmap (Deferred, Not Yet Designed)

**Status: parking-lot notes, not a validated design.** This captures a
discussion that came up while brainstorming
`2026-07-11-dast-benchmark-ci-pipeline-design.md`, deliberately deferred so
that design could stay focused on the ephemeral-benchmark-target scenario
(OWASP Juice Shop / VAmPI). Revisit this as its own brainstorm before
building anything against it.

## Why this is a separate scenario, not an extension of the benchmark pipeline

The benchmark-target CI pipeline scores tools against **known ground
truth** on a **throwaway container** that gets destroyed after each run,
and it deliberately runs a full active scan since there's nothing real to
break. Production-safe scanning is close to the opposite on every axis:

| | Benchmark target | Production-safe scanning |
|---|---|---|
| Target lifetime | Ephemeral, destroyed per run | Long-lived, real system |
| Ground truth | Known, planted vulnerabilities | Unknown — nothing to compare against |
| Scan posture | Full active scan (safe, disposable) | Light-touch / passive-first (real operational risk if aggressive) |
| Trigger model | On-demand (`workflow_dispatch`) | Post-deploy + scheduled/periodic |
| Success metric | Detection rate / false-positive rate | Non-disruption + drift/exposure detection |
| Authorization | None needed (your own throwaway container) | Explicit authorization from the asset owner required |

## What "production" means here (from the brainstorm)

Three framings were discussed, not yet decided between:
1. A staging/pre-prod clone the evaluator owns and is authorized to
   actively scan (safe since it's not customer-facing).
2. An actual production system, requiring explicit authorization/change
   window, with the most conservative scan policy (passive-first,
   rate-limited, scheduled).
3. A more realistic reference app (bigger/more complex than Juice Shop or
   VAmPI) that is still a throwaway target, not literally "prod" — tests
   tool behavior at realistic scale/auth complexity without real
   operational risk.

The user's own framing when this was raised: the real value being chased
is understanding **how to drive a DAST tool with guardrails / light touch
/ non-destructive** behavior, since that's how it would actually be pointed
at a real system.

## Trigger model — the open question that prompted this doc

Raised directly: if no code has been deployed, is there still value in
re-running a scan against an unchanged production system? Yes — this is
one of DAST's core differentiators from SAST, since DAST exercises the
*running* system rather than reacting to a code diff. Concretely, a
periodic re-scan (with no code change) can still catch:

- A newly disclosed CVE in a third-party JS dependency still being served.
- Config or infrastructure drift introduced outside the code pipeline
  (a debug endpoint left exposed, a CORS/cert misconfiguration, a newly
  reachable route from an infra change).
- Any other exposure that "looks like a vulnerability" but wasn't
  introduced by a code change at all.

This implies (not yet decided) **two distinct triggers**, not one:
- **Post-deploy, scoped:** run after a release, ideally scoped to the
  affected surface area if that's feasible to determine — open question:
  how would "affected areas" actually be scoped in practice (route diff?
  deployment manifest diff?).
- **Scheduled/periodic:** run on a cadence regardless of deployment
  activity, specifically to catch drift — probably the context where the
  passive-first/guardrailed posture matters most, since there's no
  release under test, just ambient monitoring.

## Scoring implications (not yet designed)

Because there's no known ground truth against a real production target,
the scoring dimension for this scenario is different in kind from the
benchmark tier's detection-rate/false-positive-rate model. Likely
candidates, not yet decided:
- Did the scan complete without causing any operational incident
  (rate-limit trips, alerting/on-call pages, service degradation)?
- Did it surface anything a human reviewer independently confirms as a
  real, previously-unknown exposure (drift or new CVE)?
- Resource/instrumentation overhead observed during the scan.

## Explicitly not decided yet

- Whether this uses the same CI-pipeline mechanism (GitHub Actions,
  service containers) as the benchmark tier, or a fundamentally different
  invocation path given the different trigger model (scheduled/post-deploy
  vs. on-demand dispatch) and the higher stakes of misconfiguring it.
- What "safe scan policy" concretely means per tool (passive-only? a
  specific active-scan-policy allowlist? rate limits?).
- Whether this is even in scope for the evaluator's Phase 1 hands-on
  testing, or a Phase 2+ concern once a tool has already been selected and
  the question shifts from "which tool" to "how do we run this tool
  safely in our real environment."

## Next step

Brainstorm this as its own design, using
`2026-07-11-dast-benchmark-ci-pipeline-design.md` as a reference for how
the ephemeral-target pipeline works, once picked back up. Per user
instruction, this should be proactively resurfaced in later sessions
rather than left to be rediscovered.
