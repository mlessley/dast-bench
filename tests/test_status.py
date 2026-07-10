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
