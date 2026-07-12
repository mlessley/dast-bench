#!/usr/bin/env python3
"""Normalize a Nuclei JSONL report into the generic ingest-scan-result findings shape."""
from __future__ import annotations

import json
import sys


def normalize_nuclei_report(raw_lines: list[str]) -> list[dict]:
    findings = []
    seen_template_ids = set()
    for line_no, line in enumerate(raw_lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            finding = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"unrecognized Nuclei report format: invalid JSON on line {line_no}: {e}")
        if not isinstance(finding, dict):
            raise ValueError(f"unrecognized Nuclei report format: line {line_no} must be a JSON object")
        template_id = finding.get("template-id")
        if not template_id or template_id in seen_template_ids:
            continue
        seen_template_ids.add(template_id)
        info = finding.get("info")
        if not isinstance(info, dict):
            raise ValueError(f"unrecognized Nuclei report format: line {line_no} missing 'info' object")
        severity = info.get("severity", "unknown")
        name = info.get("name", "Unknown")
        matched_at = finding.get("matched-at", "")
        description = f"{name} ({matched_at})" if matched_at else name
        findings.append({"vuln_id": str(template_id), "severity": severity, "description": description})
    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("error: usage: nuclei.py <raw_report_path> <output_path>", file=sys.stderr)
        return 1

    raw_path, output_path = argv[1], argv[2]

    try:
        with open(raw_path) as f:
            raw_lines = f.readlines()
    except OSError as e:
        print(f"error: failed to read raw report '{raw_path}': {e}", file=sys.stderr)
        return 1

    try:
        findings = normalize_nuclei_report(raw_lines)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    with open(output_path, "w") as f:
        json.dump(findings, f, indent=2)
    print(f"wrote {len(findings)} normalized finding(s) to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
