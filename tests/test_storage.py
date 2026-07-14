# tests/test_storage.py
from core import storage
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
