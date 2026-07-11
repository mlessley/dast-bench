# dast-criteria Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the two small CLI additions (`criteria remove-criterion`, `criteria update-criterion`) needed for real taxonomy revision, then write the `dast-criteria` Claude Code skill file itself, per `docs/superpowers/specs/2026-07-11-dast-criteria-skill-design.md`.

**Architecture:** Task 1 extends the existing `criteria_app` Typer sub-app in `core/cli.py` with two new commands, TDD-tested exactly like the existing `add-criterion`/`set-weight` commands. Task 2 writes `.claude/skills/dast-criteria/SKILL.md` — a complete, self-contained prompt file (no code) that an LLM agent follows to scaffold/revise the taxonomy conversationally, shelling out to the `dast-bench criteria` CLI for every mutation.

**Tech Stack:** Python 3.11+ (via `uv`), Typer, pytest — no new dependencies.

## Global Constraints

- This project uses `uv` for all Python package management — every command uses `uv run ...`, never bare `pip`.
- No placeholder/TODO code.
- Every mutation to `data/criteria.yaml` goes through the `dast-bench criteria` CLI — the skill file must never instruct direct YAML edits.
- The skill must never consider its work complete while `dast-bench criteria list` shows a `warning: weights sum to X, expected 100.00` line.
- `remove-criterion` must not delete a vendor's historical `ScoreEntry` rows for the removed criterion — only warn that they're now orphaned.
- Existing test suite (56 tests as of the last commit) must continue passing unmodified.

---

### Task 1: CLI — `remove-criterion` and `update-criterion`

**Files:**
- Modify: `core/cli.py` (append to the existing `criteria_app` block, after `list_criteria`)
- Modify: `tests/test_cli_criteria.py` (append new tests)

**Interfaces:**
- Consumes: `storage.{load_criteria, save_criteria, list_vendors}` (existing), `CriteriaTaxonomy.get` (existing), `Vendor.score_for` (existing), module-level `CRITERIA_PATH`, `CANDIDATES_DIR` (existing constants in `core/cli.py`).
- Produces: CLI commands `criteria remove-criterion --id <id>` and `criteria update-criterion --id <id> [--category] [--name] [--description] [--weight] [--rubric]`, used only by the `dast-criteria` skill written in Task 2 (and directly by a human via `uv run dast-bench criteria ...`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_criteria.py`:

```python
def test_remove_criterion_removes_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "remove-criterion", "--id", "c1"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "c1" not in result.output


def test_remove_criterion_errors_on_unknown_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["criteria", "remove-criterion", "--id", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_remove_criterion_warns_about_orphaned_scores(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    runner.invoke(app, ["candidate", "add", "--id", "v1", "--name", "Vendor One", "--source", "discovered"])
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    result = runner.invoke(app, ["criteria", "remove-criterion", "--id", "c1"])
    assert result.exit_code == 0, result.output
    assert "1 vendor" in result.output
    assert "orphaned" in result.output


def test_update_criterion_changes_only_passed_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "update-criterion", "--id", "c1", "--name", "New Name"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "New Name" in result.output
    assert "weight=20" in result.output


def test_update_criterion_updates_weight(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "update-criterion", "--id", "c1", "--weight", "75"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "weight=75" in result.output


def test_update_criterion_errors_on_unknown_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["criteria", "update-criterion", "--id", "missing", "--name", "x"])
    assert result.exit_code != 0
    assert "not found" in result.output
```

Note: `ADD_ARGS` and `runner` are already defined at the top of this file (they add criterion `c1` with `--weight 20`) — reuse them, don't redefine.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_criteria.py -v`
Expected: FAIL — `No such command 'remove-criterion'` / `No such command 'update-criterion'`.

- [ ] **Step 3: Append to `core/cli.py`**

Add immediately after the existing `list_criteria` function (before the `candidate_app = typer.Typer()` line):

```python
@criteria_app.command("remove-criterion")
def remove_criterion(id: str = typer.Option(...)) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    criterion = taxonomy.get(id)
    if not criterion:
        typer.echo(f"error: criterion '{id}' not found")
        raise typer.Exit(code=1)
    taxonomy.criteria = [c for c in taxonomy.criteria if c.id != id]
    storage.save_criteria(taxonomy, CRITERIA_PATH)
    affected = [v for v in storage.list_vendors(CANDIDATES_DIR) if v.score_for(id)]
    if affected:
        typer.echo(
            f"warning: {len(affected)} vendor(s) have existing scores for '{id}' — "
            "those scores are now orphaned, not deleted"
        )
    typer.echo(f"removed criterion '{id}'")


@criteria_app.command("update-criterion")
def update_criterion(
    id: str = typer.Option(...),
    category: str = typer.Option(None),
    name: str = typer.Option(None),
    description: str = typer.Option(None),
    weight: float = typer.Option(None),
    rubric: str = typer.Option(None),
) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    criterion = taxonomy.get(id)
    if not criterion:
        typer.echo(f"error: criterion '{id}' not found")
        raise typer.Exit(code=1)
    if category is not None:
        criterion.category = category
    if name is not None:
        criterion.name = name
    if description is not None:
        criterion.description = description
    if weight is not None:
        criterion.weight = weight
    if rubric is not None:
        criterion.rubric = rubric
    storage.save_criteria(taxonomy, CRITERIA_PATH)
    typer.echo(f"updated criterion '{id}'")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_criteria.py -v`
Expected: PASS (11 passed — 5 existing + 6 new).

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass (62 passed — 56 existing + 6 new), zero failures.

- [ ] **Step 6: Commit**

```bash
git add core/cli.py tests/test_cli_criteria.py
git commit -m "Add criteria remove-criterion and update-criterion CLI commands"
```

---

### Task 2: The `dast-criteria` skill file

**Files:**
- Create: `.claude/skills/dast-criteria/SKILL.md`

**Interfaces:**
- Consumes: `dast-bench criteria {list, add-criterion, update-criterion, remove-criterion, set-weight}` (Task 1 + existing commands) — the skill only ever calls these via Bash, never edits YAML.
- Produces: nothing consumed by another task — this is the final deliverable of this plan. Not unit-tested (a prompt file); reviewed by the evaluator reading it.

- [ ] **Step 1: Create the directory and write the complete skill file**

Create `.claude/skills/dast-criteria/SKILL.md` with exactly this content:

````markdown
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
`warning: weights sum to X, expected 100.00` line, the taxonomy is not yet
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
````

- [ ] **Step 2: Verify the file is valid, complete Markdown with YAML frontmatter**

Run: `head -5 .claude/skills/dast-criteria/SKILL.md`
Expected output starts with:
```
---
name: dast-criteria
description: Use to establish or revise the DAST evaluation criteria taxonomy (categories, criteria, weights, rubrics) that vendors will be scored against. Re-invocable anytime — first run scaffolds from an industry-standard baseline, later runs revise what's already there.
---
```

Run: `grep -c '^- \*\*' .claude/skills/dast-criteria/SKILL.md`
Expected: `12` (one bolded criterion-id bullet per criterion in the baseline taxonomy — confirms none were dropped while writing the file).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/dast-criteria/SKILL.md
git commit -m "Add dast-criteria skill"
```

---

## Self-Review Notes

- **Spec coverage:** the design doc's Architecture section (two CLI additions + skill file), Baseline Taxonomy Content (all 12 criteria present, correctly weighted, summing to 100 — verified: 15+10+5=30, 15+10=25, 12+8=20, 8+5+7=20, 3+2=5, total 100), Data Flow (Steps 1–5 in the skill file mirror the design doc's 7-step flow, condensed since some design-doc steps were narration rather than distinct agent actions), Error Handling (relay `error:` verbatim, orphaned-score warning is non-blocking, weight-warning is blocking), and Testing (Task 1 has real TDD tests; Task 2 is explicitly not unit-tested, matching the design doc) are all covered.
- **Placeholder scan:** no TODO/TBD markers; every step has complete content, including the full skill file text and all 12 rubrics.
- **Type consistency:** `remove-criterion`/`update-criterion` use the same `--id` flag name and `error: criterion '<id>' not found` message format as the existing `set-weight` command; `update-criterion`'s optional-field pattern (`typer.Option(None)`, apply only if not `None`) is a new pattern in this file but consistent with Typer conventions used elsewhere in the codebase (e.g. `candidate add`'s optional `--website`/`--notes` default to `""` rather than `None` — the difference here is intentional, since `None` here means "field not specified, don't change it," a distinct semantic from "specified as empty").
