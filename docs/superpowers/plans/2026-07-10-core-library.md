# DAST Eval Core Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python/Pydantic core data layer and CLI (`dast_eval` package, `core/` module) described in `docs/superpowers/specs/2026-07-10-dast-eval-phase1-design.md` — the YAML-backed SSoT, validation, and rendering (Markdown/XLSX/HTML) that every Claude Code skill will call via Bash. This plan does not build the Claude Code skills themselves (that is a separate follow-on plan, since the skills depend on this CLI existing and are not unit-testable the same way).

**Architecture:** A single installable Python package (`core`) with Pydantic v2 models (`core/models.py`), a YAML load/save layer (`core/storage.py`), a Typer-based CLI (`core/cli.py`) exposing `criteria`, `candidate`, `handson`, `status`, and `render` commands, and a `core/render/` subpackage producing Markdown, XLSX, and self-contained HTML from the same in-memory data. All CLI mutations go through this package — nothing hand-edits the YAML files directly.

**Tech Stack:** Python 3.11+, Pydantic 2.x, PyYAML, Typer, openpyxl, pytest.

## Global Constraints

- Python >=3.11.
- Dependencies: `pydantic>=2.5`, `pyyaml>=6.0`, `typer>=0.12`, `openpyxl>=3.1`; dev dependency `pytest>=8`.
- Package name is exactly `core` (per the spec's file layout); CLI entry point is `dast-eval`.
- All CLI options use explicit `--flag value` form (no positional arguments) so they are unambiguous when called by an LLM-driven skill.
- YAML files are the single source of truth; every value round-trips losslessly through the corresponding Pydantic model.
- No placeholder/TODO code — every function is fully implemented in the task that introduces it.
- Every task's tests must pass before moving to the next task; earlier tasks' tests must keep passing (no regressions).

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `core/__init__.py`
- Create: `core/render/__init__.py`
- Create: `data/candidates/.gitkeep`
- Create: `reports/.gitkeep`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: an installable `core` package (empty) and a working pytest setup that later tasks build on.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "dast-eval-core"
version = "0.1.0"
description = "Core data layer and CLI for DAST tool evaluation workflow"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.5",
    "pyyaml>=6.0",
    "typer>=0.12",
    "openpyxl>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
dast-eval = "core.cli:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["core*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.egg-info/
.venv/
reports/*
!reports/.gitkeep
```

- [ ] **Step 3: Create package skeleton and data directories**

Create `core/__init__.py` (empty file), `core/render/__init__.py` (empty file), `data/candidates/.gitkeep` (empty file), `reports/.gitkeep` (empty file).

- [ ] **Step 4: Write the failing smoke test**

```python
# tests/test_smoke.py
def test_core_package_importable():
    import core

    assert core is not None
```

- [ ] **Step 5: Install the package and verify the test fails for the right reason first**

Run: `pip install -e ".[dev]"`
Expected: install succeeds.

Run: `pytest tests/test_smoke.py -v`
Expected: at this point it should actually PASS already, since `core/__init__.py` was created in Step 3 — this confirms the install and package layout are wired correctly. If it fails with `ModuleNotFoundError: No module named 'core'`, re-check `[tool.setuptools.packages.find]` in `pyproject.toml` and re-run `pip install -e ".[dev]"`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore core/__init__.py core/render/__init__.py data/candidates/.gitkeep reports/.gitkeep tests/test_smoke.py
git commit -m "Scaffold dast-eval-core package and test setup"
```

---

### Task 2: Domain models

**Files:**
- Create: `core/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces (used by every later task): `Criterion`, `CriteriaTaxonomy` (with `.criteria: list[Criterion]`, `.weight_total() -> float`, `.validate_weights(tolerance: float = 0.01) -> list[str]`, `.get(criterion_id: str) -> Criterion | None`), `VendorSource` (enum: `SEEDED="seeded"`, `DISCOVERED="discovered"`), `VendorStatus` (enum: `CANDIDATE="candidate"`, `FINALIST="finalist"`, `REJECTED="rejected"`, `EVALUATED="evaluated"`), `Confidence` (enum: `PAPER="paper"`, `HANDS_ON="hands-on"`), `ScoreEntry`, `Observation`, `HandsOnResult`, `Vendor` (with `.scores`, `.hands_on_results`, `.observations`, `.score_for(criterion_id: str) -> ScoreEntry | None`), `BenchmarkVulnerability`, `Benchmark`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_models.py
import pytest

from core.models import (
    Benchmark,
    BenchmarkVulnerability,
    Confidence,
    Criterion,
    CriteriaTaxonomy,
    HandsOnResult,
    Observation,
    ScoreEntry,
    Vendor,
    VendorSource,
    VendorStatus,
)


def test_criterion_requires_weight_in_range():
    Criterion(id="c1", category="Coverage", name="API Coverage", description="d", weight=20, rubric="r")
    with pytest.raises(ValueError):
        Criterion(id="c1", category="Coverage", name="API Coverage", description="d", weight=150, rubric="r")


def test_taxonomy_validate_weights_flags_non_100_total():
    taxonomy = CriteriaTaxonomy(
        criteria=[Criterion(id="c1", category="Coverage", name="n", description="d", weight=40, rubric="r")]
    )
    issues = taxonomy.validate_weights()
    assert len(issues) == 1
    assert "40.00" in issues[0]


def test_taxonomy_validate_weights_passes_at_100():
    taxonomy = CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="n", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="n2", description="d", weight=40, rubric="r"),
        ]
    )
    assert taxonomy.validate_weights() == []


def test_taxonomy_get_returns_criterion_by_id():
    c1 = Criterion(id="c1", category="Coverage", name="n", description="d", weight=100, rubric="r")
    taxonomy = CriteriaTaxonomy(criteria=[c1])
    assert taxonomy.get("c1") is c1
    assert taxonomy.get("missing") is None


def test_score_entry_requires_score_in_1_to_5_range():
    ScoreEntry(criterion_id="c1", score=3, evidence="e", confidence=Confidence.PAPER)
    with pytest.raises(ValueError):
        ScoreEntry(criterion_id="c1", score=6, evidence="e", confidence=Confidence.PAPER)


def test_vendor_score_for_returns_latest_matching_entry():
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=2, evidence="first", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4, evidence="second", confidence=Confidence.HANDS_ON))
    latest = vendor.score_for("c1")
    assert latest.evidence == "second"
    assert vendor.score_for("missing") is None


def test_vendor_defaults_to_candidate_status():
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.SEEDED)
    assert vendor.status == VendorStatus.CANDIDATE


def test_observation_and_hands_on_result_construct_cleanly():
    Observation(context="juice-shop crawl", note="UI felt sluggish", tags=["ux-friction"])
    HandsOnResult(
        test_id="scan-1", description="ZAP baseline scan", automated=True, benchmark_id="juice-shop", outcome="ok"
    )


def test_benchmark_holds_known_vulnerabilities():
    bench = Benchmark(
        id="juice-shop",
        name="OWASP Juice Shop",
        target_type="spa",
        known_vulnerabilities=[BenchmarkVulnerability(id="v1", name="SQLi", severity="high")],
    )
    assert bench.known_vulnerabilities[0].id == "v1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.models'`.

- [ ] **Step 3: Implement `core/models.py`**

```python
# core/models.py
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class VendorSource(str, Enum):
    SEEDED = "seeded"
    DISCOVERED = "discovered"


class VendorStatus(str, Enum):
    CANDIDATE = "candidate"
    FINALIST = "finalist"
    REJECTED = "rejected"
    EVALUATED = "evaluated"


class Confidence(str, Enum):
    PAPER = "paper"
    HANDS_ON = "hands-on"


class Criterion(BaseModel):
    id: str
    category: str
    name: str
    description: str
    weight: float = Field(ge=0, le=100)
    rubric: str


class CriteriaTaxonomy(BaseModel):
    version: int = 1
    criteria: list[Criterion] = Field(default_factory=list)

    def weight_total(self) -> float:
        return sum(c.weight for c in self.criteria)

    def validate_weights(self, tolerance: float = 0.01) -> list[str]:
        total = self.weight_total()
        if abs(total - 100.0) > tolerance:
            return [f"criteria weights sum to {total:.2f}, expected 100.00"]
        return []

    def get(self, criterion_id: str) -> Criterion | None:
        return next((c for c in self.criteria if c.id == criterion_id), None)


class ScoreEntry(BaseModel):
    criterion_id: str
    score: float = Field(ge=1, le=5)
    evidence: str
    confidence: Confidence
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Observation(BaseModel):
    context: str
    note: str
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HandsOnResult(BaseModel):
    test_id: str
    description: str
    automated: bool
    benchmark_id: str | None = None
    outcome: str
    observations: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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


class BenchmarkVulnerability(BaseModel):
    id: str
    name: str
    severity: str


class Benchmark(BaseModel):
    id: str
    name: str
    target_type: str
    known_vulnerabilities: list[BenchmarkVulnerability] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "Add domain models for criteria, vendors, scores, and benchmarks"
```

---

### Task 3: YAML storage layer

**Files:**
- Create: `core/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `core.models.{CriteriaTaxonomy, Vendor, Benchmark}` (Task 2).
- Produces: `load_criteria(path: Path) -> CriteriaTaxonomy`, `save_criteria(taxonomy: CriteriaTaxonomy, path: Path) -> None`, `vendor_path(candidates_dir: Path, vendor_id: str) -> Path`, `load_vendor(path: Path) -> Vendor`, `save_vendor(vendor: Vendor, path: Path) -> None`, `list_vendors(candidates_dir: Path) -> list[Vendor]`, `load_benchmarks(path: Path) -> list[Benchmark]`, `save_benchmarks(benchmarks: list[Benchmark], path: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage.py
from core import storage
from core.models import (
    Benchmark,
    BenchmarkVulnerability,
    Criterion,
    CriteriaTaxonomy,
    Vendor,
    VendorSource,
)


def test_save_and_load_criteria_round_trips(tmp_path):
    path = tmp_path / "criteria.yaml"
    taxonomy = CriteriaTaxonomy(
        criteria=[Criterion(id="c1", category="Coverage", name="n", description="d", weight=100, rubric="r")]
    )
    storage.save_criteria(taxonomy, path)
    assert storage.load_criteria(path) == taxonomy


def test_load_criteria_returns_empty_taxonomy_when_missing(tmp_path):
    assert storage.load_criteria(tmp_path / "missing.yaml").criteria == []


def test_save_and_load_vendor_round_trips(tmp_path):
    candidates_dir = tmp_path / "candidates"
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.SEEDED)
    path = storage.vendor_path(candidates_dir, vendor.id)
    storage.save_vendor(vendor, path)
    assert storage.load_vendor(path) == vendor


def test_list_vendors_returns_all_saved_vendors_sorted(tmp_path):
    candidates_dir = tmp_path / "candidates"
    for vid in ["zeta", "alpha"]:
        storage.save_vendor(
            Vendor(id=vid, name=vid.title(), source=VendorSource.DISCOVERED),
            storage.vendor_path(candidates_dir, vid),
        )
    vendors = storage.list_vendors(candidates_dir)
    assert [v.id for v in vendors] == ["alpha", "zeta"]


def test_list_vendors_returns_empty_list_when_dir_missing(tmp_path):
    assert storage.list_vendors(tmp_path / "missing") == []


def test_save_and_load_benchmarks_round_trips(tmp_path):
    path = tmp_path / "benchmarks.yaml"
    benchmarks = [
        Benchmark(
            id="juice-shop",
            name="OWASP Juice Shop",
            target_type="spa",
            known_vulnerabilities=[BenchmarkVulnerability(id="v1", name="SQLi", severity="high")],
        )
    ]
    storage.save_benchmarks(benchmarks, path)
    assert storage.load_benchmarks(path) == benchmarks


def test_load_benchmarks_returns_empty_list_when_missing(tmp_path):
    assert storage.load_benchmarks(tmp_path / "missing.yaml") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.storage'`.

- [ ] **Step 3: Implement `core/storage.py`**

```python
# core/storage.py
from __future__ import annotations

from pathlib import Path

import yaml

from .models import Benchmark, CriteriaTaxonomy, Vendor


def load_criteria(path: Path) -> CriteriaTaxonomy:
    if not path.exists():
        return CriteriaTaxonomy()
    data = yaml.safe_load(path.read_text()) or {}
    return CriteriaTaxonomy.model_validate(data)


def save_criteria(taxonomy: CriteriaTaxonomy, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(taxonomy.model_dump(mode="json"), sort_keys=False))


def vendor_path(candidates_dir: Path, vendor_id: str) -> Path:
    return candidates_dir / f"{vendor_id}.yaml"


def load_vendor(path: Path) -> Vendor:
    data = yaml.safe_load(path.read_text()) or {}
    return Vendor.model_validate(data)


def save_vendor(vendor: Vendor, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(vendor.model_dump(mode="json"), sort_keys=False))


def list_vendors(candidates_dir: Path) -> list[Vendor]:
    if not candidates_dir.exists():
        return []
    return [load_vendor(p) for p in sorted(candidates_dir.glob("*.yaml"))]


def load_benchmarks(path: Path) -> list[Benchmark]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return [Benchmark.model_validate(b) for b in data.get("benchmarks", [])]


def save_benchmarks(benchmarks: list[Benchmark], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"benchmarks": [b.model_dump(mode="json") for b in benchmarks]}
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_storage.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add core/storage.py tests/test_storage.py
git commit -m "Add YAML storage layer for criteria, vendors, and benchmarks"
```

---

### Task 4: CLI — criteria commands

**Files:**
- Create: `core/cli.py`
- Test: `tests/test_cli_criteria.py`

**Interfaces:**
- Consumes: `core.storage.{load_criteria, save_criteria}`, `core.models.Criterion` (Tasks 2–3).
- Produces: module-level `app` (Typer app, the package's console-script target), `criteria_app` sub-app registered under `criteria`, constants `DATA_DIR = Path("data")`, `CRITERIA_PATH = DATA_DIR / "criteria.yaml"`, `CANDIDATES_DIR = DATA_DIR / "candidates"`, `BENCHMARKS_PATH = DATA_DIR / "benchmarks.yaml"`. Commands: `criteria add-criterion --id --category --name --description --weight --rubric`, `criteria set-weight --id --weight`, `criteria list`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_criteria.py
from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()

ADD_ARGS = [
    "criteria",
    "add-criterion",
    "--id",
    "c1",
    "--category",
    "Coverage",
    "--name",
    "API Coverage",
    "--description",
    "Detects vulnerabilities in REST/GraphQL APIs",
    "--weight",
    "20",
    "--rubric",
    "5 = full OpenAPI-driven scanning",
]


def test_add_criterion_then_list_shows_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "c1" in result.output
    assert "API Coverage" in result.output


def test_add_criterion_rejects_duplicate_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_set_weight_updates_existing_criterion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "set-weight", "--id", "c1", "--weight", "30"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["criteria", "list"])
    assert "weight=30" in result.output


def test_set_weight_errors_on_unknown_criterion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["criteria", "set-weight", "--id", "missing", "--weight", "10"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_list_warns_when_weights_do_not_sum_to_100(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "list"])
    assert "warning" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_criteria.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.cli'`.

- [ ] **Step 3: Implement `core/cli.py`**

```python
# core/cli.py
from __future__ import annotations

from pathlib import Path

import typer

from . import storage
from .models import Criterion

app = typer.Typer()
criteria_app = typer.Typer()
app.add_typer(criteria_app, name="criteria")

DATA_DIR = Path("data")
CRITERIA_PATH = DATA_DIR / "criteria.yaml"
CANDIDATES_DIR = DATA_DIR / "candidates"
BENCHMARKS_PATH = DATA_DIR / "benchmarks.yaml"


@criteria_app.command("add-criterion")
def add_criterion(
    id: str = typer.Option(...),
    category: str = typer.Option(...),
    name: str = typer.Option(...),
    description: str = typer.Option(...),
    weight: float = typer.Option(...),
    rubric: str = typer.Option(...),
) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    if taxonomy.get(id):
        typer.echo(f"error: criterion '{id}' already exists")
        raise typer.Exit(code=1)
    taxonomy.criteria.append(
        Criterion(id=id, category=category, name=name, description=description, weight=weight, rubric=rubric)
    )
    storage.save_criteria(taxonomy, CRITERIA_PATH)
    typer.echo(f"added criterion '{id}'")


@criteria_app.command("set-weight")
def set_weight(id: str = typer.Option(...), weight: float = typer.Option(...)) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    criterion = taxonomy.get(id)
    if not criterion:
        typer.echo(f"error: criterion '{id}' not found")
        raise typer.Exit(code=1)
    criterion.weight = weight
    storage.save_criteria(taxonomy, CRITERIA_PATH)
    typer.echo(f"set weight of '{id}' to {weight}")


@criteria_app.command("list")
def list_criteria() -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    for c in taxonomy.criteria:
        typer.echo(f"{c.id}\t{c.category}\t{c.name}\tweight={c.weight:g}")
    for issue in taxonomy.validate_weights():
        typer.echo(f"warning: {issue}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_criteria.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add core/cli.py tests/test_cli_criteria.py
git commit -m "Add CLI criteria commands"
```

---

### Task 5: CLI — candidate commands

**Files:**
- Modify: `core/cli.py` (append)
- Test: `tests/test_cli_candidate.py`

**Interfaces:**
- Consumes: `core.storage.{vendor_path, load_vendor, save_vendor, list_vendors}`, `core.models.{Vendor, VendorSource, VendorStatus, ScoreEntry, Confidence}` (Tasks 2–4), and the module-level `app`, `CRITERIA_PATH`, `CANDIDATES_DIR` from Task 4.
- Produces: `candidate_app` registered under `candidate`, helper `_load_vendor_or_exit(vendor_id: str) -> Vendor` (reused by Task 6). Commands: `candidate add --id --name --source --website --notes`, `candidate set-status --id --status`, `candidate record-score --vendor-id --criterion-id --score --evidence --confidence`, `candidate list`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_candidate.py
from typer.testing import CliRunner

from core import storage
from core.cli import app

runner = CliRunner()


def _add_vendor(monkeypatch, tmp_path, vendor_id="v1", source="discovered"):
    monkeypatch.chdir(tmp_path)
    return runner.invoke(
        app, ["candidate", "add", "--id", vendor_id, "--name", "Vendor One", "--source", source]
    )


def test_add_candidate_then_list_shows_it(tmp_path, monkeypatch):
    result = _add_vendor(monkeypatch, tmp_path)
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["candidate", "list"])
    assert "v1" in result.output
    assert "discovered" in result.output


def test_add_candidate_rejects_duplicate_id(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = _add_vendor(monkeypatch, tmp_path)
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_set_status_updates_vendor(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(app, ["candidate", "set-status", "--id", "v1", "--status", "finalist"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["candidate", "list"])
    assert "finalist" in result.output


def test_set_status_errors_on_unknown_vendor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["candidate", "set-status", "--id", "missing", "--status", "finalist"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_record_score_requires_known_criterion(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    assert result.exit_code != 0
    assert "criterion" in result.output.lower()


def test_record_score_stores_score_against_known_criterion(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    runner.invoke(
        app,
        [
            "criteria", "add-criterion",
            "--id", "c1", "--category", "Coverage", "--name", "n",
            "--description", "d", "--weight", "100", "--rubric", "r",
        ],
    )
    result = runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.score_for("c1").score == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_candidate.py -v`
Expected: FAIL — `No such command 'candidate'`.

- [ ] **Step 3: Append to `core/cli.py`**

Update the imports at the top of `core/cli.py`:

```python
from . import storage
from .models import Confidence, Criterion, ScoreEntry, Vendor, VendorSource, VendorStatus
```

Add after the `criteria_app` block:

```python
candidate_app = typer.Typer()
app.add_typer(candidate_app, name="candidate")


def _load_vendor_or_exit(vendor_id: str) -> Vendor:
    path = storage.vendor_path(CANDIDATES_DIR, vendor_id)
    if not path.exists():
        typer.echo(f"error: vendor '{vendor_id}' not found")
        raise typer.Exit(code=1)
    return storage.load_vendor(path)


@candidate_app.command("add")
def add_candidate(
    id: str = typer.Option(...),
    name: str = typer.Option(...),
    source: VendorSource = typer.Option(...),
    website: str = typer.Option(""),
    notes: str = typer.Option(""),
) -> None:
    path = storage.vendor_path(CANDIDATES_DIR, id)
    if path.exists():
        typer.echo(f"error: vendor '{id}' already exists")
        raise typer.Exit(code=1)
    vendor = Vendor(id=id, name=name, source=source, website=website, notes=notes)
    storage.save_vendor(vendor, path)
    typer.echo(f"added vendor '{id}'")


@candidate_app.command("set-status")
def set_status(id: str = typer.Option(...), status: VendorStatus = typer.Option(...)) -> None:
    vendor = _load_vendor_or_exit(id)
    vendor.status = status
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, id))
    typer.echo(f"set status of '{id}' to {status.value}")


@candidate_app.command("record-score")
def record_score(
    vendor_id: str = typer.Option(...),
    criterion_id: str = typer.Option(...),
    score: float = typer.Option(...),
    evidence: str = typer.Option(...),
    confidence: Confidence = typer.Option(...),
) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    if not taxonomy.get(criterion_id):
        typer.echo(f"error: criterion '{criterion_id}' not found in taxonomy")
        raise typer.Exit(code=1)
    vendor = _load_vendor_or_exit(vendor_id)
    vendor.scores.append(
        ScoreEntry(criterion_id=criterion_id, score=score, evidence=evidence, confidence=confidence)
    )
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, vendor_id))
    typer.echo(f"recorded score for '{vendor_id}' on '{criterion_id}'")


@candidate_app.command("list")
def list_candidates() -> None:
    for v in storage.list_vendors(CANDIDATES_DIR):
        typer.echo(f"{v.id}\t{v.name}\t{v.source.value}\t{v.status.value}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_candidate.py tests/test_cli_criteria.py -v`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add core/cli.py tests/test_cli_candidate.py
git commit -m "Add CLI candidate commands"
```

---

### Task 6: CLI — hands-on commands

**Files:**
- Modify: `core/cli.py` (append)
- Test: `tests/test_cli_handson.py`

**Interfaces:**
- Consumes: `_load_vendor_or_exit`, `storage.{load_benchmarks, save_vendor, vendor_path}`, `models.{Observation, HandsOnResult}` (Tasks 2–5).
- Produces: `handson_app` registered under `handson`. Commands: `handson log-observation --vendor-id --context --note --tags`, `handson ingest-scan-result --vendor-id --benchmark-id --file --test-id --description --automated/--no-automated`. Findings file format consumed by `ingest-scan-result`: a JSON array of objects, each with a required `vuln_id` string and optional `severity`/`description` strings.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_handson.py
import json

from typer.testing import CliRunner

from core import storage
from core.cli import app
from core.models import Benchmark, BenchmarkVulnerability

runner = CliRunner()


def _setup_vendor_and_benchmark(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["candidate", "add", "--id", "v1", "--name", "Vendor One", "--source", "discovered"])
    benchmarks_path = tmp_path / "data" / "benchmarks.yaml"
    storage.save_benchmarks(
        [
            Benchmark(
                id="juice-shop",
                name="OWASP Juice Shop",
                target_type="spa",
                known_vulnerabilities=[BenchmarkVulnerability(id="sqli-1", name="SQLi", severity="high")],
            )
        ],
        benchmarks_path,
    )


def test_log_observation_appends_to_vendor(tmp_path, monkeypatch):
    _setup_vendor_and_benchmark(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "handson", "log-observation",
            "--vendor-id", "v1", "--context", "juice-shop crawl",
            "--note", "UI felt sluggish", "--tags", "ux-friction,setup-cost",
        ],
    )
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.observations[0].note == "UI felt sluggish"
    assert vendor.observations[0].tags == ["ux-friction", "setup-cost"]


def test_ingest_scan_result_computes_detection_rate(tmp_path, monkeypatch):
    _setup_vendor_and_benchmark(monkeypatch, tmp_path)
    findings_file = tmp_path / "findings.json"
    findings_file.write_text(
        json.dumps([{"vuln_id": "sqli-1", "severity": "high"}, {"vuln_id": "not-a-real-vuln", "severity": "low"}])
    )
    result = runner.invoke(
        app,
        [
            "handson", "ingest-scan-result",
            "--vendor-id", "v1", "--benchmark-id", "juice-shop",
            "--file", str(findings_file), "--test-id", "scan-1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "1/1" in result.output
    assert "1 false positive" in result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.hands_on_results[0].benchmark_id == "juice-shop"


def test_ingest_scan_result_errors_on_unknown_benchmark(tmp_path, monkeypatch):
    _setup_vendor_and_benchmark(monkeypatch, tmp_path)
    findings_file = tmp_path / "findings.json"
    findings_file.write_text("[]")
    result = runner.invoke(
        app,
        [
            "handson", "ingest-scan-result",
            "--vendor-id", "v1", "--benchmark-id", "missing-benchmark",
            "--file", str(findings_file), "--test-id", "scan-1",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_handson.py -v`
Expected: FAIL — `No such command 'handson'`.

- [ ] **Step 3: Append to `core/cli.py`**

Add `import json` and `from pathlib import Path` are already imported; extend the model import line:

```python
from .models import Confidence, Criterion, HandsOnResult, Observation, ScoreEntry, Vendor, VendorSource, VendorStatus
```

Add `import json` near the top with the other imports.

Add after the candidate commands block:

```python
handson_app = typer.Typer()
app.add_typer(handson_app, name="handson")


@handson_app.command("log-observation")
def log_observation(
    vendor_id: str = typer.Option(...),
    context: str = typer.Option(...),
    note: str = typer.Option(...),
    tags: str = typer.Option(""),
) -> None:
    vendor = _load_vendor_or_exit(vendor_id)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    vendor.observations.append(Observation(context=context, note=note, tags=tag_list))
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, vendor_id))
    typer.echo(f"logged observation for '{vendor_id}'")


@handson_app.command("ingest-scan-result")
def ingest_scan_result(
    vendor_id: str = typer.Option(...),
    benchmark_id: str = typer.Option(...),
    file: Path = typer.Option(...),
    test_id: str = typer.Option(...),
    description: str = typer.Option(""),
    automated: bool = typer.Option(True),
) -> None:
    benchmarks = storage.load_benchmarks(BENCHMARKS_PATH)
    bench = next((b for b in benchmarks if b.id == benchmark_id), None)
    if not bench:
        typer.echo(f"error: benchmark '{benchmark_id}' not found")
        raise typer.Exit(code=1)
    vendor = _load_vendor_or_exit(vendor_id)
    findings = json.loads(file.read_text())
    known_ids = {vuln.id for vuln in bench.known_vulnerabilities}
    found_ids = {f["vuln_id"] for f in findings if "vuln_id" in f}
    detected = found_ids & known_ids
    false_positives = [f for f in findings if f.get("vuln_id") not in known_ids]
    outcome = (
        f"detected {len(detected)}/{len(known_ids)} known vulnerabilities, "
        f"{len(false_positives)} false positive(s)"
    )
    vendor.hands_on_results.append(
        HandsOnResult(
            test_id=test_id,
            description=description or f"scan against {benchmark_id}",
            automated=automated,
            benchmark_id=benchmark_id,
            outcome=outcome,
            observations=f"findings file: {file.name}",
        )
    )
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, vendor_id))
    typer.echo(outcome)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_handson.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/cli.py tests/test_cli_handson.py
git commit -m "Add CLI hands-on commands for observation logging and scan ingestion"
```

---

### Task 7: Status / gap detection

**Files:**
- Create: `core/status.py`
- Modify: `core/cli.py` (append)
- Test: `tests/test_status.py`
- Test: `tests/test_cli_status.py`

**Interfaces:**
- Consumes: `core.models.{CriteriaTaxonomy, Vendor}` (Task 2).
- Produces: `gap_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> list[str]` (reused by Task 11's `render` command), CLI command `status`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_status.py
from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.status import gap_report


def test_gap_report_flags_missing_scores():
    taxonomy = CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="n1", description="d", weight=50, rubric="r"),
            Criterion(id="c2", category="Coverage", name="n2", description="d", weight=50, rubric="r"),
        ]
    )
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=3, evidence="e", confidence=Confidence.PAPER))
    messages = gap_report(taxonomy, [vendor])
    assert any("c2" in m and "v1" in m for m in messages)


def test_gap_report_flags_weight_total_off_100():
    taxonomy = CriteriaTaxonomy(
        criteria=[Criterion(id="c1", category="Coverage", name="n1", description="d", weight=50, rubric="r")]
    )
    messages = gap_report(taxonomy, [])
    assert any("50.00" in m for m in messages)


def test_gap_report_empty_when_fully_scored_and_weights_valid():
    taxonomy = CriteriaTaxonomy(
        criteria=[Criterion(id="c1", category="Coverage", name="n1", description="d", weight=100, rubric="r")]
    )
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=3, evidence="e", confidence=Confidence.PAPER))
    assert gap_report(taxonomy, [vendor]) == []
```

```python
# tests/test_cli_status.py
from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()


def test_status_command_reports_no_gaps_on_clean_setup(tmp_path, monkeypatch):
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
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "no gaps found" in result.output


def test_status_command_reports_missing_score(tmp_path, monkeypatch):
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
    assert "missing scores" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_status.py tests/test_cli_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.status'` and `No such command 'status'`.

- [ ] **Step 3: Implement `core/status.py`**

```python
# core/status.py
from __future__ import annotations

from .models import CriteriaTaxonomy, Vendor


def gap_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> list[str]:
    messages = [f"warning: {issue}" for issue in taxonomy.validate_weights()]
    for vendor in vendors:
        scored_ids = {s.criterion_id for s in vendor.scores}
        missing = [c.id for c in taxonomy.criteria if c.id not in scored_ids]
        if missing:
            messages.append(f"{vendor.id}: missing scores for {', '.join(missing)}")
    return messages
```

Append to `core/cli.py` (add `from .status import gap_report` to the imports, and add the command after the `handson_app` block):

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_status.py tests/test_cli_status.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add core/status.py core/cli.py tests/test_status.py tests/test_cli_status.py
git commit -m "Add gap-detection status reporting"
```

---

### Task 8: Render — Markdown

**Files:**
- Create: `core/render/markdown.py`
- Test: `tests/test_render_markdown.py`

**Interfaces:**
- Consumes: `core.models.{CriteriaTaxonomy, Vendor}` (Task 2).
- Produces (reused by Tasks 9, 10, 11): `weighted_score(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> float`, `render_scorecard(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> str`, `render_comparison_matrix(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> str`, `write_markdown(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_dir: Path) -> None` (writes `scorecard-<id>.md` per vendor and `comparison-matrix.md`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_render_markdown.py
from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.render.markdown import render_comparison_matrix, render_scorecard, weighted_score, write_markdown


def _sample_taxonomy() -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="API Coverage", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="Noise Reduction", description="d", weight=40, rubric="r"),
        ]
    )


def _sample_vendor() -> Vendor:
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2, evidence="trial", confidence=Confidence.HANDS_ON))
    return vendor


def test_weighted_score_combines_weights_and_scores():
    assert weighted_score(_sample_taxonomy(), _sample_vendor()) == 4 * 0.6 + 2 * 0.4


def test_weighted_score_ignores_unscored_criteria():
    taxonomy = _sample_taxonomy()
    vendor = Vendor(id="v2", name="Vendor Two", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=5, evidence="docs", confidence=Confidence.PAPER))
    assert weighted_score(taxonomy, vendor) == 5 * 0.6


def test_render_scorecard_includes_criterion_names_and_scores():
    scorecard = render_scorecard(_sample_taxonomy(), _sample_vendor())
    assert "API Coverage" in scorecard
    assert "Noise Reduction" in scorecard
    assert "Weighted score" in scorecard


def test_render_comparison_matrix_includes_all_vendors():
    matrix = render_comparison_matrix(_sample_taxonomy(), [_sample_vendor()])
    assert "Vendor One" in matrix
    assert "Weighted Total" in matrix


def test_write_markdown_creates_scorecard_and_matrix_files(tmp_path):
    write_markdown(_sample_taxonomy(), [_sample_vendor()], tmp_path)
    assert (tmp_path / "scorecard-v1.md").exists()
    assert (tmp_path / "comparison-matrix.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_render_markdown.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.render.markdown'`.

- [ ] **Step 3: Implement `core/render/markdown.py`**

```python
# core/render/markdown.py
from __future__ import annotations

from pathlib import Path

from ..models import CriteriaTaxonomy, Vendor


def weighted_score(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> float:
    total = 0.0
    for criterion in taxonomy.criteria:
        entry = vendor.score_for(criterion.id)
        if entry:
            total += entry.score * (criterion.weight / 100.0)
    return total


def render_scorecard(taxonomy: CriteriaTaxonomy, vendor: Vendor) -> str:
    lines = [f"# {vendor.name} Scorecard", "", f"Status: {vendor.status.value}", ""]
    lines.append("| Criterion | Category | Score | Evidence | Confidence |")
    lines.append("|---|---|---|---|---|")
    for criterion in taxonomy.criteria:
        entry = vendor.score_for(criterion.id)
        if entry:
            lines.append(
                f"| {criterion.name} | {criterion.category} | {entry.score:g} | {entry.evidence} | "
                f"{entry.confidence.value} |"
            )
        else:
            lines.append(f"| {criterion.name} | {criterion.category} | _unscored_ | | |")
    lines.append("")
    lines.append(f"**Weighted score: {weighted_score(taxonomy, vendor):.2f} / 5.00**")
    return "\n".join(lines)


def render_comparison_matrix(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> str:
    lines = ["# DAST Tool Comparison Matrix", ""]
    header = "| Criterion | " + " | ".join(v.name for v in vendors) + " |"
    separator = "|---|" + "---|" * len(vendors)
    lines += [header, separator]
    for criterion in taxonomy.criteria:
        row = [criterion.name]
        for v in vendors:
            entry = v.score_for(criterion.id)
            row.append(f"{entry.score:g}" if entry else "-")
        lines.append("| " + " | ".join(row) + " |")
    totals = ["**Weighted Total**"] + [f"{weighted_score(taxonomy, v):.2f}" for v in vendors]
    lines.append("| " + " | ".join(totals) + " |")
    return "\n".join(lines)


def write_markdown(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for v in vendors:
        (out_dir / f"scorecard-{v.id}.md").write_text(render_scorecard(taxonomy, v))
    (out_dir / "comparison-matrix.md").write_text(render_comparison_matrix(taxonomy, vendors))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_render_markdown.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add core/render/markdown.py tests/test_render_markdown.py
git commit -m "Add Markdown rendering for scorecards and comparison matrix"
```

---

### Task 9: Render — XLSX

**Files:**
- Create: `core/render/xlsx.py`
- Test: `tests/test_render_xlsx.py`

**Interfaces:**
- Consumes: `core.render.markdown.weighted_score` (Task 8), `core.models.{CriteriaTaxonomy, Vendor}` (Task 2).
- Produces (reused by Task 11): `write_xlsx(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render_xlsx.py
from openpyxl import load_workbook

from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.render.xlsx import write_xlsx


def _sample_taxonomy() -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="API Coverage", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="Noise Reduction", description="d", weight=40, rubric="r"),
        ]
    )


def _sample_vendor() -> Vendor:
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2, evidence="trial", confidence=Confidence.HANDS_ON))
    return vendor


def test_write_xlsx_creates_sheet_with_header_and_vendor_column(tmp_path):
    out_path = tmp_path / "comparison-matrix.xlsx"
    write_xlsx(_sample_taxonomy(), [_sample_vendor()], out_path)
    wb = load_workbook(out_path)
    ws = wb["Comparison"]
    header = [cell.value for cell in ws[1]]
    assert header == ["Criterion", "Category", "Weight", "Vendor One"]
    assert ws.cell(row=2, column=4).value == 4
    last_row = [cell.value for cell in ws[ws.max_row]]
    assert last_row[0] == "Weighted Total"
    assert last_row[3] == 4 * 0.6 + 2 * 0.4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render_xlsx.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.render.xlsx'`.

- [ ] **Step 3: Implement `core/render/xlsx.py`**

```python
# core/render/xlsx.py
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from ..models import CriteriaTaxonomy, Vendor
from .markdown import weighted_score


def write_xlsx(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Comparison"
    ws.append(["Criterion", "Category", "Weight"] + [v.name for v in vendors])
    for criterion in taxonomy.criteria:
        row = [criterion.name, criterion.category, criterion.weight]
        for v in vendors:
            entry = v.score_for(criterion.id)
            row.append(entry.score if entry else None)
        ws.append(row)
    ws.append(["Weighted Total", "", ""] + [round(weighted_score(taxonomy, v), 2) for v in vendors])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_render_xlsx.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add core/render/xlsx.py tests/test_render_xlsx.py
git commit -m "Add XLSX rendering for the comparison matrix"
```

---

### Task 10: Render — HTML

**Files:**
- Create: `core/render/html.py`
- Test: `tests/test_render_html.py`

**Interfaces:**
- Consumes: `core.render.markdown.weighted_score` (Task 8), `core.models.{CriteriaTaxonomy, Vendor}` (Task 2).
- Produces (reused by Task 11): `write_html(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None`. Output is a single self-contained HTML file (inline CSS/JS, no external requests) with a client-side sortable comparison table.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render_html.py
from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.render.html import write_html


def _sample_taxonomy() -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="API Coverage", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="Noise Reduction", description="d", weight=40, rubric="r"),
        ]
    )


def _sample_vendor() -> Vendor:
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2, evidence="trial", confidence=Confidence.HANDS_ON))
    return vendor


def test_write_html_includes_vendor_and_criterion_names(tmp_path):
    out_path = tmp_path / "dashboard.html"
    write_html(_sample_taxonomy(), [_sample_vendor()], out_path)
    html = out_path.read_text()
    assert "Vendor One" in html
    assert "API Coverage" in html
    assert "sortTable" in html
    assert "<script" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render_html.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.render.html'`.

- [ ] **Step 3: Implement `core/render/html.py`**

```python
# core/render/html.py
from __future__ import annotations

from pathlib import Path

from ..models import CriteriaTaxonomy, Vendor
from .markdown import weighted_score

_SORT_SCRIPT = """
<script>
function sortTable(colIndex) {
  const table = document.querySelector('table');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const asc = table.dataset.sortCol == colIndex && table.dataset.sortDir !== 'asc';
  rows.sort((a, b) => {
    const av = a.children[colIndex].textContent.trim();
    const bv = b.children[colIndex].textContent.trim();
    const an = parseFloat(av);
    const bn = parseFloat(bv);
    const cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
    return asc ? cmp : -cmp;
  });
  rows.forEach((r) => tbody.appendChild(r));
  table.dataset.sortCol = colIndex;
  table.dataset.sortDir = asc ? 'asc' : 'desc';
}
</script>
"""


def write_html(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None:
    header_cells = ["Criterion", "Category"] + [v.name for v in vendors]
    header_html = "".join(f'<th onclick="sortTable({i})">{name}</th>' for i, name in enumerate(header_cells))

    rows = []
    for criterion in taxonomy.criteria:
        cells = "".join(
            f"<td>{(entry.score if (entry := v.score_for(criterion.id)) else '-')}</td>" for v in vendors
        )
        rows.append(f"<tr><td>{criterion.name}</td><td>{criterion.category}</td>{cells}</tr>")

    totals = "".join(f"<td>{weighted_score(taxonomy, v):.2f}</td>" for v in vendors)

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DAST Comparison Matrix</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
th {{ cursor: pointer; }}
tfoot td {{ font-weight: bold; }}
</style>
</head>
<body>
<h1>DAST Tool Comparison Matrix</h1>
<table>
<thead><tr>{header_html}</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
<tfoot><tr><td>Weighted Total</td><td></td>{totals}</tr></tfoot>
</table>
{_SORT_SCRIPT}
</body>
</html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_render_html.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add core/render/html.py tests/test_render_html.py
git commit -m "Add self-contained HTML rendering for the comparison dashboard"
```

---

### Task 11: CLI — render command

**Files:**
- Modify: `core/cli.py` (append)
- Test: `tests/test_cli_render.py`

**Interfaces:**
- Consumes: `core.render.markdown.write_markdown`, `core.render.xlsx.write_xlsx`, `core.render.html.write_html` (Tasks 8–10), `core.status.gap_report` (Task 7).
- Produces: CLI command `render`, constant `REPORTS_DIR = Path("reports")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_render.py
from pathlib import Path

from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()


def _seed_scored_vendor(tmp_path, monkeypatch):
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


def test_render_command_writes_all_report_formats(tmp_path, monkeypatch):
    _seed_scored_vendor(tmp_path, monkeypatch)
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    result = runner.invoke(app, ["render"])
    assert result.exit_code == 0, result.output
    assert (Path("reports") / "scorecard-v1.md").exists()
    assert (Path("reports") / "comparison-matrix.md").exists()
    assert (Path("reports") / "comparison-matrix.xlsx").exists()
    assert (Path("reports") / "dashboard.html").exists()


def test_render_command_surfaces_gap_warnings(tmp_path, monkeypatch):
    _seed_scored_vendor(tmp_path, monkeypatch)
    result = runner.invoke(app, ["render"])
    assert "missing scores" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_render.py -v`
Expected: FAIL — `No such command 'render'`.

- [ ] **Step 3: Append to `core/cli.py`**

Add to the imports:

```python
from .render.html import write_html
from .render.markdown import write_markdown
from .render.xlsx import write_xlsx
```

Add near the other module-level constants:

```python
REPORTS_DIR = Path("reports")
```

Add after the `status_command` function:

```python
@app.command("render")
def render_command() -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = storage.list_vendors(CANDIDATES_DIR)
    for message in gap_report(taxonomy, vendors):
        typer.echo(message)
    write_markdown(taxonomy, vendors, REPORTS_DIR)
    write_xlsx(taxonomy, vendors, REPORTS_DIR / "comparison-matrix.xlsx")
    write_html(taxonomy, vendors, REPORTS_DIR / "dashboard.html")
    typer.echo(f"rendered reports to {REPORTS_DIR}/")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_render.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests across every task pass (44 passed).

- [ ] **Step 6: Commit**

```bash
git add core/cli.py tests/test_cli_render.py
git commit -m "Add CLI render command wiring Markdown, XLSX, and HTML output"
```

---

## Self-Review Notes

- **Spec coverage:** Pydantic models (Task 2), YAML SSoT (Task 3), CLI as sole mutation path (Tasks 4–7, 11), criteria extensibility + gap detection (Task 7), benchmark ground-truth + generic scan ingestion + ad hoc observation capture (Task 6), Markdown/XLSX/HTML rendering (Tasks 8–10) are all covered. The five Claude Code skills and the OWASP ZAP reference adapter script are intentionally out of scope for this plan — see the note below.
- **Placeholder scan:** no TODO/TBD markers; every step has complete, runnable code.
- **Type consistency:** `vendor_id`/`criterion_id` parameter names and `--vendor-id`/`--criterion-id` flags are used consistently from Task 5 onward; `weighted_score`, `gap_report`, and the `write_*` render functions keep identical signatures everywhere they're consumed.

**Not covered by this plan (follow-on work):** the `.claude/skills/dast-criteria`, `dast-discovery`, `dast-paper-cut`, `dast-handson`, `dast-report` prompt-based skills, and the OWASP ZAP reference adapter invocation, both of which build on top of the CLI this plan delivers. These aren't unit-testable the same way (they're prompts, not code) and should be a separate plan once this core library is in place and usable standalone.
