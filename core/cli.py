from __future__ import annotations

import json
from pathlib import Path

import typer

from . import storage
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
from .render.html import write_html
from .render.markdown import write_markdown
from .render.stakeholder_workbook import compute_priority_order, generate_workbook
from .render.xlsx import write_xlsx
from .stakeholder_review import merge as merge_stakeholder_copy
from .stakeholder_review import populate as populate_pending
from .stakeholder_review import snapshot as snapshot_workbook
from .stakeholder_review import validate_workbook
from .status import gap_report
from .workflow import SKILLS, phase_report

app = typer.Typer()
criteria_app = typer.Typer()
app.add_typer(criteria_app, name="criteria")

DATA_DIR = Path("data")
CRITERIA_PATH = DATA_DIR / "criteria.yaml"
CANDIDATES_DIR = DATA_DIR / "candidates"
BENCHMARKS_PATH = DATA_DIR / "benchmarks.yaml"
REPORTS_DIR = Path("reports")
RESEARCH_CACHE_DIR = DATA_DIR / "research-cache"
STAKEHOLDER_REVIEW_ARCHIVE_DIR = DATA_DIR / "stakeholder-reviews-archive"


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


@candidate_app.command("set-ci-tool")
def set_ci_tool(id: str = typer.Option(...), tool: str = typer.Option(...)) -> None:
    vendor = _load_vendor_or_exit(id)
    vendor.ci_tool_id = tool
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, id))
    typer.echo(f"set ci-tool of '{id}' to {tool}")


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


@candidate_app.command("log-observation")
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


scan_app = typer.Typer()
app.add_typer(scan_app, name="scan")


@scan_app.command("ingest-scan-result")
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

    # Load and validate findings JSON
    try:
        findings_text = file.read_text()
    except FileNotFoundError:
        typer.echo(f"error: findings file not found: {file}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"error: failed to read findings file: {e}")
        raise typer.Exit(code=1)

    try:
        findings = json.loads(findings_text)
    except json.JSONDecodeError as e:
        typer.echo(f"error: invalid JSON in findings file: {e}")
        raise typer.Exit(code=1)

    # Validate findings is a list and extract vuln_ids
    if not isinstance(findings, list):
        typer.echo("error: findings must be a JSON array")
        raise typer.Exit(code=1)

    found_ids = set()
    for f in findings:
        if not isinstance(f, dict):
            typer.echo("error: each finding must be a JSON object")
            raise typer.Exit(code=1)
        vuln_id = f.get("vuln_id")
        if vuln_id is not None and not isinstance(vuln_id, str):
            typer.echo("error: vuln_id must be a string")
            raise typer.Exit(code=1)
        if vuln_id:
            found_ids.add(vuln_id)

    known_ids = {vuln.id for vuln in bench.known_vulnerabilities}
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


@benchmark_app.command("remove-vulnerability")
def remove_benchmark_vulnerability(
    benchmark_id: str = typer.Option(...),
    vuln_id: str = typer.Option(...),
) -> None:
    benchmarks = storage.load_benchmarks(BENCHMARKS_PATH)
    bench = next((b for b in benchmarks if b.id == benchmark_id), None)
    if not bench:
        typer.echo(f"error: benchmark '{benchmark_id}' not found")
        raise typer.Exit(code=1)
    if not any(v.id == vuln_id for v in bench.known_vulnerabilities):
        typer.echo(f"error: vulnerability '{vuln_id}' not found on benchmark '{benchmark_id}'")
        raise typer.Exit(code=1)
    bench.known_vulnerabilities = [v for v in bench.known_vulnerabilities if v.id != vuln_id]
    storage.save_benchmarks(benchmarks, BENCHMARKS_PATH)
    typer.echo(f"removed vulnerability '{vuln_id}' from benchmark '{benchmark_id}'")


@benchmark_app.command("list")
def list_benchmarks() -> None:
    for b in storage.load_benchmarks(BENCHMARKS_PATH):
        typer.echo(f"{b.id}\t{b.name}\t{b.target_type}\tknown_vulnerabilities={len(b.known_vulnerabilities)}")


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


@app.command("workflow")
def workflow_command() -> None:
    for skill in SKILLS:
        typer.echo(skill["name"])
        typer.echo(f"  purpose: {skill['purpose']}")
        typer.echo(f"  reads:   {skill['reads']}")
        typer.echo(f"  writes:  {skill['writes']}")
        typer.echo("")


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


stakeholder_review_app = typer.Typer()
app.add_typer(stakeholder_review_app, name="stakeholder-review")


def _parse_stakeholder(raw: str) -> tuple[str | None, str]:
    name, _, role = raw.partition(":")
    return (name or None, role)


def _parse_pending_criteria(raw_list: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for raw in raw_list:
        vendor_id, _, criteria_csv = raw.partition(":")
        result.setdefault(vendor_id, set()).update(c.strip() for c in criteria_csv.split(",") if c.strip())
    return result


@stakeholder_review_app.command("generate")
def stakeholder_review_generate(
    vendor_id: list[str] = typer.Option(..., "--vendor-id"),
    stakeholder: list[str] = typer.Option(..., "--stakeholder"),
    pending_criteria: list[str] = typer.Option([], "--pending-criteria"),
    out: Path = typer.Option(...),
) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = []
    for vid in vendor_id:
        path = storage.vendor_path(CANDIDATES_DIR, vid)
        if not path.exists():
            typer.echo(f"error: vendor '{vid}' not found")
            raise typer.Exit(code=1)
        vendor = storage.load_vendor(path)
        for criterion in taxonomy.criteria:
            if vendor.score_for(criterion.id) is None:
                typer.echo(f"error: vendor '{vid}' has no score for criterion '{criterion.id}'")
                raise typer.Exit(code=1)
        vendors.append(vendor)

    stakeholders = [_parse_stakeholder(s) for s in stakeholder]
    pending = _parse_pending_criteria(pending_criteria)
    research_caches = {
        v.id: storage.load_research_cache(storage.research_cache_path(RESEARCH_CACHE_DIR, v.id), v.id)
        for v in vendors
    }
    generate_workbook(taxonomy, vendors, stakeholders, pending, research_caches, out)
    typer.echo(f"generated stakeholder review workbook at {out}")


@stakeholder_review_app.command("populate")
def stakeholder_review_populate(
    vendor_id: str = typer.Option(...),
    file: Path = typer.Option(...),
) -> None:
    path = storage.vendor_path(CANDIDATES_DIR, vendor_id)
    if not path.exists():
        typer.echo(f"error: vendor '{vendor_id}' not found")
        raise typer.Exit(code=1)
    vendor = storage.load_vendor(path)
    typer.echo(populate_pending(vendor, file))


@stakeholder_review_app.command("merge")
def stakeholder_review_merge(
    into: Path = typer.Option(...),
    from_: Path = typer.Option(..., "--from"),
) -> None:
    if not into.exists() or not from_.exists():
        typer.echo("error: both --into and --from files must exist")
        raise typer.Exit(code=1)
    typer.echo(merge_stakeholder_copy(into, from_))


@stakeholder_review_app.command("validate")
def stakeholder_review_validate(file: Path = typer.Option(...)) -> None:
    if not file.exists():
        typer.echo(f"error: file not found: {file}")
        raise typer.Exit(code=1)
    issues = validate_workbook(file)
    if not issues:
        typer.echo("no issues found")
        return
    for issue in issues:
        typer.echo(issue)


@stakeholder_review_app.command("snapshot")
def stakeholder_review_snapshot(
    file: Path = typer.Option(...),
    vendor_id: str = typer.Option(...),
    label: str = typer.Option(None),
) -> None:
    if not file.exists():
        typer.echo(f"error: file not found: {file}")
        raise typer.Exit(code=1)
    dest = snapshot_workbook(file, vendor_id, STAKEHOLDER_REVIEW_ARCHIVE_DIR, label)
    typer.echo(f"snapshotted to {dest}")
