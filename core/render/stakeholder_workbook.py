from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from ..models import CriteriaTaxonomy, Vendor, VendorResearchCache

SCORE_VALUES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
_PENDING_TEXT = (
    "Pending — dast-scan results not yet available. "
    "Do not edit; will be populated in Round 2."
)
_BASE_HEADERS = [
    "Criterion",
    "Category",
    "Weight",
    "Automated Score",
    "Automated Evidence",
    "Automated Confidence",
]
_RESOLUTION_HEADERS = ["Resolved Score", "Resolved By", "Resolved Timestamp", "Automated vs. Resolved Delta"]
_HIDDEN_HEADERS = ["_criterion_id", "_pending", "_effective_score"]

HEADER_ROW = 3
FIRST_DATA_ROW = 4


def compute_priority_order(
    taxonomy: CriteriaTaxonomy, vendor: Vendor, research_cache: VendorResearchCache
) -> list[str]:
    def sort_key(criterion):
        entry = vendor.score_for(criterion.id)
        score = entry.score if entry else 0.0
        cache_entry = research_cache.criteria.get(criterion.id)
        gap_checked = cache_entry.reviewed_by_gap_check if cache_entry else False
        needs_attention = score <= 2.5 or gap_checked
        return (-criterion.weight, 0 if needs_attention else 1, criterion.id)

    return [c.id for c in sorted(taxonomy.criteria, key=sort_key)]


def stakeholder_headers(stakeholders: list[tuple[str | None, str]]) -> list[str]:
    headers: list[str] = []
    for name, role in stakeholders:
        label = f"{name} ({role})" if name else role
        headers += [f"{label} Score", f"{label} Dispute?", f"{label} Rationale"]
    return headers


def _all_headers(stakeholders: list[tuple[str | None, str]]) -> list[str]:
    return _BASE_HEADERS + stakeholder_headers(stakeholders) + _RESOLUTION_HEADERS + _HIDDEN_HEADERS


def _column_index(headers: list[str], name: str) -> int:
    return headers.index(name) + 1


def generate_workbook(
    taxonomy: CriteriaTaxonomy,
    vendors: list[Vendor],
    stakeholders: list[tuple[str | None, str]],
    pending_criteria: dict[str, set[str]],
    research_caches: dict[str, VendorResearchCache],
    out_path: Path,
    top_tier_count: int = 10,
) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    headers = _all_headers(stakeholders)
    for vendor in vendors:
        ws = wb.create_sheet(title=vendor.id[:31])
        ws.append([])
        ws.append([])
        ws.append(headers)
        pending_for_vendor = pending_criteria.get(vendor.id, set())
        cache = research_caches.get(vendor.id) or VendorResearchCache(vendor_id=vendor.id)
        order = compute_priority_order(taxonomy, vendor, cache)
        for criterion_id in order:
            criterion = taxonomy.get(criterion_id)
            entry = vendor.score_for(criterion_id)
            is_pending = criterion_id in pending_for_vendor
            row = [criterion.name, criterion.category, criterion.weight]
            if is_pending:
                row += [None, _PENDING_TEXT, None]
            else:
                row += [entry.score if entry else None, entry.evidence if entry else None, entry.confidence.value if entry else None]
            row += [None] * len(stakeholder_headers(stakeholders))
            row += [None, None, None, None]  # resolution columns
            row += [criterion_id, 1 if is_pending else 0, None]  # hidden columns
            ws.append(row)
        for hidden_name in _HIDDEN_HEADERS:
            ws.column_dimensions[get_column_letter(_column_index(headers, hidden_name))].hidden = True
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
