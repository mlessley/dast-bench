# Research Cache (Code) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new, git-tracked research cache (`data/research-cache/<vendor-id>.yaml`) with a Pydantic data model, storage functions, and a `dast-bench cache` CLI command group (`record`, `show`, `invalidate` with all three invalidation modes).

**Architecture:** Two tasks — Task 1 adds the data model (`core/models.py`) and storage functions (`core/storage.py`); Task 2 adds the CLI command group (`core/cli.py`), which depends on Task 1's exports.

**Tech Stack:** Python, Pydantic, Typer, pytest, `uv`. No new dependencies.

## Global Constraints

- This is Track A (code) of the research-cache-and-gap-check-design spec. Track B (skill-instruction changes to `dast-discovery`/`dast-shortlist`) is a separate plan.
- Never edit `data/research-cache/*.yaml` by hand — same "CLI is the only sanctioned way to mutate data" rule as every other file in this project.
- No change to the existing `Vendor`/`ScoreEntry`/`Criterion` models or any existing CLI command's behavior — this is purely additive.
- Use `uv run pytest` for every test run. Never modify `uv.lock`.

---

### Task 1: `ResearchFinding`/`CriterionResearchCache`/`VendorResearchCache` models + storage functions

**Files:**
- Modify: `core/models.py` (append new classes at the end of the file, after `Benchmark`)
- Modify: `core/storage.py` (append new functions at the end of the file, extend the existing import line)
- Test: `tests/test_models.py` (extend import line, append new tests)
- Test: `tests/test_storage.py` (extend import line, append new tests)

**Interfaces:**
- Produces: `ResearchFinding(url: str, snippet: str)`, `CriterionResearchCache(researched_at: datetime, queries: list[str], findings: list[ResearchFinding], reviewed_by_gap_check: bool, stale: bool)`, `VendorResearchCache(vendor_id: str, criteria: dict[str, CriterionResearchCache])` — all in `core/models.py`. `research_cache_path(base_dir: Path, vendor_id: str) -> Path`, `load_research_cache(path: Path, vendor_id: str) -> VendorResearchCache`, `save_research_cache(cache: VendorResearchCache, path: Path) -> None` — all in `core/storage.py`. Task 2 imports and uses all of these.

- [ ] **Step 1: Write the failing tests**

Update the import line at the top of `tests/test_models.py` from:

```python
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
```

to:

```python
from core.models import (
    Benchmark,
    BenchmarkVulnerability,
    Confidence,
    Criterion,
    CriteriaTaxonomy,
    CriterionResearchCache,
    HandsOnResult,
    Observation,
    ResearchFinding,
    ScoreEntry,
    Vendor,
    VendorResearchCache,
    VendorSource,
    VendorStatus,
)
```

Append these tests to the end of `tests/test_models.py`:

```python
def test_criterion_research_cache_defaults():
    entry = CriterionResearchCache()
    assert entry.queries == []
    assert entry.findings == []
    assert entry.reviewed_by_gap_check is False
    assert entry.stale is False


def test_vendor_research_cache_holds_criteria_by_id():
    cache = VendorResearchCache(vendor_id="veracode")
    cache.criteria["aspm-integration"] = CriterionResearchCache(
        queries=["Veracode Risk Manager ASPM"],
        findings=[ResearchFinding(url="veracode.com/risk-manager", snippet="ASPM platform")],
    )
    assert cache.criteria["aspm-integration"].findings[0].url == "veracode.com/risk-manager"
    assert cache.criteria["aspm-integration"].queries == ["Veracode Risk Manager ASPM"]
```

Update the import line at the top of `tests/test_storage.py` from:

```python
from core.models import (
    Benchmark,
    BenchmarkVulnerability,
    Criterion,
    CriteriaTaxonomy,
    Vendor,
    VendorSource,
)
```

to:

```python
from core.models import (
    Benchmark,
    BenchmarkVulnerability,
    Criterion,
    CriteriaTaxonomy,
    CriterionResearchCache,
    ResearchFinding,
    Vendor,
    VendorResearchCache,
    VendorSource,
)
```

Append these tests to the end of `tests/test_storage.py`:

```python
def test_save_and_load_research_cache_round_trips(tmp_path):
    cache = VendorResearchCache(vendor_id="veracode")
    cache.criteria["aspm-integration"] = CriterionResearchCache(
        queries=["Veracode Risk Manager ASPM"],
        findings=[ResearchFinding(url="veracode.com/risk-manager", snippet="ASPM platform")],
    )
    path = storage.research_cache_path(tmp_path, "veracode")
    storage.save_research_cache(cache, path)
    assert storage.load_research_cache(path, "veracode") == cache


def test_load_research_cache_returns_empty_cache_when_missing(tmp_path):
    path = storage.research_cache_path(tmp_path, "missing-vendor")
    cache = storage.load_research_cache(path, "missing-vendor")
    assert cache.vendor_id == "missing-vendor"
    assert cache.criteria == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py tests/test_storage.py -v`
Expected: collection errors / `ImportError` (the new names don't exist in `core.models`/`core.storage` yet).

- [ ] **Step 3: Implement the models**

Append to the end of `core/models.py`:

```python
class ResearchFinding(BaseModel):
    url: str
    snippet: str


class CriterionResearchCache(BaseModel):
    researched_at: datetime = Field(default_factory=datetime.utcnow)
    queries: list[str] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    reviewed_by_gap_check: bool = False
    stale: bool = False


class VendorResearchCache(BaseModel):
    vendor_id: str
    criteria: dict[str, CriterionResearchCache] = Field(default_factory=dict)
```

- [ ] **Step 4: Implement the storage functions**

Change the import line at the top of `core/storage.py` from:

```python
from .models import Benchmark, CriteriaTaxonomy, Vendor
```

to:

```python
from .models import Benchmark, CriteriaTaxonomy, Vendor, VendorResearchCache
```

Append to the end of `core/storage.py`:

```python
def research_cache_path(base_dir: Path, vendor_id: str) -> Path:
    return base_dir / f"{vendor_id}.yaml"


def load_research_cache(path: Path, vendor_id: str) -> VendorResearchCache:
    if not path.exists():
        return VendorResearchCache(vendor_id=vendor_id)
    data = yaml.safe_load(path.read_text()) or {}
    return VendorResearchCache.model_validate(data)


def save_research_cache(cache: VendorResearchCache, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cache.model_dump(mode="json"), sort_keys=False))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py tests/test_storage.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/storage.py tests/test_models.py tests/test_storage.py
git commit -m "Add ResearchFinding/CriterionResearchCache/VendorResearchCache models and storage"
```

---

### Task 2: `dast-bench cache` CLI command group

**Files:**
- Modify: `core/cli.py` (extend imports, add `RESEARCH_CACHE_DIR` constant, add the `cache` command group)
- Test: `tests/test_cli_cache.py` (new file)

**Interfaces:**
- Consumes: `ResearchFinding`, `CriterionResearchCache`, `VendorResearchCache` (from `core.models`), `storage.research_cache_path`, `storage.load_research_cache`, `storage.save_research_cache` (from Task 1, exact signatures above).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_cache.py`:

```python
import json

from typer.testing import CliRunner

from core import storage
from core.cli import app

runner = CliRunner()


def _add_vendor(monkeypatch, tmp_path, vendor_id="veracode"):
    monkeypatch.chdir(tmp_path)
    return runner.invoke(app, ["candidate", "add", "--id", vendor_id, "--name", "Veracode", "--source", "seeded"])


def _add_criterion(criterion_id="aspm-integration"):
    return runner.invoke(
        app,
        [
            "criteria", "add-criterion",
            "--id", criterion_id, "--category", "Reporting & Extensibility", "--name", "n",
            "--description", "d", "--weight", "100", "--rubric", "r",
        ],
    )


def _write_findings_file(tmp_path, findings):
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(findings))
    return path


def test_cache_record_then_show_round_trips(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(
        tmp_path, [{"url": "veracode.com/risk-manager", "snippet": "ASPM platform"}]
    )
    result = runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--query", "Veracode Risk Manager ASPM",
            "--findings-file", str(findings_file),
        ],
    )
    assert result.exit_code == 0, result.output

    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    entry = cache.criteria["aspm-integration"]
    assert entry.queries == ["Veracode Risk Manager ASPM"]
    assert entry.findings[0].url == "veracode.com/risk-manager"
    assert entry.stale is False

    result = runner.invoke(app, ["cache", "show", "--vendor-id", "veracode"])
    assert result.exit_code == 0, result.output
    assert "aspm-integration" in result.output
    assert "veracode.com/risk-manager" in result.output


def test_cache_record_rejects_malformed_findings_file(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = tmp_path / "bad.json"
    findings_file.write_text("not json")
    result = runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    assert result.exit_code != 0
    assert "invalid JSON" in result.output


def test_cache_show_errors_when_no_cache_exists(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(app, ["cache", "show", "--vendor-id", "veracode"])
    assert result.exit_code != 0
    assert "no research cache found" in result.output


def test_cache_invalidate_single_criterion(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    result = runner.invoke(
        app, ["cache", "invalidate", "--vendor-id", "veracode", "--criterion-id", "aspm-integration"]
    )
    assert result.exit_code == 0, result.output
    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    assert cache.criteria["aspm-integration"].stale is True


def test_cache_invalidate_by_max_score(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    _add_criterion("aspm-integration")
    _add_criterion("detection-accuracy")
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--score", "2.0", "--evidence", "low score", "--confidence", "paper",
        ],
    )
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "veracode", "--criterion-id", "detection-accuracy",
            "--score", "4.5", "--evidence", "high score", "--confidence", "paper",
        ],
    )
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "detection-accuracy",
            "--findings-file", str(findings_file),
        ],
    )

    result = runner.invoke(
        app, ["cache", "invalidate", "--vendor-id", "veracode", "--max-score", "2.5"]
    )
    assert result.exit_code == 0, result.output
    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    assert cache.criteria["aspm-integration"].stale is True
    assert cache.criteria["detection-accuracy"].stale is False


def test_cache_invalidate_all(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "detection-accuracy",
            "--findings-file", str(findings_file),
        ],
    )
    result = runner.invoke(app, ["cache", "invalidate", "--vendor-id", "veracode", "--all"])
    assert result.exit_code == 0, result.output
    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    assert all(entry.stale for entry in cache.criteria.values())


def test_cache_invalidate_requires_exactly_one_mode(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    result = runner.invoke(app, ["cache", "invalidate", "--vendor-id", "veracode"])
    assert result.exit_code != 0
    assert "exactly one" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_cache.py -v`
Expected: FAIL — `Error: No such command 'cache'` (the command group doesn't exist yet).

- [ ] **Step 3: Implement the CLI command group**

Change the import block at the top of `core/cli.py` from:

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

to:

```python
from .models import (
    Benchmark,
    BenchmarkVulnerability,
    Confidence,
    Criterion,
    CriterionResearchCache,
    HandsOnResult,
    Observation,
    ResearchFinding,
    ScoreEntry,
    Vendor,
    VendorSource,
    VendorStatus,
)
```

Add this constant right after the existing `REPORTS_DIR = Path("reports")` line:

```python
RESEARCH_CACHE_DIR = DATA_DIR / "research-cache"
```

Append this entire block to the end of `core/cli.py` (after the existing `render_command` function):

```python
cache_app = typer.Typer()
app.add_typer(cache_app, name="cache")


def _load_research_cache(vendor_id: str) -> "storage.VendorResearchCache":
    path = storage.research_cache_path(RESEARCH_CACHE_DIR, vendor_id)
    return storage.load_research_cache(path, vendor_id)


def _print_cache_entry(criterion_id: str, entry: CriterionResearchCache) -> None:
    typer.echo(
        f"{criterion_id}\tresearched_at={entry.researched_at.isoformat()}\t"
        f"stale={entry.stale}\treviewed_by_gap_check={entry.reviewed_by_gap_check}"
    )
    for q in entry.queries:
        typer.echo(f"  query: {q}")
    for f in entry.findings:
        typer.echo(f"  finding: {f.url} -- {f.snippet}")


@cache_app.command("record")
def cache_record(
    vendor_id: str = typer.Option(...),
    criterion_id: str = typer.Option(...),
    query: list[str] = typer.Option([]),
    findings_file: Path = typer.Option(...),
    reviewed_by_gap_check: bool = typer.Option(False),
) -> None:
    try:
        findings_text = findings_file.read_text()
    except FileNotFoundError:
        typer.echo(f"error: findings file not found: {findings_file}")
        raise typer.Exit(code=1)

    try:
        findings_data = json.loads(findings_text)
    except json.JSONDecodeError as e:
        typer.echo(f"error: invalid JSON in findings file: {e}")
        raise typer.Exit(code=1)

    if not isinstance(findings_data, list):
        typer.echo("error: findings file must contain a JSON array")
        raise typer.Exit(code=1)

    findings = []
    for f in findings_data:
        if not isinstance(f, dict) or "url" not in f or "snippet" not in f:
            typer.echo("error: each finding must be an object with 'url' and 'snippet'")
            raise typer.Exit(code=1)
        findings.append(ResearchFinding(url=f["url"], snippet=f["snippet"]))

    cache = _load_research_cache(vendor_id)
    cache.criteria[criterion_id] = CriterionResearchCache(
        queries=list(query),
        findings=findings,
        reviewed_by_gap_check=reviewed_by_gap_check,
        stale=False,
    )
    storage.save_research_cache(cache, storage.research_cache_path(RESEARCH_CACHE_DIR, vendor_id))
    typer.echo(f"recorded research cache for '{vendor_id}' on '{criterion_id}'")


@cache_app.command("show")
def cache_show(
    vendor_id: str = typer.Option(...),
    criterion_id: str = typer.Option(None),
) -> None:
    path = storage.research_cache_path(RESEARCH_CACHE_DIR, vendor_id)
    if not path.exists():
        typer.echo(f"error: no research cache found for vendor '{vendor_id}'")
        raise typer.Exit(code=1)
    cache = storage.load_research_cache(path, vendor_id)
    if criterion_id:
        entry = cache.criteria.get(criterion_id)
        if not entry:
            typer.echo(f"error: no cache entry for '{vendor_id}' on criterion '{criterion_id}'")
            raise typer.Exit(code=1)
        _print_cache_entry(criterion_id, entry)
    else:
        if not cache.criteria:
            typer.echo(f"no cache entries for vendor '{vendor_id}'")
        for cid, entry in cache.criteria.items():
            _print_cache_entry(cid, entry)


@cache_app.command("invalidate")
def cache_invalidate(
    vendor_id: str = typer.Option(...),
    criterion_id: str = typer.Option(None),
    max_score: float = typer.Option(None),
    all_: bool = typer.Option(False, "--all"),
) -> None:
    modes_selected = sum([criterion_id is not None, max_score is not None, all_])
    if modes_selected != 1:
        typer.echo("error: specify exactly one of --criterion-id, --max-score, or --all")
        raise typer.Exit(code=1)

    path = storage.research_cache_path(RESEARCH_CACHE_DIR, vendor_id)
    if not path.exists():
        typer.echo(f"error: no research cache found for vendor '{vendor_id}'")
        raise typer.Exit(code=1)
    cache = storage.load_research_cache(path, vendor_id)

    if criterion_id is not None:
        entry = cache.criteria.get(criterion_id)
        if not entry:
            typer.echo(f"error: no cache entry for '{vendor_id}' on criterion '{criterion_id}'")
            raise typer.Exit(code=1)
        entry.stale = True
        count = 1
    elif all_:
        for entry in cache.criteria.values():
            entry.stale = True
        count = len(cache.criteria)
    else:
        vendor = _load_vendor_or_exit(vendor_id)
        count = 0
        for cid, entry in cache.criteria.items():
            score_entry = vendor.score_for(cid)
            if score_entry is not None and score_entry.score <= max_score:
                entry.stale = True
                count += 1

    storage.save_research_cache(cache, path)
    typer.echo(f"invalidated {count} cache entr{'y' if count == 1 else 'ies'} for '{vendor_id}'")
```

Note: the `_load_research_cache` helper's return-type annotation uses a forward-reference string `"storage.VendorResearchCache"` only as a type hint convenience — `VendorResearchCache` itself does not need to be imported into `cli.py`'s namespace since the function body never constructs one directly (it only calls `storage.load_research_cache`, which returns one). If your editor/linter complains about the forward reference, it's safe to simplify the annotation to `-> object` or remove it — this does not affect runtime behavior either way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_cache.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add core/cli.py tests/test_cli_cache.py
git commit -m "Add dast-bench cache CLI command group (record, show, invalidate)"
```
