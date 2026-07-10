from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.render.markdown import render_comparison_matrix, render_scorecard, weighted_score, write_markdown


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
