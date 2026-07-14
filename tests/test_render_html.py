# tests/test_render_html.py
from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorSource
from core.render.html import write_html


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


def test_write_html_includes_vendor_and_criterion_names(tmp_path):
    out_path = tmp_path / "dashboard.html"
    write_html(_sample_taxonomy(), [_sample_vendor()], out_path)
    html = out_path.read_text()
    assert "Vendor One" in html
    assert "API Coverage" in html
    assert "sortTable" in html
    assert "<script" in html


def test_write_html_includes_disclaimer(tmp_path):
    out_path = tmp_path / "dashboard.html"
    write_html(_sample_taxonomy(), [_sample_vendor()], out_path)
    html = out_path.read_text()
    assert "Draft/sample output" in html
    assert "not a final vendor recommendation" in html
