# tests/test_dast_benchmark_workflow.py
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "dast-benchmark.yml"


def _load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def test_workflow_dispatch_inputs_present():
    workflow = _load_workflow()
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert inputs["tool"]["type"] == "choice"
    assert "zap" in inputs["tool"]["options"]
    assert inputs["target"]["type"] == "choice"
    assert set(inputs["target"]["options"]) == {"juice-shop", "vampi"}


def test_juice_shop_job_has_correct_service_and_gate():
    workflow = _load_workflow()
    job = workflow["jobs"]["juice-shop"]
    assert job["if"] == "inputs.target == 'juice-shop'"
    assert job["services"]["target"]["image"] == "bkimminich/juice-shop"
    assert "3000:3000" in job["services"]["target"]["ports"]


def test_vampi_job_has_correct_service_and_gate():
    workflow = _load_workflow()
    job = workflow["jobs"]["vampi"]
    assert job["if"] == "inputs.target == 'vampi'"
    assert job["services"]["target"]["image"] == "erev0s/vampi:latest"
    assert "5000:5000" in job["services"]["target"]["ports"]
    assert job["services"]["target"]["env"]["vulnerable"] == "1"


def test_each_job_uploads_raw_report_unconditionally():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        raw_upload_steps = [
            s
            for s in steps
            if s.get("uses", "").startswith("actions/upload-artifact")
            and "raw-report" in s.get("with", {}).get("name", "")
        ]
        assert len(raw_upload_steps) == 1, f"expected exactly one raw-report upload step in job {job_name}"
        assert "if" not in raw_upload_steps[0], f"raw-report upload in job {job_name} must not be conditional"


def test_each_job_normalizes_and_uploads_for_zap_conditionally():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        normalize_steps = [s for s in steps if "normalize/zap.py" in s.get("run", "")]
        assert len(normalize_steps) == 1, f"expected exactly one normalize step in job {job_name}"
        assert normalize_steps[0]["if"] == "inputs.tool == 'zap'"

        normalized_upload_steps = [
            s
            for s in steps
            if s.get("uses", "").startswith("actions/upload-artifact")
            and "normalized" in s.get("with", {}).get("name", "")
        ]
        assert len(normalized_upload_steps) == 1, f"expected exactly one normalized-report upload step in job {job_name}"
        assert normalized_upload_steps[0]["if"] == "inputs.tool == 'zap'"


def test_each_job_scans_with_zap_and_tolerates_its_nonzero_exit():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        scan_steps = [s for s in steps if "zap-full-scan.py" in s.get("run", "")]
        assert len(scan_steps) == 1, f"expected exactly one ZAP scan step in job {job_name}"
        assert "|| true" in scan_steps[0]["run"], (
            f"ZAP scan step in job {job_name} must tolerate zap-full-scan.py's "
            "non-zero exit when it finds alerts"
        )
