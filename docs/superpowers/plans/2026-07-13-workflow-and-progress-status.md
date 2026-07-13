# Workflow Command and Progress Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `dast-bench workflow` command (a static, hardcoded reference table of all six skills) and enhance `dast-bench status` to append a synthesized "Progress:" + "Next:" section below its existing, unchanged gap-report output, per `docs/superpowers/specs/2026-07-13-workflow-and-progress-status-design.md`.

**Architecture:** One new module, `core/workflow.py`, holding a static `SKILLS` table and a `phase_report()` function computed purely from the same `CriteriaTaxonomy`/`Vendor` data `core/status.py`'s `gap_report()` already takes — no new persisted state. Two small `core/cli.py` changes consume it: a new `workflow` command, and an addition (never a removal or edit) to the existing `status` command.

**Tech Stack:** Python (Pydantic models already in place, Typer CLI, pytest) — no new dependencies.

## Global Constraints

- `dast-bench status`'s existing gap-report output (used programmatically by the `dast-shortlist` and `dast-report` skills today) must remain byte-for-byte unchanged — this plan is strictly additive to it, never edits its existing lines.
- No new persisted data — both features are pure reads over `data/criteria.yaml` and `data/candidates/*.yaml`, exactly as `status` already loads them.
- `dast-bench workflow` loads no data at all — it is a static lookup table, print-only.
- The "Next:" recommendation always resolves to exactly one of: `dast-criteria`, `dast-discovery`, `dast-shortlist`, `dast-scan` (paired with a `dast-onboard-tool` mention if not CI-wired), or `dast-report` — evaluated in that fixed order, first incomplete phase wins.
- `dast-report`'s completion is never tracked as done/not-done (no reliable signal exists — `reports/` is gitignored) — it is always the fallback recommendation once every other phase is settled.
- Use `uv run pytest ...` for all test commands.

---

### Task 1: `core/workflow.py` — the static skill table and phase-detection logic

**Files:**
- Create: `core/workflow.py`
- Test: `tests/test_workflow.py`

**Interfaces:**
- Consumes: `core.models.CriteriaTaxonomy`, `core.models.Vendor`, `core.models.VendorSource`, `core.models.VendorStatus` (all already exist, unchanged).
- Produces: `SKILLS: list[dict[str, str]]` (keys: `name`, `purpose`, `reads`, `writes`) and `phase_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> list[str]` — both consumed by Task 2's CLI changes.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workflow.py`:

```python
from core.models import (
    Confidence,
    Criterion,
    CriteriaTaxonomy,
    ScoreEntry,
    Vendor,
    VendorSource,
    VendorStatus,
)
from core.workflow import SKILLS, phase_report


def _taxonomy(*weights: float) -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id=f"c{i}", category="Coverage", name=f"n{i}", description="d", weight=w, rubric="r")
            for i, w in enumerate(weights)
        ]
    )


def _scored_vendor(vendor_id: str, criterion_ids: list[str], status: VendorStatus = VendorStatus.CANDIDATE) -> Vendor:
    vendor = Vendor(id=vendor_id, name=vendor_id, source=VendorSource.DISCOVERED, status=status)
    for cid in criterion_ids:
        vendor.scores.append(ScoreEntry(criterion_id=cid, score=3, evidence="e", confidence=Confidence.PAPER))
    return vendor


def test_skills_table_has_all_six_skills_in_order():
    assert [s["name"] for s in SKILLS] == [
        "dast-criteria",
        "dast-discovery",
        "dast-shortlist",
        "dast-onboard-tool",
        "dast-scan",
        "dast-report",
    ]
    for skill in SKILLS:
        assert skill["purpose"] and skill["reads"] and skill["writes"]


def test_phase_report_criteria_not_started():
    lines = phase_report(CriteriaTaxonomy(), [])
    assert "[ ] Criteria      not started" in lines


def test_phase_report_criteria_invalid_weights():
    lines = phase_report(_taxonomy(50), [])
    assert "[!] Criteria      1 criteria, weights invalid" in lines


def test_phase_report_criteria_done():
    lines = phase_report(_taxonomy(100), [])
    assert "[x] Criteria      1 criteria, weights sum to 100" in lines


def test_phase_report_discovery_empty():
    lines = phase_report(_taxonomy(100), [])
    assert "[ ] Discovery     no candidates yet" in lines


def test_phase_report_discovery_counts_seeded_and_discovered():
    v1 = Vendor(id="v1", name="v1", source=VendorSource.SEEDED)
    v2 = Vendor(id="v2", name="v2", source=VendorSource.DISCOVERED)
    lines = phase_report(_taxonomy(100), [v1, v2])
    assert "[x] Discovery     2 candidates (1 seeded, 1 discovered)" in lines


def test_phase_report_shortlist_partial():
    taxonomy = _taxonomy(50, 50)
    vendor = _scored_vendor("v1", ["c0"])
    lines = phase_report(taxonomy, [vendor])
    assert "[ ] Shortlist     0/1 candidates fully scored" in lines


def test_phase_report_shortlist_scored_pending_decision():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.CANDIDATE)
    lines = phase_report(taxonomy, [vendor])
    assert "[ ] Shortlist     scored, 1 finalist decision(s) pending" in lines


def test_phase_report_shortlist_done():
    taxonomy = _taxonomy(100)
    v1 = _scored_vendor("v1", ["c0"], status=VendorStatus.FINALIST)
    v2 = _scored_vendor("v2", ["c0"], status=VendorStatus.REJECTED)
    lines = phase_report(taxonomy, [v1, v2])
    assert "[x] Shortlist     2/2 scored, 1 finalists, 1 rejected" in lines


def test_phase_report_hands_on_scan_no_finalists():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.REJECTED)
    lines = phase_report(taxonomy, [vendor])
    assert "[ ] Hands-on scan no finalists yet" in lines


def test_phase_report_hands_on_scan_partial():
    taxonomy = _taxonomy(100)
    v1 = _scored_vendor("v1", ["c0"], status=VendorStatus.FINALIST)
    v2 = _scored_vendor("v2", ["c0"], status=VendorStatus.EVALUATED)
    lines = phase_report(taxonomy, [v1, v2])
    assert "[ ] Hands-on scan 1/2 finalists evaluated" in lines


def test_phase_report_hands_on_scan_done():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.EVALUATED)
    lines = phase_report(taxonomy, [vendor])
    assert "[x] Hands-on scan 1/1 finalists evaluated" in lines


def test_next_action_recommends_criteria_when_missing():
    lines = phase_report(CriteriaTaxonomy(), [])
    assert any(line.startswith("Next: run dast-criteria --") for line in lines)


def test_next_action_recommends_discovery_when_no_vendors():
    lines = phase_report(_taxonomy(100), [])
    assert any(line.startswith("Next: run dast-discovery --") for line in lines)


def test_next_action_recommends_shortlist_when_scores_missing():
    taxonomy = _taxonomy(50, 50)
    vendor = _scored_vendor("v1", ["c0"])
    lines = phase_report(taxonomy, [vendor])
    assert any(line.startswith("Next: run dast-shortlist --") for line in lines)


def test_next_action_recommends_shortlist_when_decisions_pending():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.CANDIDATE)
    lines = phase_report(taxonomy, [vendor])
    assert any(line.startswith("Next: run dast-shortlist --") for line in lines)


def test_next_action_recommends_scan_when_finalists_pending():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.FINALIST)
    lines = phase_report(taxonomy, [vendor])
    assert any(line.startswith("Next: run dast-scan (or dast-onboard-tool if not CI-wired) --") for line in lines)


def test_next_action_recommends_report_when_everything_settled():
    taxonomy = _taxonomy(100)
    v1 = _scored_vendor("v1", ["c0"], status=VendorStatus.EVALUATED)
    v2 = _scored_vendor("v2", ["c0"], status=VendorStatus.REJECTED)
    lines = phase_report(taxonomy, [v1, v2])
    assert any(line.startswith("Next: everything's current -- run dast-report --") for line in lines)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workflow.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.workflow'`

- [ ] **Step 3: Write `core/workflow.py`**

```python
# core/workflow.py
from __future__ import annotations

from .models import CriteriaTaxonomy, Vendor, VendorSource, VendorStatus

SKILLS: list[dict[str, str]] = [
    {
        "name": "dast-criteria",
        "purpose": "Establish or revise the criteria taxonomy (categories, weights, rubrics)",
        "reads": "-",
        "writes": "data/criteria.yaml",
    },
    {
        "name": "dast-discovery",
        "purpose": "Build or extend the candidate vendor list via live research + seeded must-includes",
        "reads": "data/criteria.yaml",
        "writes": "data/candidates/*.yaml",
    },
    {
        "name": "dast-shortlist",
        "purpose": "Score one candidate against every criterion; once all are scored, decide finalists/rejected",
        "reads": "data/criteria.yaml, data/candidates/*.yaml",
        "writes": "data/candidates/*.yaml (scores, status)",
    },
    {
        "name": "dast-onboard-tool",
        "purpose": "Wire a new DAST tool into the CI workflow, or produce a manual runbook",
        "reads": "data/candidates/*.yaml",
        "writes": ".github/workflows/dast-benchmark.yml, data/candidates/*.yaml (ci_tool_id)",
    },
    {
        "name": "dast-scan",
        "purpose": "Hands-on test a finalist (CI or manual), refine detection scores, mark evaluated",
        "reads": "data/candidates/*.yaml, data/benchmarks.yaml",
        "writes": "data/candidates/*.yaml (hands-on results, scores, status)",
    },
    {
        "name": "dast-report",
        "purpose": "Render the SSoT into reports + write a narrative executive summary",
        "reads": "data/criteria.yaml, data/candidates/*.yaml",
        "writes": "reports/",
    },
]


def _skill(name: str) -> dict[str, str]:
    return next(s for s in SKILLS if s["name"] == name)


def _fully_scored(vendor: Vendor, taxonomy: CriteriaTaxonomy) -> bool:
    return all(vendor.score_for(c.id) is not None for c in taxonomy.criteria)


def phase_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> list[str]:
    lines = ["", "Progress:"]

    if not taxonomy.criteria:
        lines.append("[ ] Criteria      not started")
    elif taxonomy.validate_weights():
        lines.append(f"[!] Criteria      {len(taxonomy.criteria)} criteria, weights invalid")
    else:
        lines.append(f"[x] Criteria      {len(taxonomy.criteria)} criteria, weights sum to 100")

    if not vendors:
        lines.append("[ ] Discovery     no candidates yet")
    else:
        seeded = sum(1 for v in vendors if v.source == VendorSource.SEEDED)
        discovered = len(vendors) - seeded
        lines.append(f"[x] Discovery     {len(vendors)} candidates ({seeded} seeded, {discovered} discovered)")

    if not vendors:
        lines.append("[ ] Shortlist     no candidates yet")
    elif not taxonomy.criteria:
        lines.append("[ ] Shortlist     no criteria to score against yet")
    else:
        scored = [v for v in vendors if _fully_scored(v, taxonomy)]
        undecided = [v for v in vendors if v.status == VendorStatus.CANDIDATE]
        if len(scored) < len(vendors):
            lines.append(f"[ ] Shortlist     {len(scored)}/{len(vendors)} candidates fully scored")
        elif undecided:
            lines.append(f"[ ] Shortlist     scored, {len(undecided)} finalist decision(s) pending")
        else:
            finalists = sum(1 for v in vendors if v.status in (VendorStatus.FINALIST, VendorStatus.EVALUATED))
            rejected = sum(1 for v in vendors if v.status == VendorStatus.REJECTED)
            lines.append(
                f"[x] Shortlist     {len(vendors)}/{len(vendors)} scored, {finalists} finalists, {rejected} rejected"
            )

    finalist_like = [v for v in vendors if v.status in (VendorStatus.FINALIST, VendorStatus.EVALUATED)]
    if not finalist_like:
        lines.append("[ ] Hands-on scan no finalists yet")
    else:
        evaluated = sum(1 for v in finalist_like if v.status == VendorStatus.EVALUATED)
        marker = "x" if evaluated == len(finalist_like) else " "
        lines.append(f"[{marker}] Hands-on scan {evaluated}/{len(finalist_like)} finalists evaluated")

    lines.append("")
    lines.append(f"Next: {_next_action(taxonomy, vendors)}")
    return lines


def _next_action(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> str:
    if not taxonomy.criteria or taxonomy.validate_weights():
        return f"run dast-criteria -- {_skill('dast-criteria')['purpose']}"
    if not vendors:
        return f"run dast-discovery -- {_skill('dast-discovery')['purpose']}"
    if any(not _fully_scored(v, taxonomy) for v in vendors):
        return f"run dast-shortlist -- {_skill('dast-shortlist')['purpose']}"
    if any(v.status == VendorStatus.CANDIDATE for v in vendors):
        return f"run dast-shortlist -- {_skill('dast-shortlist')['purpose']}"
    finalist_like = [v for v in vendors if v.status in (VendorStatus.FINALIST, VendorStatus.EVALUATED)]
    if any(v.status == VendorStatus.FINALIST for v in finalist_like):
        return f"run dast-scan (or dast-onboard-tool if not CI-wired) -- {_skill('dast-scan')['purpose']}"
    return f"everything's current -- run dast-report -- {_skill('dast-report')['purpose']}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workflow.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS (all existing tests unaffected — this task only adds a new, unimported module)

- [ ] **Step 6: Commit**

```bash
git add core/workflow.py tests/test_workflow.py
git commit -m "Add static skill table and progress phase-detection logic"
```

---

### Task 2: Wire `workflow` command and extend `status` with progress output

**Files:**
- Modify: `core/cli.py` (add `workflow` command; extend `status_command`)
- Test: `tests/test_cli_status.py` (extend), create `tests/test_cli_workflow.py`

**Interfaces:**
- Consumes: `SKILLS`, `phase_report` from `core.workflow` (Task 1, already built and tested).
- Produces: nothing consumed by another task — this is the plan's final deliverable.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_workflow.py`:

```python
from typer.testing import CliRunner

from core.cli import app
from core.workflow import SKILLS

runner = CliRunner()


def test_workflow_command_lists_all_six_skills():
    result = runner.invoke(app, ["workflow"])
    assert result.exit_code == 0, result.output
    for skill in SKILLS:
        assert skill["name"] in result.output
        assert skill["purpose"] in result.output
```

Add to `tests/test_cli_status.py` (after the existing two tests):

```python
def test_status_command_appends_progress_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "Progress:" in result.output
    assert "[ ] Criteria      not started" in result.output
    assert "Next: run dast-criteria --" in result.output


def test_status_command_existing_gap_report_output_unchanged(tmp_path, monkeypatch):
    # Regression guard: dast-shortlist and dast-report depend on this exact
    # wording. This plan must never change it, only append after it.
    monkeypatch.chdir(tmp_path)
    runner.invoke(
        app,
        [
            "criteria", "add-criterion",
            "--id", "c1", "--category", "Coverage", "--name", "n",
            "--description", "d", "--weight", "100", "--rubric", "r",
        ],
    )
    runner.invoke(app, ["candidate", "add", "--id", "v1", "--name", "Vendor One", "--source", "discovered"])
    result = runner.invoke(app, ["status"])
    assert "v1: missing scores for c1" in result.output
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_cli_workflow.py tests/test_cli_status.py -v`
Expected: FAIL — `workflow` is not a registered command; `status` output doesn't yet contain "Progress:".

- [ ] **Step 3: Add the `workflow` command and extend `status_command`**

In `core/cli.py`, add `phase_report` and `SKILLS` to the imports (currently `from .status import gap_report` is the only status-related import — add a new import line directly after it):

```python
from .status import gap_report
from .workflow import SKILLS, phase_report
```

The current `status_command` (at `core/cli.py:346-354`) reads:

```python
@app.command("status")
def status_command() -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = storage.list_vendors(CANDIDATES_DIR)
    messages = gap_report(taxonomy, vendors)
    if not messages:
        typer.echo("no gaps found")
    for message in messages:
        typer.echo(message)
```

Change it to (appending the new section, nothing above this point changes):

```python
@app.command("status")
def status_command() -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = storage.list_vendors(CANDIDATES_DIR)
    messages = gap_report(taxonomy, vendors)
    if not messages:
        typer.echo("no gaps found")
    for message in messages:
        typer.echo(message)
    for line in phase_report(taxonomy, vendors):
        typer.echo(line)
```

Add a new `workflow` command directly after `status_command`:

```python
@app.command("workflow")
def workflow_command() -> None:
    for skill in SKILLS:
        typer.echo(skill["name"])
        typer.echo(f"  purpose: {skill['purpose']}")
        typer.echo(f"  reads:   {skill['reads']}")
        typer.echo(f"  writes:  {skill['writes']}")
        typer.echo("")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cli_workflow.py tests/test_cli_status.py -v`
Expected: PASS (all tests, including the two new ones and the two pre-existing ones)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS (all existing tests unaffected, including `dast-shortlist`'s and `dast-report`'s reliance on `status`'s pre-existing output, verified directly by the new regression test in Step 1)

- [ ] **Step 6: Update the README's CLI reference**

In `README.md`, the current top-level commands block reads:

```
dast-bench status   # reports vendors missing a score for any current criterion, and weight-total warnings
dast-bench render   # renders reports/scorecard-<id>.md, comparison-matrix.md, comparison-matrix.xlsx, dashboard.html
```

Replace it with:

```
dast-bench status   # reports vendors missing a score for any current criterion, and weight-total warnings, plus a Progress/Next summary of the whole pipeline
dast-bench render   # renders reports/scorecard-<id>.md, comparison-matrix.md, comparison-matrix.xlsx, dashboard.html
dast-bench workflow # static reference: what each of the six skills does, reads, and writes
```

- [ ] **Step 7: Commit**

```bash
git add core/cli.py tests/test_cli_workflow.py tests/test_cli_status.py README.md
git commit -m "Add workflow command and progress/next summary to status"
```

---

## Self-Review Notes

- **Spec coverage:** the design doc's Goals (static `workflow` command with zero data loading, `status`'s existing output strictly unchanged and appended-to, phase-by-phase Progress section, synthesized Next line pulling from the same static table, both commands remain pure reads), Non-Goals (no TUI, no report-done tracking, no renaming, no change to `dast-shortlist`/`dast-report`'s reliance on `status`), Architecture (the `core/workflow.py` module boundary, the two small `core/cli.py` additions), Data Flow (all phase-detection branches), and Testing (unit tests per phase-state transition, CLI-invocation tests, the explicit regression guard for unchanged gap-report wording) are all covered across Tasks 1-2.
- **Placeholder scan:** no TODO/TBD markers; every phase's wording and every branch of `_next_action` is fully written out, not described abstractly.
- **Type consistency:** `phase_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> list[str]` is defined once in Task 1 and consumed identically in Task 2 — no signature drift. `SKILLS`'s dict keys (`name`, `purpose`, `reads`, `writes`) are used identically in both `_next_action`'s lookups and `workflow_command`'s printing. `VendorStatus`/`VendorSource` enum members referenced (`CANDIDATE`, `FINALIST`, `REJECTED`, `EVALUATED`, `SEEDED`, `DISCOVERED`) all match `core/models.py`'s actual definitions exactly — no invented values.
