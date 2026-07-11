# DAST Benchmark CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the GitHub Actions workflow and ZAP report normalization script described in `docs/superpowers/specs/2026-07-11-dast-benchmark-ci-pipeline-design.md` — a `workflow_dispatch` pipeline that spins up an ephemeral Juice Shop or VAmPI target as a service container, runs a ZAP full active scan against it, and produces both a raw report artifact (always) and a normalized findings artifact (for tools with a checked-in normalization script) ready to feed into the existing `dast-eval handson ingest-scan-result` CLI command.

**Architecture:** Two independent, testable pieces. (1) `.github/scripts/normalize/zap.py`: a standalone Python script (no dependency on the `core` package) that converts ZAP's native JSON report into the generic `[{vuln_id, severity, description}]` shape, deduplicating by ZAP's `pluginid` so repeated instances of the same vulnerability type don't inflate finding counts. (2) `.github/workflows/dast-benchmark.yml`: a `workflow_dispatch` workflow with one job per benchmark target (`juice-shop`, `vampi`), each declaring that target's official Docker image as a service container, running ZAP against it, and wiring the normalization script in as a conditional step.

**Tech Stack:** Python 3.11+ (via `uv`), PyYAML (already a project dependency, reused here for workflow-structure tests), GitHub Actions (`workflow_dispatch`, `services:`, `actions/upload-artifact@v4`), Docker (`zaproxy/zap-stable` image), pytest.

## Global Constraints

- This project uses `uv` for all Python package management — every command in this plan uses `uv run ...`, never bare `pip`/`python -m pip`.
- Python >=3.11, matching the existing `core` package's `pyproject.toml`.
- No placeholder/TODO code — every step's code is complete and runnable as written.
- Verified external references (checked 2026-07-11, do not treat as guesses): Juice Shop's official Docker image is `bkimminich/juice-shop` (port 3000); VAmPI's official Docker image is `erev0s/vampi:latest` (port 5000), and its vulnerabilities are only active when the container is run with the environment variable `vulnerable=1` (the image's own Dockerfile defaults to this, but the workflow sets it explicitly rather than relying on an undocumented default); ZAP's official Docker image is `zaproxy/zap-stable`, and `zap-full-scan.py -J <path>` is the correct, documented flag for writing a JSON report.
- `zap-full-scan.py` exits non-zero whenever it finds alerts at or above its warn threshold — this is normal, expected behavior for a benchmark target with deliberately planted vulnerabilities, not a failure. Every invocation of it in the workflow must be followed by `|| true` so a successful, vulnerability-finding scan does not fail the job.
- The normalization script must never silently emit an empty or partial findings array on unrecognized input — it must exit non-zero with a message prefixed `error:` on stderr. A silent empty result would be indistinguishable from "the tool found nothing," corrupting the scorecard with a false negative (see the design doc's Error Handling section).
- Out of scope for this plan (per the design doc): the `dast-handson` Claude Code skill itself, production-safe scanning, and any change to the existing `core` package — this plan only adds new, independent files.
- Existing project test suite (`core` package, 45 tests as of the last commit) must continue passing unmodified; this plan does not touch it.

---

### Task 1: ZAP report normalization script

**Files:**
- Create: `.github/scripts/normalize/zap.py`
- Test: `tests/test_normalize_zap.py`

**Interfaces:**
- Consumes: nothing — a standalone script with no dependency on the `core` package.
- Produces: a CLI script invoked as `python .github/scripts/normalize/zap.py <raw_report_path> <output_path>`. On success (exit 0), writes a JSON array of `{"vuln_id": str, "severity": str, "description": str}` objects to `<output_path>` — this is the exact shape the existing `core` CLI's `handson ingest-scan-result --file` command consumes. On any unreadable file, malformed JSON, or unrecognized report structure, writes nothing to `<output_path>`, prints a message starting with `error:` to stderr, and exits non-zero. Reused by Task 2's workflow, which invokes this script as a step.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_normalize_zap.py -v`
Expected: FAIL — every test errors because `.github/scripts/normalize/zap.py` does not exist yet (Python reports `can't open file '.../.github/scripts/normalize/zap.py': [Errno 2] No such file or directory` on stderr, non-zero exit, so `result.returncode == 0` assertions fail).

- [ ] **Step 3: Implement `.github/scripts/normalize/zap.py`**

```python
#!/usr/bin/env python3
"""Normalize a ZAP JSON report into the generic ingest-scan-result findings shape."""
from __future__ import annotations

import json
import sys

_RISK_CODE_TO_SEVERITY = {
    "0": "informational",
    "1": "low",
    "2": "medium",
    "3": "high",
}


def _severity_from_riskcode(riskcode) -> str:
    return _RISK_CODE_TO_SEVERITY.get(str(riskcode), "unknown")


def normalize_zap_report(raw: dict) -> list[dict]:
    if not isinstance(raw, dict) or not isinstance(raw.get("site"), list):
        raise ValueError("unrecognized ZAP report format: expected an object with a 'site' array")

    findings = []
    seen_plugin_ids = set()
    for site in raw["site"]:
        if not isinstance(site, dict):
            raise ValueError("unrecognized ZAP report format: 'site' entries must be objects")
        for alert in site.get("alerts", []):
            if not isinstance(alert, dict):
                raise ValueError("unrecognized ZAP report format: 'alerts' entries must be objects")
            plugin_id = alert.get("pluginid")
            if not plugin_id or plugin_id in seen_plugin_ids:
                continue
            seen_plugin_ids.add(plugin_id)
            instance_count = len(alert.get("instances") or [])
            name = alert.get("name", "Unknown")
            plural = "occurrences" if instance_count != 1 else "occurrence"
            findings.append(
                {
                    "vuln_id": str(plugin_id),
                    "severity": _severity_from_riskcode(alert.get("riskcode")),
                    "description": f"{name} ({instance_count} {plural})",
                }
            )
    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("error: usage: zap.py <raw_report_path> <output_path>", file=sys.stderr)
        return 1

    raw_path, output_path = argv[1], argv[2]

    try:
        with open(raw_path) as f:
            raw = json.load(f)
    except OSError as e:
        print(f"error: failed to read raw report '{raw_path}': {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"error: failed to parse raw report '{raw_path}' as JSON: {e}", file=sys.stderr)
        return 1

    try:
        findings = normalize_zap_report(raw)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    with open(output_path, "w") as f:
        json.dump(findings, f, indent=2)
    print(f"wrote {len(findings)} normalized finding(s) to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_normalize_zap.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/normalize/zap.py tests/test_normalize_zap.py
git commit -m "Add ZAP report normalization script for the benchmark CI pipeline"
```

---

### Task 2: DAST benchmark GitHub Actions workflow

**Files:**
- Create: `.github/workflows/dast-benchmark.yml`
- Test: `tests/test_dast_benchmark_workflow.py`

**Interfaces:**
- Consumes: `.github/scripts/normalize/zap.py` (Task 1) — referenced by path in a workflow step's `run:` command; the workflow does not need the script to actually execute successfully for this task's tests, which validate workflow structure, not live execution (see Testing note below).
- Produces: `.github/workflows/dast-benchmark.yml`, a `workflow_dispatch`-triggered pipeline with jobs `juice-shop` and `vampi`, each gated on the `target` input and declaring the appropriate service container. No other task consumes this file programmatically — it is triggered externally via `gh workflow run` once merged to the repository's default branch (GitHub Actions only picks up `workflow_dispatch` workflows that exist on the branch you're targeting).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dast_benchmark_workflow.py -v`
Expected: FAIL with `FileNotFoundError` (or similar) because `.github/workflows/dast-benchmark.yml` does not exist yet.

- [ ] **Step 3: Implement `.github/workflows/dast-benchmark.yml`**

Note the `"on":` key is deliberately quoted — PyYAML's `safe_load` (YAML 1.1 semantics) parses a bare `on:` key as the Python boolean `True`, not the string `"on"`, which would silently break every test above that does `workflow["on"]`. Quoting it as `"on":` is valid, standard YAML that GitHub Actions parses identically to the bare form, and it keeps the structure test straightforward.

```yaml
"on":
  workflow_dispatch:
    inputs:
      tool:
        description: "DAST tool to run"
        required: true
        type: choice
        options:
          - zap
      target:
        description: "Benchmark target to scan"
        required: true
        type: choice
        options:
          - juice-shop
          - vampi

jobs:
  juice-shop:
    if: inputs.target == 'juice-shop'
    runs-on: ubuntu-latest
    services:
      target:
        image: bkimminich/juice-shop
        ports:
          - 3000:3000
    steps:
      - uses: actions/checkout@v4

      - name: Wait for target to become healthy
        run: |
          for i in $(seq 1 30); do
            if curl -sf http://localhost:3000 > /dev/null; then
              echo "target healthy"
              exit 0
            fi
            sleep 2
          done
          echo "target did not become healthy in time" >&2
          exit 1

      - name: Run ZAP full scan
        run: |
          docker run --network host -v "$(pwd)":/zap/wrk/:rw \
            zaproxy/zap-stable zap-full-scan.py \
            -t http://localhost:3000 -J raw-report.json || true

      - name: Upload raw report
        uses: actions/upload-artifact@v4
        with:
          name: raw-report-${{ inputs.tool }}-${{ inputs.target }}
          path: raw-report.json

      - name: Normalize report
        if: inputs.tool == 'zap'
        run: python .github/scripts/normalize/zap.py raw-report.json normalized.json

      - name: Upload normalized report
        if: inputs.tool == 'zap'
        uses: actions/upload-artifact@v4
        with:
          name: normalized-${{ inputs.tool }}-${{ inputs.target }}
          path: normalized.json

  vampi:
    if: inputs.target == 'vampi'
    runs-on: ubuntu-latest
    services:
      target:
        image: erev0s/vampi:latest
        ports:
          - 5000:5000
        env:
          vulnerable: "1"
    steps:
      - uses: actions/checkout@v4

      - name: Wait for target to become healthy
        run: |
          for i in $(seq 1 30); do
            if curl -sf http://localhost:5000 > /dev/null; then
              echo "target healthy"
              exit 0
            fi
            sleep 2
          done
          echo "target did not become healthy in time" >&2
          exit 1

      - name: Run ZAP full scan
        run: |
          docker run --network host -v "$(pwd)":/zap/wrk/:rw \
            zaproxy/zap-stable zap-full-scan.py \
            -t http://localhost:5000 -J raw-report.json || true

      - name: Upload raw report
        uses: actions/upload-artifact@v4
        with:
          name: raw-report-${{ inputs.tool }}-${{ inputs.target }}
          path: raw-report.json

      - name: Normalize report
        if: inputs.tool == 'zap'
        run: python .github/scripts/normalize/zap.py raw-report.json normalized.json

      - name: Upload normalized report
        if: inputs.tool == 'zap'
        uses: actions/upload-artifact@v4
        with:
          name: normalized-${{ inputs.tool }}-${{ inputs.target }}
          path: normalized.json
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dast_benchmark_workflow.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass — the 45 pre-existing `core` package tests plus this plan's 9 new tests (4 from Task 1, 5 from Task 2), 54 passed, zero failures.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/dast-benchmark.yml tests/test_dast_benchmark_workflow.py
git commit -m "Add DAST benchmark GitHub Actions workflow for Juice Shop and VAmPI"
```

- [ ] **Step 7: Note for manual verification (not automatable in this environment)**

The tests above validate the workflow's structure (correct inputs, correct service images/ports/env, correct conditional wiring) but cannot execute a real GitHub Actions run from this sandboxed environment. Once this plan's commits are merged to the repository's default branch, the evaluator should manually dispatch it once against each target to confirm live end-to-end behavior before relying on it for real hands-on testing:

```bash
gh workflow run dast-benchmark.yml -f tool=zap -f target=juice-shop
gh workflow run dast-benchmark.yml -f tool=zap -f target=vampi
```

Then, for each run, confirm both the `raw-report-*` and `normalized-*` artifacts were produced and that the normalized JSON contains at least one finding (Juice Shop and VAmPI both have numerous discoverable vulnerabilities, so an empty findings array on a real run would indicate something is wrong — e.g. the target never became reachable, or ZAP's report format has drifted from what `zap.py` expects).

---

## Self-Review Notes

- **Spec coverage:** the design doc's Components section names four things — the workflow, the normalization script, the (unmodified) `ingest-scan-result` command, and the roadmap doc. The roadmap doc and `ingest-scan-result` are already done (prior work); Tasks 1–2 here cover the two new artifacts. The Data Flow, Error Handling, and Testing sections of the design doc are covered by: Task 1 (dedup by `pluginid`, non-zero exit on unrecognized shape, unit tests including the error path) and Task 2 (raw report always uploaded regardless of normalization outcome via step ordering, `|| true` on the ZAP invocation, structural workflow tests, and the manual-verification note acknowledging what automated tests in this environment cannot cover).
- **Placeholder scan:** no TODO/TBD markers; every step has complete, runnable code, including the full normalization script and the full workflow YAML.
- **Type consistency:** the normalization script's output shape (`vuln_id`/`severity`/`description` string keys) matches exactly what `core.cli`'s `ingest-scan-result` command already expects (verified against the existing, already-implemented and already-tested command — no assumption, that command's shape was fixed during the core library's implementation). The script's CLI argument order (`<raw_report_path> <output_path>`) is used identically in both the workflow's `run:` step and every test's subprocess invocation.
