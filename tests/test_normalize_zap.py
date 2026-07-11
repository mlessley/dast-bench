# tests/test_normalize_zap.py
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".github" / "scripts" / "normalize" / "zap.py"


def _run(raw_report: dict, tmp_path: Path):
    raw_path = tmp_path / "raw-report.json"
    raw_path.write_text(json.dumps(raw_report))
    output_path = tmp_path / "normalized.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(raw_path), str(output_path)],
        capture_output=True,
        text=True,
    )
    return result, output_path


def test_normalizes_alerts_into_generic_finding_shape(tmp_path):
    raw_report = {
        "site": [
            {
                "@name": "http://localhost:3000",
                "alerts": [
                    {
                        "pluginid": "40018",
                        "name": "SQL Injection",
                        "riskcode": "3",
                        "instances": [{"uri": "http://localhost:3000/a"}, {"uri": "http://localhost:3000/b"}],
                    },
                    {
                        "pluginid": "10202",
                        "name": "Absence of Anti-CSRF Tokens",
                        "riskcode": "1",
                        "instances": [{"uri": "http://localhost:3000/c"}],
                    },
                ],
            }
        ]
    }
    result, output_path = _run(raw_report, tmp_path)
    assert result.returncode == 0, result.stderr
    findings = json.loads(output_path.read_text())
    assert findings == [
        {"vuln_id": "40018", "severity": "high", "description": "SQL Injection (2 occurrences)"},
        {"vuln_id": "10202", "severity": "low", "description": "Absence of Anti-CSRF Tokens (1 occurrence)"},
    ]


def test_deduplicates_repeated_plugin_ids_across_sites(tmp_path):
    raw_report = {
        "site": [
            {
                "@name": "http://localhost:3000",
                "alerts": [
                    {"pluginid": "40018", "name": "SQL Injection", "riskcode": "3", "instances": [{"uri": "a"}]}
                ],
            },
            {
                "@name": "http://localhost:3000/api",
                "alerts": [
                    {"pluginid": "40018", "name": "SQL Injection", "riskcode": "3", "instances": [{"uri": "b"}]}
                ],
            },
        ]
    }
    result, output_path = _run(raw_report, tmp_path)
    assert result.returncode == 0, result.stderr
    findings = json.loads(output_path.read_text())
    assert len(findings) == 1
    assert findings[0]["vuln_id"] == "40018"


def test_unrecognized_report_shape_exits_nonzero_with_error_message(tmp_path):
    raw_report = {"not_a_zap_report": True}
    result, output_path = _run(raw_report, tmp_path)
    assert result.returncode != 0
    assert "error:" in result.stderr.lower()
    assert not output_path.exists()


def test_missing_raw_report_file_exits_nonzero_with_error_message(tmp_path):
    missing_path = tmp_path / "does-not-exist.json"
    output_path = tmp_path / "normalized.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing_path), str(output_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "error:" in result.stderr.lower()
    assert not output_path.exists()
