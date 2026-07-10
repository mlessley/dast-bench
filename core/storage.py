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
