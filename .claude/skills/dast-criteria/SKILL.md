---
name: dast-criteria
description: Use to establish or revise the DAST evaluation criteria taxonomy (categories, criteria, weights, rubrics) that vendors will be scored against. Re-invocable anytime — first run scaffolds from an industry-standard baseline, later runs revise what's already there.
---

# dast-criteria

This skill builds and revises the **criteria taxonomy** for the DAST tool
evaluation — the list of criteria vendors will be scored against later (by
the `dast-shortlist` and `dast-scan` skills). It is not the scorecard
itself, and it never touches any vendor's scores.

Never edit `data/criteria.yaml` directly. Every change happens through
`dast-bench criteria` CLI commands: `add-criterion`, `update-criterion`,
`remove-criterion`, `set-weight`, `list`.

## Step 1: Check current state

Run `dast-bench criteria list`.

## Step 2: Present taxonomy state

**If the list is empty (first run):** present the baseline taxonomy below
to the evaluator, grouped by category, with each criterion's weight and
category subtotals shown. Ask what they want to change before persisting
anything — add, remove, reweight, or edit wording. Treat the baseline as a
starting draft, not a final answer.

**If the list is non-empty (a revision):** summarize the current taxonomy
back to the evaluator conversationally (categories, criteria, weights) —
do not just paste the raw CLI output — and ask what should change.

## Step 3: Iterate conversationally

Discuss changes with the evaluator. Do not call any CLI command yet — this
is a conversation, not an execution loop. Keep iterating until the
evaluator confirms they're happy with the full set of changes.

## Step 4: Apply changes

Once agreed, apply every change as an individual CLI call:

- **New criterion:** `dast-bench criteria add-criterion --id <id> --category <category> --name <name> --description <description> --weight <weight> --rubric <rubric>`
- **Edited criterion (any field):** `dast-bench criteria update-criterion --id <id> [--category <category>] [--name <name>] [--description <description>] [--weight <weight>] [--rubric <rubric>]` — only pass flags for fields that actually changed.
- **Weight-only tweak:** `dast-bench criteria set-weight --id <id> --weight <weight>` (a shorthand for the common case; `update-criterion --weight` does the same thing).
- **Removed criterion:** `dast-bench criteria remove-criterion --id <id>` — if this warns about orphaned vendor scores, relay that warning to the evaluator; it is informational, not an error, and does not block anything.

If any command prints an `error: ...` message, relay it verbatim to the
evaluator and ask how to proceed. Do not retry blindly or invent a
workaround.

## Step 5: Confirm final state

Run `dast-bench criteria list` again. If its output includes a
`warning: criteria weights sum to X, expected 100.00` line, the taxonomy is not yet
valid — return to Step 3 and keep adjusting weights with the evaluator
until that warning disappears. Do not consider this phase complete while
it is showing.

Once weights are clean, summarize the final taxonomy back to the
evaluator as confirmation.

## Baseline Taxonomy (first-run default)

A starting draft covering coverage, detection quality, production safety,
developer experience, and reporting — weighted so that Coverage and
Detection Quality (the core "does it actually work" questions) carry the
most weight, while Production Safety and Developer Experience are
first-class, not afterthoughts. Present all of this to the evaluator
before persisting anything.

### Coverage (30)

- **`api-spa-coverage`** — API/SPA Coverage (weight 15)
  Detects vulnerabilities across REST APIs, GraphQL, and JavaScript-rendered
  single-page applications, not just traditional server-rendered pages.
  - *1:* Only scans traditional server-rendered HTML forms; no JS-rendered
    SPA crawling, no OpenAPI/GraphQL-aware scanning.
  - *3:* Crawls JS-rendered SPA content with a headless browser and
    supports REST via OpenAPI import, but GraphQL support is absent or
    minimal.
  - *5:* Full support for JS-rendered SPAs (headless browser crawling),
    REST (OpenAPI/Swagger import), and GraphQL (schema-aware introspection
    and query fuzzing).

- **`shadow-api-discovery`** — Shadow/Zombie API Discovery (weight 10)
  Finds undocumented, deprecated, or forgotten API endpoints beyond what's
  in a provided spec.
  - *1:* Only tests endpoints explicitly provided (via spec file or manual
    crawl); no discovery of undocumented endpoints.
  - *3:* Some heuristic discovery (common path guessing, JS bundle
    analysis for hidden routes) but misses deprecated/versioned endpoints.
  - *5:* Actively discovers undocumented, deprecated, and versioned
    ("zombie") endpoints via traffic analysis, JS bundle parsing, and
    pattern-based enumeration, without needing a provided spec.

- **`auth-session-handling`** — Authentication & Session Handling (weight 5)
  Navigates login flows and holds authenticated session state through a
  scan.
  - *1:* No support for authenticated scanning; every scan is effectively
    unauthenticated.
  - *3:* Supports basic scripted login (form-based or token-based) but
    session handling breaks on complex flows (MFA, SSO, refresh tokens).
  - *5:* Robust support for complex auth flows (SSO, OAuth, MFA bypass
    hooks, token refresh) with reliable session maintenance throughout a
    long scan.

### Detection Quality (25)

- **`detection-accuracy`** — Detection Accuracy (weight 15)
  True-positive rate against known benchmarks.
  - *1:* Detects only a small fraction of known vulnerabilities in
    benchmark targets, well below OWASP Top 10 baseline coverage.
  - *3:* Detects most common vulnerability classes (OWASP Top 10) reliably
    but misses more nuanced/logic-based vulnerabilities.
  - *5:* High detection rate across both common and nuanced vulnerability
    classes on benchmark targets, validated against known ground truth.

- **`false-positive-rate`** — Noise / False-Positive Rate (weight 10)
  How much triage overhead the findings create.
  - *1:* High false-positive rate requiring extensive manual triage to
    find real issues.
  - *3:* Moderate false-positive rate; a noticeable but manageable amount
    of triage needed.
  - *5:* Low false-positive rate; findings are consistently actionable
    with minimal triage overhead.

### Production Safety & Operability (20)

- **`safe-prod-scanning`** — Safe Production Scanning (weight 12)
  Passive/non-destructive scan modes, rate limiting, low instrumentation
  overhead.
  - *1:* No passive-only mode; active scans risk disrupting a live system
    (data mutation, rate-limit trips, alerting).
  - *3:* Offers a passive/safe mode but with limited configurability
    (can't fine-tune rate limits or scan scope).
  - *5:* Robust passive/non-destructive scanning mode with configurable
    rate limiting and scan-policy controls suitable for scanning a real
    production system without disruption.

- **`cicd-native-fit`** — CI/CD-Native Fit (weight 8)
  Drivable headlessly via CLI/API, not just GUI.
  - *1:* GUI-only; no meaningful CLI/API to drive scans headlessly.
  - *3:* CLI/API exists but requires significant scripting/glue code to
    integrate into a pipeline (inconsistent output formats, unclear exit
    codes).
  - *5:* First-class CLI/API designed for CI/CD use — clear exit codes,
    consistent machine-readable output formats, minimal glue code needed.

### Developer Experience (20)

- **`triage-remediation-guidance`** — Triage & Remediation Guidance (weight 8)
  Explains how to fix a finding, not just what's wrong.
  - *1:* Findings list vulnerability names only, with no guidance on how
    to fix them.
  - *3:* Findings include general remediation advice but not tailored to
    the specific instance/tech stack.
  - *5:* Findings include specific, actionable remediation guidance
    tailored to the detected instance and tech stack.

- **`auto-remediation-pr`** — Auto-Remediation / Auto-PR (weight 5)
  - *1:* No auto-remediation capability at all.
  - *3:* Can suggest a fix diff but can't open a PR automatically.
  - *5:* Can automatically open a pull request with a proposed fix for at
    least some finding classes.

- **`setup-onboarding-friction`** — Setup & Onboarding Friction (weight 7)
  Time/complexity to get a first useful scan running.
  - *1:* Significant setup complexity — multiple support tickets/hours
    needed before a first useful scan.
  - *3:* Moderate setup — some configuration required but a first scan is
    achievable within an hour with docs.
  - *5:* Minimal setup — a first useful scan is achievable within minutes
    of install, with sensible defaults.

### Reporting & Extensibility (5)

- **`reporting-exportability`** — Reporting Quality / Exportability (weight 3)
  - *1:* Reports are hard to read/export; no integration with common tools
    (Jira, Slack, etc.).
  - *3:* Clear reports with basic export (PDF/CSV) but no direct
    integrations.
  - *5:* Clear, exportable reports with direct integrations into common
    tools (Jira, Slack, CI dashboards).

- **`extensibility-custom-rules`** — Extensibility / Custom Rules (weight 2)
  - *1:* No way to add custom detection rules or policies.
  - *3:* Some support for custom rules but limited/awkward (e.g. requires
    vendor support to add).
  - *5:* Well-documented, straightforward way to add custom detection
    rules/policies without vendor involvement.
