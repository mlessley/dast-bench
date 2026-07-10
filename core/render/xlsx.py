from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from ..models import CriteriaTaxonomy, Vendor
from .markdown import weighted_score


def write_xlsx(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Comparison"
    ws.append(["Criterion", "Category", "Weight"] + [v.name for v in vendors])
    for criterion in taxonomy.criteria:
        row = [criterion.name, criterion.category, criterion.weight]
        for v in vendors:
            entry = v.score_for(criterion.id)
            row.append(entry.score if entry else None)
        ws.append(row)
    ws.append(["Weighted Total", "", ""] + [round(weighted_score(taxonomy, v), 2) for v in vendors])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
