from __future__ import annotations

import json
from pathlib import Path

import typer

from . import storage
from .models import Confidence, Criterion, HandsOnResult, Observation, ScoreEntry, Vendor, VendorSource, VendorStatus
from .render.html import write_html
from .render.markdown import write_markdown
from .render.xlsx import write_xlsx
from .status import gap_report

app = typer.Typer()
criteria_app = typer.Typer()
app.add_typer(criteria_app, name="criteria")

DATA_DIR = Path("data")
CRITERIA_PATH = DATA_DIR / "criteria.yaml"
CANDIDATES_DIR = DATA_DIR / "candidates"
BENCHMARKS_PATH = DATA_DIR / "benchmarks.yaml"
REPORTS_DIR = Path("reports")


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


scan_app = typer.Typer()
app.add_typer(scan_app, name="scan")


@scan_app.command("log-observation")
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


@app.command("status")
def status_command() -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = storage.list_vendors(CANDIDATES_DIR)
    messages = gap_report(taxonomy, vendors)
    if not messages:
        typer.echo("no gaps found")
    for message in messages:
        typer.echo(message)


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
