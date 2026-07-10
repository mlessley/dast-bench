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
