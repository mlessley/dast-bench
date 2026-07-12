# tests/test_normalize_nuclei.py
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".github" / "scripts" / "normalize" / "nuclei.py"


def _run(raw_lines: list[dict], tmp_path: Path):
    raw_path = tmp_path / "raw-report.jsonl"
    raw_path.write_text("\n".join(json.dumps(line) for line in raw_lines))
    output_path = tmp_path / "normalized.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(raw_path), str(output_path)],
        capture_output=True,
        text=True,
    )
    return result, output_path


def test_normalizes_findings_into_generic_finding_shape(tmp_path):
    raw_lines = [
        {
            "template-id": "exposed-panels/generic-detect",
            "info": {"name": "Generic Exposed Panel", "severity": "medium"},
            "matched-at": "http://localhost:3000/admin",
        },
        {
            "template-id": "cves/CVE-2021-12345",
            "info": {"name": "Example Known CVE", "severity": "high"},
            "matched-at": "http://localhost:3000/api",
        },
    ]
    result, output_path = _run(raw_lines, tmp_path)
    assert result.returncode == 0, result.stderr
    findings = json.loads(output_path.read_text())
    assert findings == [
        {
            "vuln_id": "exposed-panels/generic-detect",
            "severity": "medium",
            "description": "Generic Exposed Panel (http://localhost:3000/admin)",
        },
        {
            "vuln_id": "cves/CVE-2021-12345",
            "severity": "high",
            "description": "Example Known CVE (http://localhost:3000/api)",
        },
    ]


def test_deduplicates_repeated_template_ids(tmp_path):
    raw_lines = [
        {
            "template-id": "cves/CVE-2021-12345",
            "info": {"name": "Example Known CVE", "severity": "high"},
            "matched-at": "http://localhost:3000/a",
        },
        {
            "template-id": "cves/CVE-2021-12345",
            "info": {"name": "Example Known CVE", "severity": "high"},
            "matched-at": "http://localhost:3000/b",
        },
    ]
    result, output_path = _run(raw_lines, tmp_path)
    assert result.returncode == 0, result.stderr
    findings = json.loads(output_path.read_text())
    assert len(findings) == 1
    assert findings[0]["vuln_id"] == "cves/CVE-2021-12345"


def test_skips_blank_lines(tmp_path):
    raw_path = tmp_path / "raw-report.jsonl"
    raw_path.write_text(
        json.dumps({"template-id": "tech-detect/example", "info": {"name": "Example", "severity": "info"}}) + "\n\n"
    )
    output_path = tmp_path / "normalized.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(raw_path), str(output_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads(output_path.read_text())
    assert len(findings) == 1


def test_unrecognized_report_shape_exits_nonzero_with_error_message(tmp_path):
    raw_path = tmp_path / "raw-report.jsonl"
    raw_path.write_text(json.dumps({"template-id": "example"}))  # missing 'info'
    output_path = tmp_path / "normalized.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(raw_path), str(output_path)], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "error:" in result.stderr.lower()
    assert not output_path.exists()


def test_missing_raw_report_file_exits_nonzero_with_error_message(tmp_path):
    missing_path = tmp_path / "does-not-exist.jsonl"
    output_path = tmp_path / "normalized.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing_path), str(output_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "error:" in result.stderr.lower()
    assert not output_path.exists()
