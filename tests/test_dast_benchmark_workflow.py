# tests/test_dast_benchmark_workflow.py
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "dast-benchmark.yml"


def _load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def test_run_name_shows_tool_and_target_in_the_runs_list():
    workflow = _load_workflow()
    assert workflow["run-name"] == "${{ inputs.tool == 'zap' && 'ZAP' || 'Nuclei' }} · ${{ inputs.target }}"


def test_workflow_dispatch_inputs_present():
    workflow = _load_workflow()
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert inputs["tool"]["type"] == "choice"
    assert "zap" in inputs["tool"]["options"]
    assert "nuclei" in inputs["tool"]["options"]
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


def test_each_job_normalizes_and_uploads_for_known_tools_conditionally():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        normalize_steps = [s for s in steps if "normalize/${{ inputs.tool }}.py" in s.get("run", "")]
        assert len(normalize_steps) == 1, f"expected exactly one normalize step in job {job_name}"
        assert normalize_steps[0]["if"] == "inputs.tool == 'zap' || inputs.tool == 'nuclei'"

        normalized_upload_steps = [
            s
            for s in steps
            if s.get("uses", "").startswith("actions/upload-artifact")
            and "normalized" in s.get("with", {}).get("name", "")
        ]
        assert len(normalized_upload_steps) == 1, f"expected exactly one normalized-report upload step in job {job_name}"
        assert normalized_upload_steps[0]["if"] == "inputs.tool == 'zap' || inputs.tool == 'nuclei'"


def test_each_job_scans_with_zap_and_tolerates_its_nonzero_exit():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        scan_steps = [s for s in steps if "zap-full-scan.py" in s.get("run", "")]
        assert len(scan_steps) == 1, f"expected exactly one ZAP scan step in job {job_name}"
        assert scan_steps[0]["if"] == "inputs.tool == 'zap'", (
            f"ZAP scan step in job {job_name} must be gated on inputs.tool == 'zap' "
            "(retrofitted so ZAP isn't a special, unconditional case once other tools exist)"
        )
        assert "|| true" in scan_steps[0]["run"], (
            f"ZAP scan step in job {job_name} must tolerate zap-full-scan.py's "
            "non-zero exit when it finds alerts"
        )


def test_each_job_scans_with_nuclei_conditionally():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        scan_steps = [s for s in steps if "projectdiscovery/nuclei" in s.get("run", "")]
        assert len(scan_steps) == 1, f"expected exactly one Nuclei scan step in job {job_name}"
        assert scan_steps[0]["if"] == "inputs.tool == 'nuclei'"
        assert "|| true" in scan_steps[0]["run"], (
            f"Nuclei scan step in job {job_name} should tolerate a non-zero exit, "
            "consistent with the ZAP step's defensive style"
        )


def test_juice_shop_job_authenticates_before_scanning():
    # Unauthenticated scans never reach Juice Shop's login-gated challenges
    # (SQLi in the login form, JWT weaknesses, etc.) -- a real gap this
    # project's own dogfooding run surfaced (detected 1/10 known
    # vulnerabilities). This step registers a test user, logs in, and
    # captures the JWT so both ZAP and Nuclei can attack authenticated.
    workflow = _load_workflow()
    steps = workflow["jobs"]["juice-shop"]["steps"]
    auth_steps = [s for s in steps if "/api/Users/" in s.get("run", "") and "/rest/user/login" in s.get("run", "")]
    assert len(auth_steps) == 1, "expected exactly one register+login step in the juice-shop job"
    assert "GITHUB_ENV" in auth_steps[0]["run"], "auth step must export the token via GITHUB_ENV for later steps"

    auth_index = steps.index(auth_steps[0])
    scan_indices = [
        i
        for i, s in enumerate(steps)
        if "zap-full-scan.py" in s.get("run", "") or "projectdiscovery/nuclei" in s.get("run", "")
    ]
    assert auth_index < min(scan_indices), "auth step must run before every scan step"


def test_vampi_job_authenticates_before_scanning():
    workflow = _load_workflow()
    steps = workflow["jobs"]["vampi"]["steps"]
    auth_steps = [
        s for s in steps if "/users/v1/register" in s.get("run", "") and "/users/v1/login" in s.get("run", "")
    ]
    assert len(auth_steps) == 1, "expected exactly one register+login step in the vampi job"
    assert "GITHUB_ENV" in auth_steps[0]["run"], "auth step must export the token via GITHUB_ENV for later steps"

    auth_index = steps.index(auth_steps[0])
    scan_indices = [
        i
        for i, s in enumerate(steps)
        if "zap-full-scan.py" in s.get("run", "") or "projectdiscovery/nuclei" in s.get("run", "")
    ]
    assert auth_index < min(scan_indices), "auth step must run before every scan step"


def test_zap_scan_steps_inject_auth_header():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        scan_steps = [s for s in steps if "zap-full-scan.py" in s.get("run", "")]
        assert "ZAP_AUTH_HEADER_VALUE" in scan_steps[0]["run"], (
            f"ZAP scan step in job {job_name} must inject the captured token via "
            "ZAP_AUTH_HEADER_VALUE so the scan runs authenticated"
        )


def test_nuclei_scan_steps_inject_auth_header():
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        scan_steps = [s for s in steps if "projectdiscovery/nuclei" in s.get("run", "")]
        assert "-H " in scan_steps[0]["run"] and "Authorization" in scan_steps[0]["run"], (
            f"Nuclei scan step in job {job_name} must inject the captured token via "
            "a -H Authorization header so the scan runs authenticated"
        )


def test_each_job_chmods_workspace_before_any_scan():
    # ZAP's docker image runs as its own internal `zap` user, which cannot
    # write to the GitHub Actions runner's mounted checkout directory unless
    # its permissions are opened up first — without this step, the scan
    # completes but fails to write raw-report.json with a permission error.
    # Generalized to run before any tool's scan step, not just ZAP's, since
    # other tools' containers can hit the same mounted-volume permission issue.
    workflow = _load_workflow()
    for job_name in ("juice-shop", "vampi"):
        steps = workflow["jobs"][job_name]["steps"]
        chmod_indices = [i for i, s in enumerate(steps) if "chmod" in s.get("run", "") and "777" in s.get("run", "")]
        scan_indices = [
            i
            for i, s in enumerate(steps)
            if "zap-full-scan.py" in s.get("run", "") or "projectdiscovery/nuclei" in s.get("run", "")
        ]
        assert len(chmod_indices) == 1, f"expected exactly one chmod step in job {job_name}"
        assert len(scan_indices) == 2, f"expected exactly two scan steps (ZAP + Nuclei) in job {job_name}"
        assert chmod_indices[0] < min(scan_indices), (
            f"chmod step in job {job_name} must run before every tool's scan step, "
            "not after"
        )
