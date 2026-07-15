from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ..models import CriteriaTaxonomy, Vendor, VendorResearchCache
from .markdown import _ordered_categories

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

_TIER_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
_UNFILLED_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")

_HEADER_FILL_COLOR = "1F4E78"
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color=_HEADER_FILL_COLOR, end_color=_HEADER_FILL_COLOR, fill_type="solid")
_HEADER_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

_FIXED_COLUMN_WIDTHS = {
    "Criterion": 32,
    "Category": 16,
    "Weight": 10,
    "Automated Score": 14,
    "Automated Evidence": 45,
    "Automated Confidence": 16,
    "Resolved Score": 14,
    "Resolved By": 16,
    "Resolved Timestamp": 18,
    "Automated vs. Resolved Delta": 14,
}
_COLUMN_WIDTHS_BY_SUFFIX = [
    (" Rationale", 40),
    (" Dispute?", 12),
    (" Score", 12),
]


def _column_width_for(header: str) -> float | None:
    if header in _FIXED_COLUMN_WIDTHS:
        return _FIXED_COLUMN_WIDTHS[header]
    for suffix, width in _COLUMN_WIDTHS_BY_SUFFIX:
        if header.endswith(suffix):
            return width
    return None


_BAND_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
_ROLLUP_BORDER = Border(top=Side(style="medium"))

_RIGHT_ALIGN_NUMERIC_HEADERS_EXACT = {"Weight", "Automated vs. Resolved Delta"}
_RIGHT_ALIGN_NUMERIC_HEADERS_SUFFIX = " Score"

_TAB_COLOR_PALETTE = ["2E86AB", "A23B72", "F18F01", "C73E1D", "3B1F2B", "6A994E"]


def _tab_color_for(index: int) -> str:
    return _TAB_COLOR_PALETTE[index % len(_TAB_COLOR_PALETTE)]


def _is_right_aligned_numeric(header_name: str) -> bool:
    return (
        header_name in _RIGHT_ALIGN_NUMERIC_HEADERS_EXACT
        or header_name.endswith(_RIGHT_ALIGN_NUMERIC_HEADERS_SUFFIX)
    )


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
    for vendor_index, vendor in enumerate(vendors):
        ws = wb.create_sheet(title=vendor.id[:31])
        ws.sheet_properties.tabColor = _tab_color_for(vendor_index)
        ws.append(["Provisional — ranking may shift once pending dast-scan results land."])
        ws.append([])
        ws.append(headers)
        ws.freeze_panes = "C4"
        for col_idx, header_name in enumerate(headers, start=1):
            width = _column_width_for(header_name)
            if width is not None:
                ws.column_dimensions[get_column_letter(col_idx)].width = width
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=HEADER_ROW, column=col_idx)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.border = _HEADER_BORDER
            cell.alignment = _HEADER_ALIGNMENT
        pending_for_vendor = pending_criteria.get(vendor.id, set())
        cache = research_caches.get(vendor.id) or VendorResearchCache(vendor_id=vendor.id)
        order = compute_priority_order(taxonomy, vendor, cache)

        score_cols = [
            _column_index(headers, h) for h in stakeholder_headers(stakeholders) if h.endswith(" Score")
        ] + [_column_index(headers, "Resolved Score")]

        dv = DataValidation(
            type="list",
            formula1='"' + ",".join(str(v) for v in SCORE_VALUES) + '"',
            allow_blank=True,
        )
        ws.add_data_validation(dv)

        for i, criterion_id in enumerate(order):
            row_num = FIRST_DATA_ROW + i
            criterion = taxonomy.get(criterion_id)
            entry = vendor.score_for(criterion_id)
            is_pending = criterion_id in pending_for_vendor
            row = [criterion.name, criterion.category, criterion.weight]
            if is_pending:
                row += [None, _PENDING_TEXT, None]
            else:
                row += [entry.score if entry else None, entry.evidence if entry else None, entry.confidence.value if entry else None]
            row += [None] * len(stakeholder_headers(stakeholders))
            row += [None, None, None, None]
            row += [criterion_id, 1 if is_pending else 0, None]
            ws.append(row)

            if i < top_tier_count:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _TIER_FILL
            elif i % 2 == 1:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col).fill = _BAND_FILL

            for col_idx, header_name in enumerate(headers, start=1):
                if header_name in _HIDDEN_HEADERS:
                    continue
                cell = ws.cell(row=row_num, column=col_idx)
                if _is_right_aligned_numeric(header_name):
                    cell.number_format = "0.0"
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.alignment = Alignment(horizontal="left")

            for col in score_cols:
                cell = ws.cell(row=row_num, column=col)
                cell.protection = Protection(locked=is_pending)
                dv.add(cell)
                if i < top_tier_count:
                    ws.conditional_formatting.add(
                        cell.coordinate,
                        CellIsRule(operator="equal", formula=['""'], fill=_UNFILLED_FILL),
                    )

            editable_non_score_cols = [
                _column_index(headers, h) for h in stakeholder_headers(stakeholders) if not h.endswith(" Score")
            ] + [_column_index(headers, h) for h in ("Resolved By", "Resolved Timestamp")]
            for col in editable_non_score_cols:
                ws.cell(row=row_num, column=col).protection = Protection(locked=is_pending)

        resolved_col_letter = get_column_letter(_column_index(headers, "Resolved Score"))
        automated_col_letter = get_column_letter(_column_index(headers, "Automated Score"))
        effective_col_letter = get_column_letter(_column_index(headers, "_effective_score"))
        pending_col_letter = get_column_letter(_column_index(headers, "_pending"))
        weight_col_letter = get_column_letter(_column_index(headers, "Weight"))
        category_col_letter = get_column_letter(_column_index(headers, "Category"))
        delta_col = _column_index(headers, "Automated vs. Resolved Delta")
        effective_col = _column_index(headers, "_effective_score")
        last_data_row = FIRST_DATA_ROW + len(order) - 1

        for row_num in range(FIRST_DATA_ROW, last_data_row + 1):
            resolved_ref = f"{resolved_col_letter}{row_num}"
            automated_ref = f"{automated_col_letter}{row_num}"
            ws.cell(row=row_num, column=effective_col).value = f"=IF(ISBLANK({resolved_ref}),{automated_ref},{resolved_ref})"
            ws.cell(row=row_num, column=delta_col).value = f'=IF(ISBLANK({resolved_ref}),"",{resolved_ref}-{automated_ref})'

        def _points_formulas(category_filter: str | None) -> tuple[str, str]:
            weight_range = f"{weight_col_letter}{FIRST_DATA_ROW}:{weight_col_letter}{last_data_row}"
            effective_range = f"{effective_col_letter}{FIRST_DATA_ROW}:{effective_col_letter}{last_data_row}"
            pending_range = f"{pending_col_letter}{FIRST_DATA_ROW}:{pending_col_letter}{last_data_row}"
            if category_filter is None:
                achieved = f"=SUMPRODUCT({weight_range},{effective_range},(1-{pending_range}))/5"
                available = f"=SUMPRODUCT({weight_range},(1-{pending_range}))"
            else:
                category_range = f"{category_col_letter}{FIRST_DATA_ROW}:{category_col_letter}{last_data_row}"
                achieved = f'=SUMPRODUCT(({category_range}=\"{category_filter}\")*{weight_range}*{effective_range}*(1-{pending_range}))/5'
                available = f'=SUMPRODUCT(({category_range}=\"{category_filter}\")*{weight_range}*(1-{pending_range}))'
            return achieved, available

        weight_header_col = _column_index(headers, "Weight")
        evidence_header_col = _column_index(headers, "Automated Evidence")
        score_header_col = _column_index(headers, "Automated Score")

        def _write_rollup_row(label: str, category_filter: str | None) -> None:
            ws.append([label] + [None] * (len(headers) - 1))
            r = ws.max_row
            achieved_formula, available_formula = _points_formulas(category_filter)
            ws.cell(row=r, column=weight_header_col).value = achieved_formula
            ws.cell(row=r, column=evidence_header_col).value = available_formula
            weight_ref = f"{weight_col_letter}{r}"
            evidence_ref = f"{get_column_letter(evidence_header_col)}{r}"
            ws.cell(row=r, column=score_header_col).value = (
                f'=TEXT({weight_ref},"0.0")&"/"&TEXT({evidence_ref},"0")&" available points"'
            )

        ws.append([])
        first_rollup_row = last_data_row + 2
        for category in _ordered_categories(taxonomy):
            _write_rollup_row(category, category)
        _write_rollup_row("Weighted Total", None)
        for col in range(1, len(headers) + 1):
            ws.cell(row=first_rollup_row, column=col).border = _ROLLUP_BORDER

        for hidden_name in _HIDDEN_HEADERS:
            ws.column_dimensions[get_column_letter(_column_index(headers, hidden_name))].hidden = True
        ws.protection.sheet = True
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
