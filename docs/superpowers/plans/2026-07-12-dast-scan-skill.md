# dast-scan Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the small CLI/model surface `dast-scan` needs (a vendor-to-CI-tool mapping, and commands to define benchmark ground truth), then write the `dast-scan` Claude Code skill file itself, per `docs/superpowers/specs/2026-07-12-dast-scan-skill-design.md`.

**Architecture:** Three tasks. Task 1 adds `Vendor.ci_tool_id` plus `candidate set-ci-tool` (mirrors the existing `candidate set-status` shape exactly). Task 2 adds a new `benchmark` command group (`add`, `add-vulnerability`, `list`) mirroring `criteria add-criterion`'s one-thing-per-call pattern. Task 3 is the skill file itself — a prompt file with no code, orchestrating the already-built `dast-benchmark.yml` CI workflow via the `gh` CLI and the already-built `scan ingest-scan-result` command.

**Tech Stack:** Python (Typer CLI, Pydantic models, pytest), `gh` CLI (already authenticated in this environment), one new Markdown skill file.

## Global Constraints

- Every *mutation* to `data/candidates/*.yaml` or `data/benchmarks.yaml` must go through the `dast-bench` CLI — the skill file must never instruct direct YAML edits. Reading a vendor's current record directly (`Read data/candidates/<id>.yaml`) for inspection is fine — only writes must go through the CLI.
- The skill must only refine `detection-accuracy` and `false-positive-rate` with hands-on evidence (`--confidence hands-on`). Any other qualitative finding (CI/CD friction, a manual tweak needed, any caveat) goes into `candidate log-observation` as a tagged note, never a formal score.
- `dast-scan` only ever runs a vendor's tool if that vendor's `ci_tool_id` is set and matches a `tool` value the CI workflow already supports (currently only `zap`). If unset or unsupported, the skill says so and points at `dast-onboard-tool` (not yet built) — it must never itself edit `.github/workflows/dast-benchmark.yml`.
- One finalist per invocation; within that invocation, cover whichever of the two benchmark targets (Juice Shop, VAmPI) the vendor doesn't yet have a `HandsOnResult` for.
- The `evaluated` status transition only happens after evaluator confirmation, once both targets are scanned — never automatically.
- Use `uv run pytest ...` for all test commands (never bare `pytest` or `pip`).
- Do not touch `.github/workflows/dast-benchmark.yml` or `uv.lock` in this plan — both have pre-existing uncommitted changes unrelated to this work.

---

### Task 1: `Vendor.ci_tool_id` field + `candidate set-ci-tool` command

**Files:**
- Modify: `core/models.py:77-90` (`Vendor` class)
- Modify: `core/cli.py:142-147` (insert new command directly after `set_status`)
- Modify: `README.md` (CLI reference section — fix a stale line and document the new command)
- Test: `tests/test_cli_candidate.py`

**Interfaces:**
- Consumes: `storage.load_vendor`, `storage.save_vendor`, `storage.vendor_path`, `_load_vendor_or_exit` (all already exist in `core/cli.py`).
- Produces: `Vendor.ci_tool_id: str | None` (consumed by Task 3's skill file) and CLI command `candidate set-ci-tool --id --tool` (consumed by Task 3's skill file, Step 2).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli_candidate.py` (after `test_log_observation_appends_to_vendor`, which is currently the last test in the file):

```python
def test_set_ci_tool_updates_vendor(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(app, ["candidate", "set-ci-tool", "--id", "v1", "--tool", "zap"])
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.ci_tool_id == "zap"


def test_set_ci_tool_errors_on_unknown_vendor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["candidate", "set-ci-tool", "--id", "missing", "--tool", "zap"])
    assert result.exit_code != 0
    assert "not found" in result.output
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_cli_candidate.py::test_set_ci_tool_updates_vendor tests/test_cli_candidate.py::test_set_ci_tool_errors_on_unknown_vendor -v`
Expected: FAIL — `set-ci-tool` is not a registered command (Typer reports "No such command").

- [ ] **Step 3: Add the `ci_tool_id` field to `Vendor`**

In `core/models.py`, the current `Vendor` class (lines 77-90) reads:

```python
class Vendor(BaseModel):
    id: str
    name: str
    source: VendorSource
    status: VendorStatus = VendorStatus.CANDIDATE
    website: str = ""
    notes: str = ""
    scores: list[ScoreEntry] = Field(default_factory=list)
    hands_on_results: list[HandsOnResult] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)

    def score_for(self, criterion_id: str) -> ScoreEntry | None:
        matches = [s for s in self.scores if s.criterion_id == criterion_id]
        return matches[-1] if matches else None
```

Change it to add `ci_tool_id` right after `notes`:

```python
class Vendor(BaseModel):
    id: str
    name: str
    source: VendorSource
    status: VendorStatus = VendorStatus.CANDIDATE
    website: str = ""
    notes: str = ""
    ci_tool_id: str | None = None
    scores: list[ScoreEntry] = Field(default_factory=list)
    hands_on_results: list[HandsOnResult] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)

    def score_for(self, criterion_id: str) -> ScoreEntry | None:
        matches = [s for s in self.scores if s.criterion_id == criterion_id]
        return matches[-1] if matches else None
```

- [ ] **Step 4: Add the `candidate set-ci-tool` command**

In `core/cli.py`, the current `set_status` command (lines 142-147) reads:

```python
@candidate_app.command("set-status")
def set_status(id: str = typer.Option(...), status: VendorStatus = typer.Option(...)) -> None:
    vendor = _load_vendor_or_exit(id)
    vendor.status = status
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, id))
    typer.echo(f"set status of '{id}' to {status.value}")
```

Insert a new command directly after it (before `@candidate_app.command("record-score")`):

```python
@candidate_app.command("set-ci-tool")
def set_ci_tool(id: str = typer.Option(...), tool: str = typer.Option(...)) -> None:
    vendor = _load_vendor_or_exit(id)
    vendor.ci_tool_id = tool
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, id))
    typer.echo(f"set ci-tool of '{id}' to {tool}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cli_candidate.py -v`
Expected: PASS (all tests in the file, including the two new ones)

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS (all existing tests unaffected — `ci_tool_id` defaults to `None`, so no existing vendor fixture/round-trip test breaks)

- [ ] **Step 7: Update the README's CLI reference**

In `README.md`, the current candidate/scan block reads:

```
dast-bench candidate add --id --name --source --website --notes
dast-bench candidate set-status --id --status
dast-bench candidate record-score --vendor-id --criterion-id --score --evidence --confidence
dast-bench candidate list

dast-bench scan log-observation --vendor-id --context --note --tags
dast-bench scan ingest-scan-result --vendor-id --benchmark-id --file --test-id --description --automated
```

Replace it with (this also fixes a pre-existing stale line: `log-observation` moved from `scan` to `candidate` during the `dast-discovery` plan, and the README was never updated):

```
dast-bench candidate add --id --name --source --website --notes
dast-bench candidate set-status --id --status
dast-bench candidate set-ci-tool --id --tool
dast-bench candidate record-score --vendor-id --criterion-id --score --evidence --confidence
dast-bench candidate log-observation --vendor-id --context --note --tags
dast-bench candidate list

dast-bench scan ingest-scan-result --vendor-id --benchmark-id --file --test-id --description --automated
```

- [ ] **Step 8: Commit**

```bash
git add core/models.py core/cli.py tests/test_cli_candidate.py README.md
git commit -m "Add Vendor.ci_tool_id and candidate set-ci-tool command"
```

---

### Task 2: `benchmark` command group (`add`, `add-vulnerability`, `list`)

**Files:**
- Modify: `core/cli.py` (new `benchmark_app` sub-app, registered after `scan_app`'s section and before `@app.command("status")`)
- Modify: `README.md` (CLI reference section — document the new commands)
- Test: Create `tests/test_cli_benchmark.py`

**Interfaces:**
- Consumes: `storage.load_benchmarks(BENCHMARKS_PATH)`, `storage.save_benchmarks(benchmarks, BENCHMARKS_PATH)` (both already exist in `core/storage.py`), `Benchmark`, `BenchmarkVulnerability` (already exist in `core/models.py`), `BENCHMARKS_PATH` (already defined at `core/cli.py:22`).
- Produces: CLI commands `benchmark add --id --name --target-type`, `benchmark add-vulnerability --benchmark-id --vuln-id --name --severity`, `benchmark list` (all consumed by Task 3's skill file).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_benchmark.py`:

```python
from typer.testing import CliRunner

from core import storage
from core.cli import app

runner = CliRunner()

ADD_ARGS = ["benchmark", "add", "--id", "juice-shop", "--name", "OWASP Juice Shop", "--target-type", "spa"]


def test_add_benchmark_then_list_shows_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["benchmark", "list"])
    assert "juice-shop" in result.output
    assert "OWASP Juice Shop" in result.output
    assert "known_vulnerabilities=0" in result.output


def test_add_benchmark_rejects_duplicate_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_add_vulnerability_appends_to_benchmark(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(
        app,
        [
            "benchmark", "add-vulnerability",
            "--benchmark-id", "juice-shop", "--vuln-id", "40018",
            "--name", "SQL Injection", "--severity", "high",
        ],
    )
    assert result.exit_code == 0, result.output
    benchmarks = storage.load_benchmarks(tmp_path / "data" / "benchmarks.yaml")
    assert benchmarks[0].known_vulnerabilities[0].id == "40018"
    result = runner.invoke(app, ["benchmark", "list"])
    assert "known_vulnerabilities=1" in result.output


def test_add_vulnerability_errors_on_unknown_benchmark(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "benchmark", "add-vulnerability",
            "--benchmark-id", "missing", "--vuln-id", "40018",
            "--name", "SQL Injection", "--severity", "high",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_add_vulnerability_rejects_duplicate_vuln_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    vuln_args = [
        "benchmark", "add-vulnerability",
        "--benchmark-id", "juice-shop", "--vuln-id", "40018",
        "--name", "SQL Injection", "--severity", "high",
    ]
    runner.invoke(app, vuln_args)
    result = runner.invoke(app, vuln_args)
    assert result.exit_code != 0
    assert "already exists" in result.output
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_cli_benchmark.py -v`
Expected: FAIL — `benchmark` is not a registered command group.

- [ ] **Step 3: Add the `benchmark` command group**

In `core/cli.py`, add `Benchmark` and `BenchmarkVulnerability` to the existing models import (currently line 9):

```python
from .models import Confidence, Criterion, HandsOnResult, Observation, ScoreEntry, Vendor, VendorSource, VendorStatus
```

becomes:

```python
from .models import (
    Benchmark,
    BenchmarkVulnerability,
    Confidence,
    Criterion,
    HandsOnResult,
    Observation,
    ScoreEntry,
    Vendor,
    VendorSource,
    VendorStatus,
)
```

Then insert the new sub-app directly after the `ingest_scan_result` function (i.e. immediately before `@app.command("status")`, which currently starts at `core/cli.py:264`):

```python
benchmark_app = typer.Typer()
app.add_typer(benchmark_app, name="benchmark")


@benchmark_app.command("add")
def add_benchmark(
    id: str = typer.Option(...),
    name: str = typer.Option(...),
    target_type: str = typer.Option(...),
) -> None:
    benchmarks = storage.load_benchmarks(BENCHMARKS_PATH)
    if any(b.id == id for b in benchmarks):
        typer.echo(f"error: benchmark '{id}' already exists")
        raise typer.Exit(code=1)
    benchmarks.append(Benchmark(id=id, name=name, target_type=target_type))
    storage.save_benchmarks(benchmarks, BENCHMARKS_PATH)
    typer.echo(f"added benchmark '{id}'")


@benchmark_app.command("add-vulnerability")
def add_benchmark_vulnerability(
    benchmark_id: str = typer.Option(...),
    vuln_id: str = typer.Option(...),
    name: str = typer.Option(...),
    severity: str = typer.Option(...),
) -> None:
    benchmarks = storage.load_benchmarks(BENCHMARKS_PATH)
    bench = next((b for b in benchmarks if b.id == benchmark_id), None)
    if not bench:
        typer.echo(f"error: benchmark '{benchmark_id}' not found")
        raise typer.Exit(code=1)
    if any(v.id == vuln_id for v in bench.known_vulnerabilities):
        typer.echo(f"error: vulnerability '{vuln_id}' already exists on benchmark '{benchmark_id}'")
        raise typer.Exit(code=1)
    bench.known_vulnerabilities.append(BenchmarkVulnerability(id=vuln_id, name=name, severity=severity))
    storage.save_benchmarks(benchmarks, BENCHMARKS_PATH)
    typer.echo(f"added vulnerability '{vuln_id}' to benchmark '{benchmark_id}'")


@benchmark_app.command("list")
def list_benchmarks() -> None:
    for b in storage.load_benchmarks(BENCHMARKS_PATH):
        typer.echo(f"{b.id}\t{b.name}\t{b.target_type}\tknown_vulnerabilities={len(b.known_vulnerabilities)}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cli_benchmark.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS (all existing tests unaffected)

- [ ] **Step 6: Update the README's CLI reference**

In `README.md`, directly after the line `dast-bench scan ingest-scan-result --vendor-id --benchmark-id --file --test-id --description --automated` (added/kept by Task 1's Step 7), add a blank line followed by:

```
dast-bench benchmark add --id --name --target-type
dast-bench benchmark add-vulnerability --benchmark-id --vuln-id --name --severity
dast-bench benchmark list
```

- [ ] **Step 7: Commit**

```bash
git add core/cli.py tests/test_cli_benchmark.py README.md
git commit -m "Add benchmark command group (add, add-vulnerability, list)"
```

---

### Task 3: The `dast-scan` skill file

**Files:**
- Create: `.claude/skills/dast-scan/SKILL.md`

**Interfaces:**
- Consumes: `dast-bench candidate {list, set-ci-tool, record-score, set-status, log-observation}`, `dast-bench benchmark {list, add, add-vulnerability}`, `dast-bench criteria list`, `dast-bench scan ingest-scan-result` (all already exist after Tasks 1-2), `gh` CLI (`workflow run`, `run list`, `run watch`, `run download`), plus direct `Read` of a vendor's YAML (inspection only) and `Bash` with `run_in_background: true` for the CI wait.
- Produces: nothing consumed by another task in this plan — this is the plan's final deliverable, reviewed by the evaluator reading it once written.

- [ ] **Step 1: Create the directory and write the complete skill file**

Create `.claude/skills/dast-scan/SKILL.md` with exactly this content:

````markdown
---
name: dast-scan
description: Use to hands-on test a finalist vendor's tool against the ephemeral benchmark targets (Juice Shop, VAmPI) via the CI workflow, refine detection-accuracy/false-positive-rate scores with the results, and — once both targets are scanned — drive that finalist to evaluated status. Re-invocable anytime, one finalist per invocation.
---

# dast-scan

This skill fills in **hands-on evidence** for a finalist vendor — it runs
that vendor's tool (via the already-built `dast-benchmark.yml` CI workflow)
against Juice Shop and VAmPI, records the results, and refines the two
criteria whose scores are directly computable from detection results:
`detection-accuracy` and `false-positive-rate`. It never decides finalists
(`dast-shortlist`'s job) and never wires a *new* tool into the CI workflow
(`dast-onboard-tool`'s job — not yet built). Any other hands-on impression
(CI/CD integration friction, a manual tweak that was needed, any other
caveat) belongs in `candidate log-observation`, tagged, not in a formal
score — that criterion-level judgment stays out of this skill's scope.

Never edit `data/candidates/*.yaml` or `data/benchmarks.yaml` directly.
Every change happens through `dast-bench` CLI commands: `candidate
set-ci-tool`, `candidate record-score`, `candidate set-status`, `candidate
log-observation`, `benchmark add`, `benchmark add-vulnerability`, `scan
ingest-scan-result`. Reading a vendor's current record directly
(`data/candidates/<id>.yaml`) is fine for inspection — only writes must go
through the CLI.

**Score exactly one finalist per invocation.** Cover whichever of the two
benchmark targets that finalist doesn't yet have a result for in this one
pass (usually both, the first time).

## Step 1: Identify which finalist to scan

If the evaluator names a specific vendor, use that. Otherwise, run
`dast-bench candidate list` and suggest the first `finalist`-status vendor
that doesn't yet have hands-on results for both Juice Shop and VAmPI (check
via Step 4's direct read).

## Step 2: Check the vendor is wired into the CI workflow

Read the vendor's record directly (`data/candidates/<id>.yaml`) and check
`ci_tool_id`. The CI workflow currently only supports `tool=zap`.

**If `ci_tool_id` is unset:** ask the evaluator what CI `tool` value this
vendor's product corresponds to, then persist it:
```
dast-bench candidate set-ci-tool --id <id> --tool <tool>
```

**If `ci_tool_id` is set but isn't a value the workflow supports (currently
only `zap`):** tell the evaluator this vendor's tool isn't wired into
`.github/workflows/dast-benchmark.yml` yet. Wiring in a new tool (a new
workflow step, docker/CLI invocation, auth/licensing handling, a new
normalize script) is `dast-onboard-tool`'s job, not this skill's — do not
attempt to edit the workflow yourself. Stop here for this vendor.

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
target before proceeding — do not silently rerun or silently skip.

## Step 5: Run the CI workflow for each target still needed

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
succeeded; this finalist just isn't ready for Step 6 yet.

On success, download the workflow's already-normalized artifact directly —
the workflow itself runs `.github/scripts/normalize/zap.py` and uploads the
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

## Step 6: Propose refined scores once both targets are scanned

Once the vendor has `HandsOnResult`s for **both** Juice Shop and VAmPI, read
both results' `outcome` text (e.g. "detected 8/10 known vulnerabilities, 2
false positive(s)"), aggregate the detected/known counts and false-positive
counts across both, and run `dast-bench criteria list` to get the current
rubric text for `detection-accuracy` and `false-positive-rate`. Propose a
refined score for each against that rubric, citing the aggregate numbers as
evidence. Present both proposed scores together — nothing persisted yet —
for the evaluator to review and adjust.

If either target's scan hasn't happened yet for this vendor, stop after
Step 5 instead — confirm what was scanned this round and that the other
target remains outstanding.

## Step 7: Persist confirmed scores and offer the evaluated transition

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

## Step 8: Summarize

Summarize for the evaluator what was scanned, what scores were refined
(and with what evidence), and whether the vendor was transitioned to
`evaluated`, so they have a clear record of what this invocation changed.
````

- [ ] **Step 2: Verify the file is valid, complete Markdown with YAML frontmatter**

Run: `head -6 .claude/skills/dast-scan/SKILL.md`
Expected output starts with:
```
---
name: dast-scan
description: Use to hands-on test a finalist vendor's tool against the ephemeral benchmark targets (Juice Shop, VAmPI) via the CI workflow, refine detection-accuracy/false-positive-rate scores with the results, and — once both targets are scanned — drive that finalist to evaluated status. Re-invocable anytime, one finalist per invocation.
---

# dast-scan
```

Run: `grep -c '^## Step' .claude/skills/dast-scan/SKILL.md`
Expected: `8` (one per numbered step — confirms none were dropped while writing the file).

Run: `grep -c 'add-vulnerability --benchmark-id' .claude/skills/dast-scan/SKILL.md`
Expected: `19` (10 Juice Shop entries + 9 VAmPI entries in Step 3 — confirms the full curated ground-truth list transcribed correctly, none dropped; this pattern excludes the one incidental mention of `add-vulnerability` in the intro paragraph, which would otherwise inflate a plain count to 20).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/dast-scan/SKILL.md
git commit -m "Add dast-scan skill"
```

---

## Self-Review Notes

- **Spec coverage:** the design doc's Goals (seed benchmark ground truth,
  persist `ci_tool_id`, orchestrate CI via `gh`, refine only the two
  detection-related criteria, capture other findings as observations, drive
  the `evaluated` transition on evaluator confirmation) and Non-Goals
  (no finalist-deciding, no new-tool wiring, no generic pipeline-observer
  abstraction) are all covered — Task 1 covers `ci_tool_id`/`set-ci-tool`,
  Task 2 covers benchmark seeding commands, Task 3's skill file covers
  orchestration, revision detection, score refinement, and the evaluated
  gate. Architecture's `gh` recipe and Error Handling's partial-completion
  and verbatim-relay rules are both reflected in Task 3 Step 5.
- **Placeholder scan:** no TODO/TBD markers. The benchmark ground-truth data
  in Task 3 Step 3 is real, sourced content (ZAP plugin IDs verified against
  ZAP's own alert documentation; Juice Shop/VAmPI vulnerability categories
  verified against each project's own documentation/README), not a stand-in
  — see the ID-scheme explanation embedded directly after the seeding
  commands.
- **Type consistency:** `--confidence hands-on` matches `Confidence.HANDS_ON
  = "hands-on"` in `core/models.py:23`. `--status evaluated` matches
  `VendorStatus.EVALUATED = "evaluated"` in `core/models.py:18`. All new CLI
  flag names (`set-ci-tool --id --tool`, `benchmark add --id --name
  --target-type`, `benchmark add-vulnerability --benchmark-id --vuln-id
  --name --severity`) are used identically across Tasks 1-2's implementation
  and Task 3's skill file — no drift between what's built and what's
  documented as usable.
