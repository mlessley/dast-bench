from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Protection

from .models import Vendor
from .render.stakeholder_workbook import FIRST_DATA_ROW, HEADER_ROW, stakeholder_headers


def _column_map(ws) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for cell in ws[HEADER_ROW]:
        if cell.value:
            mapping[cell.value] = cell.column_letter
    return mapping


def populate(vendor: Vendor, file_path: Path) -> str:
    wb = load_workbook(file_path)
    sheet_name = vendor.id[:31]
    if sheet_name not in wb.sheetnames:
        return f"error: vendor '{vendor.id}' has no sheet in {file_path}"
    ws = wb[sheet_name]
    cols = _column_map(ws)
    crit_id_col = cols["_criterion_id"]
    pending_col = cols["_pending"]
    score_col = cols["Automated Score"]
    evidence_col = cols["Automated Evidence"]
    confidence_col = cols["Automated Confidence"]

    filled = 0
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        criterion_id = ws[f"{crit_id_col}{row}"].value
        if not criterion_id:
            continue
        if ws[f"{pending_col}{row}"].value != 1:
            continue
        entry = vendor.score_for(criterion_id)
        if entry is None:
            continue
        ws[f"{score_col}{row}"] = entry.score
        ws[f"{evidence_col}{row}"] = entry.evidence
        ws[f"{confidence_col}{row}"] = entry.confidence.value
        ws[f"{pending_col}{row}"] = 0
        for header in cols:
            if header.endswith(" Score") and header != "Automated Score" and header != "Resolved Score":
                ws[f"{cols[header]}{row}"].protection = Protection(locked=False)
        filled += 1

    wb.save(file_path)
    return f"populated {filled} pending row(s) for '{vendor.id}'"
