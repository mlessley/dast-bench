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
