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
