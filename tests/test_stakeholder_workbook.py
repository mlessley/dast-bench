from core.models import (
    Confidence,
    Criterion,
    CriteriaTaxonomy,
    CriterionResearchCache,
    ScoreEntry,
    Vendor,
    VendorResearchCache,
    VendorSource,
)
from core.render.stakeholder_workbook import compute_priority_order


def _taxonomy():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="low-weight", category="Cat", name="Low Weight", description="d", weight=5, rubric="r"),
            Criterion(id="high-weight-confident", category="Cat", name="High Confident", description="d", weight=20, rubric="r"),
            Criterion(id="high-weight-shaky", category="Cat", name="High Shaky", description="d", weight=20, rubric="r"),
        ]
    )


def _vendor():
    vendor = Vendor(id="v1", name="V1", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="low-weight", score=5.0, evidence="e", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="high-weight-confident", score=4.5, evidence="e", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="high-weight-shaky", score=2.0, evidence="e", confidence=Confidence.PAPER))
    return vendor


def test_priority_order_sorts_by_weight_then_needs_attention():
    taxonomy = _taxonomy()
    vendor = _vendor()
    cache = VendorResearchCache(vendor_id="v1")
    order = compute_priority_order(taxonomy, vendor, cache)
    # both weight-20 criteria outrank the weight-5 one; within the
    # weight-20 band, the low-scoring (<=2.5) one sorts first
    assert order == ["high-weight-shaky", "high-weight-confident", "low-weight"]


def test_priority_order_pulls_up_gap_checked_criteria_even_with_high_score():
    taxonomy = _taxonomy()
    vendor = _vendor()
    vendor.scores[-1] = ScoreEntry(criterion_id="high-weight-shaky", score=4.5, evidence="e", confidence=Confidence.PAPER)
    cache = VendorResearchCache(
        vendor_id="v1",
        criteria={"high-weight-shaky": CriterionResearchCache(reviewed_by_gap_check=True)},
    )
    order = compute_priority_order(taxonomy, vendor, cache)
    assert order == ["high-weight-shaky", "high-weight-confident", "low-weight"]
