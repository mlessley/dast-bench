from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.render.markdown import (
    _ordered_categories,
    category_weighted_score,
    render_comparison_matrix,
    render_scorecard,
    render_scoring_legend,
    weighted_score,
    write_markdown,
)


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


def _rubric_taxonomy() -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(
                id="c1",
                category="Coverage",
                name="API Coverage",
                description="d",
                weight=60,
                rubric="1: No API coverage at all. 3: Covers REST but not GraphQL. 5: Full REST and GraphQL coverage.",
            ),
            Criterion(
                id="c2",
                category="Coverage",
                name="Shadow API Discovery",
                description="d",
                weight=15,
                rubric="1: No discovery. 3: Basic heuristic discovery. 5: Full traffic-analysis-based discovery.",
            ),
            Criterion(id="c3", category="DX", name="Noise Reduction", description="d", weight=25, rubric="r"),
        ]
    )


def test_ordered_categories_preserves_first_occurrence_order():
    taxonomy = _rubric_taxonomy()
    assert _ordered_categories(taxonomy) == ["Coverage", "DX"]


def test_category_weighted_score_combines_only_that_categorys_criteria():
    taxonomy = _rubric_taxonomy()
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2, evidence="docs", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c3", score=5, evidence="docs", confidence=Confidence.PAPER))
    # Coverage: (4*60 + 2*15) / (60+15) = 270/75 = 3.6
    assert category_weighted_score(taxonomy, vendor, "Coverage") == 3.6
    # DX: (5*25) / 25 = 5.0
    assert category_weighted_score(taxonomy, vendor, "DX") == 5.0


def test_category_weighted_score_missing_score_drags_score_down():
    taxonomy = _rubric_taxonomy()
    vendor = Vendor(id="v2", name="Vendor Two", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=5, evidence="docs", confidence=Confidence.PAPER))
    # c2 unscored: (5*60 + 0) / (60+15) = 300/75 = 4.0, not 5.0 -- missing scores drag the category down,
    # mirroring how the existing overall weighted_score() already treats unscored criteria.
    assert category_weighted_score(taxonomy, vendor, "Coverage") == 4.0


def test_category_weighted_score_returns_zero_for_unknown_category():
    taxonomy = _rubric_taxonomy()
    vendor = Vendor(id="v3", name="Vendor Three", source=VendorSource.DISCOVERED)
    assert category_weighted_score(taxonomy, vendor, "Nonexistent") == 0.0


def test_render_scoring_legend_parses_rubric_anchors_grouped_by_category():
    legend = render_scoring_legend(_rubric_taxonomy())
    assert "## Scoring Legend" in legend
    assert "### Coverage" in legend
    assert "### DX" in legend
    assert "**API Coverage**" in legend
    assert "- 1: No API coverage at all." in legend
    assert "- 3: Covers REST but not GraphQL." in legend
    assert "- 5: Full REST and GraphQL coverage." in legend
