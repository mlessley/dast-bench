# Stakeholder Review Workbook (Code) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the xlsx generation, populate/merge/validate/snapshot
logic, and CLI wiring for the stakeholder review workbook described in
`docs/superpowers/specs/2026-07-15-stakeholder-review-workbook-design.md`.

**Architecture:** Two new modules alongside the existing `core/render/`
package: `core/render/stakeholder_workbook.py` (priority ordering +
`generate_workbook`, the "write" side) and `core/stakeholder_review.py`
(`populate`/`merge`/`validate_workbook`/`snapshot`, the "read and modify
an already-generated file" side). Both operate on plain `.xlsx` files via
`openpyxl` — no new Pydantic models, no new YAML storage. A new
`stakeholder_review_app` Typer sub-app in `core/cli.py` exposes all five
operations as `dast-bench stakeholder-review <command>`.

**Tech Stack:** Python, `openpyxl` (already a project dependency, used by
`core/render/xlsx.py`), `typer` (already used throughout `core/cli.py`),
`pytest`.

## Global Constraints

- No new Pydantic models or YAML storage — read `CriteriaTaxonomy`,
  `Vendor`, `VendorResearchCache` as they exist today in `core/models.py`.
- No Excel macros or add-ins — every computed value is a native formula
  or a plain value written by Python; no VBA.
- Valid score values are exactly: `1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0`.
- Every new CLI command relays failures via `typer.echo(f"error: ...")` +
  `raise typer.Exit(code=1)`, matching every existing command in
  `core/cli.py`.
- Rows must be addressable by a criterion's `criterion_id`, not visual
  row position, everywhere `populate`/`merge`/`validate` look up a row.

---

## File Structure

- Create: `core/render/stakeholder_workbook.py` — `compute_priority_order`,
  `generate_workbook`, and the column-layout helpers both this file and
  `core/stakeholder_review.py` need (header label constants, hidden
  column names).
- Create: `core/stakeholder_review.py` — `populate`, `merge`,
  `validate_workbook`, `snapshot`, and a shared `_column_map` helper that
  reads a sheet's header row back into a `{header_text: column_letter}`
  dict (so every operation finds columns by label, never a hardcoded
  letter, and survives the sheet being resorted/filtered by a
  stakeholder).
- Modify: `core/cli.py` — add a new `stakeholder_review_app` Typer
  sub-app with `generate`, `populate`, `merge`, `validate`, `snapshot`
  commands, mounted as `dast-bench stakeholder-review`.
- Test: `tests/test_stakeholder_workbook.py`
- Test: `tests/test_stakeholder_review.py`
- Test: `tests/test_cli_stakeholder_review.py`

---

### Task 1: Priority-order computation

**Files:**
- Create: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `CriteriaTaxonomy`, `Vendor`, `VendorResearchCache` from
  `core.models` (all exist today — see Global Constraints).
- Produces: `compute_priority_order(taxonomy: CriteriaTaxonomy, vendor:
  Vendor, research_cache: VendorResearchCache) -> list[str]` — a list of
  `criterion_id` strings in priority order. Task 2 imports and calls this.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stakeholder_workbook.py
from core.models import (
    Confidence,
    Criterion,
    CriteriaTaxonomy,
    CriterionResearchCache,
    ScoreEntry,
    Vendor,
    VendorResearchCache,
    VendorSource,
)
from core.render.stakeholder_workbook import compute_priority_order


def _taxonomy():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="low-weight", category="Cat", name="Low Weight", description="d", weight=5, rubric="r"),
            Criterion(id="high-weight-confident", category="Cat", name="High Confident", description="d", weight=20, rubric="r"),
            Criterion(id="high-weight-shaky", category="Cat", name="High Shaky", description="d", weight=20, rubric="r"),
        ]
    )


def _vendor():
    vendor = Vendor(id="v1", name="V1", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="low-weight", score=5.0, evidence="e", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="high-weight-confident", score=4.5, evidence="e", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="high-weight-shaky", score=2.0, evidence="e", confidence=Confidence.PAPER))
    return vendor


def test_priority_order_sorts_by_weight_then_needs_attention():
    taxonomy = _taxonomy()
    vendor = _vendor()
    cache = VendorResearchCache(vendor_id="v1")
    order = compute_priority_order(taxonomy, vendor, cache)
    # both weight-20 criteria outrank the weight-5 one; within the
    # weight-20 band, the low-scoring (<=2.5) one sorts first
    assert order == ["high-weight-shaky", "high-weight-confident", "low-weight"]


def test_priority_order_pulls_up_gap_checked_criteria_even_with_high_score():
    taxonomy = _taxonomy()
    vendor = _vendor()
    vendor.scores[-1] = ScoreEntry(criterion_id="high-weight-shaky", score=4.5, evidence="e", confidence=Confidence.PAPER)
    cache = VendorResearchCache(
        vendor_id="v1",
        criteria={"high-weight-shaky": CriterionResearchCache(reviewed_by_gap_check=True)},
    )
    order = compute_priority_order(taxonomy, vendor, cache)
    assert order == ["high-weight-shaky", "high-weight-confident", "low-weight"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.render.stakeholder_workbook'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/render/stakeholder_workbook.py
from __future__ import annotations

from ..models import CriteriaTaxonomy, Vendor, VendorResearchCache


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add stakeholder-review priority-order computation"
```

---

### Task 2: Base workbook generation (sheets, columns, hidden criterion_id, pending placeholders)

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `compute_priority_order` from Task 1.
- Produces:
  - Module constants: `SCORE_VALUES: list[float]`, `_PENDING_TEXT: str`,
    `_BASE_HEADERS: list[str]`, `_RESOLUTION_HEADERS: list[str]`,
    `HEADER_ROW: int = 3`, `FIRST_DATA_ROW: int = 4`.
  - `stakeholder_headers(stakeholders: list[tuple[str | None, str]]) ->
    list[str]` — one triple of headers
    (`f"{label} Score"`/`f"{label} Dispute?"`/`f"{label} Rationale"`) per
    stakeholder, where `label` is `f"{name} ({role})"` if `name` is set
    else just `role`.
  - `generate_workbook(taxonomy: CriteriaTaxonomy, vendors: list[Vendor],
    stakeholders: list[tuple[str | None, str]], pending_criteria:
    dict[str, set[str]], research_caches: dict[str, VendorResearchCache],
    out_path: Path, top_tier_count: int = 10) -> None` — Task 3 (native
    Excel constraints) and Task 4 (formulas) both extend this same
    function's sheet-building loop; Task 6 (`populate`) and Task 7
    (`merge`) read the sheets this produces via the hidden
    `_criterion_id`/`_pending` columns and the header row.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stakeholder_workbook.py -- add to the existing file
from pathlib import Path

from openpyxl import load_workbook

from core.render.stakeholder_workbook import generate_workbook


def _taxonomy_two_criteria():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="Coverage One", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="DX One", description="d", weight=40, rubric="r"),
        ]
    )


def _vendor_two_criteria(vendor_id="v1", name="Vendor One"):
    vendor = Vendor(id=vendor_id, name=name, source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="ev2", confidence=Confidence.PAPER))
    return vendor


def test_generate_workbook_writes_one_sheet_per_vendor_with_headers(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[("Jane Doe", "DAST SME"), (None, "Dev Lead")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    wb = load_workbook(out_path)
    assert wb.sheetnames == ["v1"]
    ws = wb["v1"]
    header = [c.value for c in ws[3]]
    assert header[:6] == ["Criterion", "Category", "Weight", "Automated Score", "Automated Evidence", "Automated Confidence"]
    assert "Jane Doe (DAST SME) Score" in header
    assert "Jane Doe (DAST SME) Dispute?" in header
    assert "Jane Doe (DAST SME) Rationale" in header
    assert "Dev Lead Score" in header
    assert "Resolved Score" in header
    assert "Resolved By" in header
    assert "Resolved Timestamp" in header
    assert "_criterion_id" in header


def test_generate_workbook_orders_rows_by_priority_and_fills_automated_data(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_col = header.index("Criterion") + 1
    score_col = header.index("Automated Score") + 1
    crit_id_col = header.index("_criterion_id") + 1
    # c2 (weight 40, score 2.0 <= 2.5) outranks c1 (weight 60, score 4.0)
    # under the priority rule -- wait: weight sorts first, so c1 (60)
    # comes before c2 (40) here since neither ties on weight.
    assert ws.cell(row=4, column=crit_col).value == "Coverage One"
    assert ws.cell(row=4, column=score_col).value == 4.0
    assert ws.cell(row=4, column=crit_id_col).value == "c1"
    assert ws.cell(row=5, column=crit_id_col).value == "c2"


def test_generate_workbook_marks_pending_criteria_with_placeholder_and_no_automated_data(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    score_col = header.index("Automated Score") + 1
    evidence_col = header.index("Automated Evidence") + 1
    crit_id_col = header.index("_criterion_id") + 1
    pending_col = header.index("_pending") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    assert ws.cell(row=row, column=pending_col).value == 1
    assert "Pending" in ws.cell(row=row, column=evidence_col).value
    assert ws.cell(row=row, column=score_col).value is None
    non_pending_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    assert ws.cell(row=non_pending_row, column=pending_col).value == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: FAIL — `ImportError: cannot import name 'generate_workbook'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/render/stakeholder_workbook.py -- replace the file's contents with this
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: generate base stakeholder-review workbook structure"
```

---

### Task 3: Native Excel constraints (data validation, tier fill, conditional formatting, pending-row locking)

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: `generate_workbook`'s sheet-building loop from Task 2.
- Produces: no new public functions — `generate_workbook`'s output gains
  data validation objects, a tier fill color on the top
  `top_tier_count` rows, conditional formatting on stakeholder score
  columns, and cell protection (locked stakeholder cells on pending
  rows, unlocked everywhere else) plus `ws.protection.sheet = True`.
  Task 4 builds on the same per-row loop to add formulas; Task 6
  (`populate`) relies on pending rows being locked here so it can
  correctly unlock them later.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stakeholder_workbook.py -- add to the existing file
def test_generate_workbook_adds_score_data_validation_and_locks_pending_rows(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    assert len(ws.data_validations.dataValidation) >= 1
    score_col = header.index("DAST SME Score") + 1
    crit_id_col = header.index("_criterion_id") + 1
    pending_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    non_pending_row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    assert ws.cell(row=pending_row, column=score_col).protection.locked is True
    assert ws.cell(row=non_pending_row, column=score_col).protection.locked is False
    assert ws.protection.sheet is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: FAIL — pending row's score cell is locked True by openpyxl's
default (not yet distinguished from non-pending), so the
`non_pending_row` assertion fails.

- [ ] **Step 3: Write minimal implementation**

```python
# core/render/stakeholder_workbook.py -- modify generate_workbook
# add these imports at the top of the file:
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

_TIER_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
_UNFILLED_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")

# inside generate_workbook, replace the vendor loop body with:
    for vendor in vendors:
        ws = wb.create_sheet(title=vendor.id[:31])
        ws.append([])
        ws.append([])
        ws.append(headers)
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

        for hidden_name in _HIDDEN_HEADERS:
            ws.column_dimensions[get_column_letter(_column_index(headers, hidden_name))].hidden = True
        ws.protection.sheet = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add data validation, tier fill, and pending-row locking to workbook"
```

---

### Task 4: Formulas (effective score, delta, category subtotals, grand total with partial-completeness)

**Files:**
- Modify: `core/render/stakeholder_workbook.py`
- Test: `tests/test_stakeholder_workbook.py`

**Interfaces:**
- Consumes: the per-row loop and column layout from Tasks 2–3.
- Produces: `generate_workbook`'s output gains, per data row, a formula
  in the hidden `_effective_score` column and in the visible
  `Automated vs. Resolved Delta` column; and, after the last data row, a
  blank row, one subtotal row per category (in `_ordered_categories`
  order — reuse the existing helper from `core/render/markdown.py`), and
  a final "Weighted Total" row. Each subtotal/total row's `Automated
  Score` cell shows `"<achieved>/<available> available points"` per the
  spec's partial-completeness rule.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stakeholder_workbook.py -- add to the existing file
def test_generate_workbook_writes_delta_formula_and_partial_completeness_total(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy_two_criteria()
    vendor = _vendor_two_criteria()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    delta_col = header.index("Automated vs. Resolved Delta") + 1
    crit_id_col = header.index("_criterion_id") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    delta_formula = ws.cell(row=row, column=delta_col).value
    assert delta_formula.startswith("=IF(ISBLANK(")

    total_row = ws.cell(row=ws.max_row, column=1).value
    assert total_row == "Weighted Total"
    total_score_cell = ws.cell(row=ws.max_row, column=header.index("Automated Score") + 1).value
    assert total_score_cell.startswith("=")
    assert "available points" in total_score_cell
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: FAIL — no delta formula written yet, no total row exists

- [ ] **Step 3: Write minimal implementation**

```python
# core/render/stakeholder_workbook.py
# add this import:
from .markdown import _ordered_categories

# inside generate_workbook, after the per-criterion `for i, criterion_id in enumerate(order):` loop body
# (still inside the `for vendor in vendors:` loop, after that inner loop finishes), add:

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
        for category in _ordered_categories(taxonomy):
            _write_rollup_row(category, category)
        _write_rollup_row("Weighted Total", None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_workbook.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add core/render/stakeholder_workbook.py tests/test_stakeholder_workbook.py
git commit -m "feat: add delta and partial-completeness rollup formulas to workbook"
```

---

### Task 5: `populate` — fill pending rows from current vendor data

**Files:**
- Create: `core/stakeholder_review.py`
- Test: `tests/test_stakeholder_review.py`

**Interfaces:**
- Consumes: the workbook structure and header labels
  (`_BASE_HEADERS`, `_RESOLUTION_HEADERS`, `_HIDDEN_HEADERS`,
  `HEADER_ROW`, `FIRST_DATA_ROW`, `_PENDING_TEXT`, `stakeholder_headers`)
  from `core.render.stakeholder_workbook` (Tasks 1–4). `Vendor` from
  `core.models`.
- Produces: a shared `_column_map(ws) -> dict[str, str]` helper (reads
  `ws[HEADER_ROW]`, maps each non-empty header string to its column
  letter) that Task 6 (`merge`) and Task 7 (`validate_workbook`) also
  import and reuse. `populate(vendor: Vendor, file_path: Path) -> str` —
  returns a one-line human-readable summary; Task 8's CLI `populate`
  command prints this directly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stakeholder_review.py
from openpyxl import load_workbook

from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorResearchCache, VendorSource
from core.render.stakeholder_workbook import generate_workbook
from core.stakeholder_review import populate


def _taxonomy():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="Coverage One", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="DX One", description="d", weight=40, rubric="r"),
        ]
    )


def _vendor_with_hands_on_c2():
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=1.0, evidence="paper guess", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=3.5, evidence="hands-on: 7/10 detected", confidence=Confidence.HANDS_ON))
    return vendor


def _generate_with_c2_pending(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy()
    vendor = _vendor_with_hands_on_c2()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    return out_path


def test_populate_fills_pending_row_and_unlocks_it(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    vendor = _vendor_with_hands_on_c2()
    summary = populate(vendor, out_path)
    assert "populated 1" in summary

    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    score_col = header.index("Automated Score") + 1
    evidence_col = header.index("Automated Evidence") + 1
    pending_col = header.index("_pending") + 1
    stakeholder_score_col = header.index("DAST SME Score") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    assert ws.cell(row=row, column=score_col).value == 3.5
    assert ws.cell(row=row, column=evidence_col).value == "hands-on: 7/10 detected"
    assert ws.cell(row=row, column=pending_col).value == 0
    assert ws.cell(row=row, column=stakeholder_score_col).protection.locked is False


def test_populate_leaves_stakeholder_entered_cells_untouched(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    score_col = header.index("DAST SME Score") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c1")
    ws.cell(row=row, column=score_col).value = 4.5
    wb = ws.parent
    wb.save(out_path)

    vendor = _vendor_with_hands_on_c2()
    populate(vendor, out_path)

    ws2 = load_workbook(out_path)["v1"]
    assert ws2.cell(row=row, column=score_col).value == 4.5


def test_populate_is_a_no_op_when_vendor_has_no_pending_rows(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy()
    vendor = _vendor_with_hands_on_c2()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    summary = populate(vendor, out_path)
    assert "populated 0" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.stakeholder_review'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/stakeholder_review.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/stakeholder_review.py tests/test_stakeholder_review.py
git commit -m "feat: add populate command for pending stakeholder-review rows"
```

---

### Task 6: `merge` — fold a returned copy's stakeholder columns into the master

**Files:**
- Modify: `core/stakeholder_review.py`
- Test: `tests/test_stakeholder_review.py`

**Interfaces:**
- Consumes: `_column_map` from Task 5.
- Produces: `merge(master_path: Path, from_path: Path) -> str` — a
  one-line summary (`"merged N cell(s), M invalid, K conflict(s),
  unrecognized: [...]"`). Task 8's CLI `merge` command prints this.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stakeholder_review.py -- add to the existing file
from core.stakeholder_review import merge


def _generate_two_stakeholders(tmp_path, filename="master.xlsx"):
    out_path = tmp_path / filename
    taxonomy = _taxonomy()
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="ev2", confidence=Confidence.PAPER))
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[("Jane Doe", "DAST SME"), (None, "Dev Lead")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    return out_path


def _row_for(ws, cols, criterion_id):
    crit_col = cols["_criterion_id"]
    for r in range(4, ws.max_row + 1):
        if ws[f"{crit_col}{r}"].value == criterion_id:
            return r
    raise AssertionError(f"row for {criterion_id} not found")


def test_merge_fills_blank_master_cells_from_a_valid_returned_copy(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{cols['Jane Doe (DAST SME) Score']}{row}"] = 4.5
    copy_ws[f"{cols['Jane Doe (DAST SME) Rationale']}{row}"] = "Confirmed with vendor demo"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "merged 1 cell" in summary

    master_ws = load_workbook(master_path)["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    assert master_ws[f"{mcols['Jane Doe (DAST SME) Score']}{mrow}"].value == 4.5


def test_merge_flags_conflict_without_overwriting(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    master_wb = load_workbook(master_path)
    master_ws = master_wb["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    master_ws[f"{mcols['Jane Doe (DAST SME) Score']}{mrow}"] = 3.0
    master_wb.save(master_path)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{cols['Jane Doe (DAST SME) Score']}{row}"] = 4.5
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "1 conflict" in summary
    assert load_workbook(master_path)["v1"][f"{mcols['Jane Doe (DAST SME) Score']}{mrow}"].value == 3.0


def test_merge_flags_invalid_score_and_dispute_without_rationale(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{cols['Jane Doe (DAST SME) Score']}{row}"] = 9.0
    row2 = _row_for(copy_ws, cols, "c2")
    copy_ws[f"{cols['Jane Doe (DAST SME) Dispute?']}{row2}"] = "Y"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "2 invalid" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: FAIL — `ImportError: cannot import name 'merge'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/stakeholder_review.py -- add to the existing file
from .render.stakeholder_workbook import SCORE_VALUES


def _stakeholder_bases(cols: dict[str, str]) -> list[str]:
    bases = []
    for header in cols:
        if header.endswith(" Score") and header not in ("Automated Score", "Resolved Score"):
            bases.append(header[: -len(" Score")])
    return bases


def merge(master_path: Path, from_path: Path) -> str:
    master_wb = load_workbook(master_path)
    from_wb = load_workbook(from_path)

    merged = 0
    invalid = 0
    conflicts = 0
    unrecognized: list[str] = []

    for sheet_name in master_wb.sheetnames:
        if sheet_name not in from_wb.sheetnames:
            continue
        m_ws = master_wb[sheet_name]
        f_ws = from_wb[sheet_name]
        m_cols = _column_map(m_ws)
        f_cols = _column_map(f_ws)

        m_crit_col = m_cols["_criterion_id"]
        f_crit_col = f_cols["_criterion_id"]
        m_pending_col = m_cols["_pending"]

        m_row_by_crit = {
            m_ws[f"{m_crit_col}{r}"].value: r
            for r in range(FIRST_DATA_ROW, m_ws.max_row + 1)
            if m_ws[f"{m_crit_col}{r}"].value
        }
        f_row_by_crit = {
            f_ws[f"{f_crit_col}{r}"].value: r
            for r in range(FIRST_DATA_ROW, f_ws.max_row + 1)
            if f_ws[f"{f_crit_col}{r}"].value
        }

        for base in _stakeholder_bases(m_cols):
            score_h, dispute_h, rationale_h = f"{base} Score", f"{base} Dispute?", f"{base} Rationale"
            if score_h not in m_cols or score_h not in f_cols:
                if score_h not in m_cols:
                    unrecognized.append(score_h)
                continue
            for criterion_id, f_row in f_row_by_crit.items():
                f_score = f_ws[f"{f_cols[score_h]}{f_row}"].value
                f_dispute = f_ws[f"{f_cols[dispute_h]}{f_row}"].value
                f_rationale = f_ws[f"{f_cols[rationale_h]}{f_row}"].value
                if f_score is None and f_dispute is None and f_rationale is None:
                    continue
                m_row = m_row_by_crit.get(criterion_id)
                if m_row is None or m_ws[f"{m_pending_col}{m_row}"].value == 1:
                    continue
                valid = (f_score is None or f_score in SCORE_VALUES) and (f_dispute != "Y" or bool(f_rationale))
                if not valid:
                    invalid += 1
                    continue
                existing = m_ws[f"{m_cols[score_h]}{m_row}"].value
                if existing is not None and f_score is not None and existing != f_score:
                    conflicts += 1
                    continue
                m_ws[f"{m_cols[score_h]}{m_row}"] = f_score
                m_ws[f"{m_cols[dispute_h]}{m_row}"] = f_dispute
                m_ws[f"{m_cols[rationale_h]}{m_row}"] = f_rationale
                merged += 1

    master_wb.save(master_path)
    return f"merged {merged} cell(s), {invalid} invalid, {conflicts} conflict(s), unrecognized: {unrecognized}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add core/stakeholder_review.py tests/test_stakeholder_review.py
git commit -m "feat: add merge command for distributed-copies collection mode"
```

---

### Task 7: `validate_workbook` and `snapshot`

**Files:**
- Modify: `core/stakeholder_review.py`
- Test: `tests/test_stakeholder_review.py`

**Interfaces:**
- Consumes: `_column_map`, `_stakeholder_bases`, `SCORE_VALUES` from
  Tasks 5–6.
- Produces: `validate_workbook(file_path: Path) -> list[str]` (a list of
  human-readable issue strings, empty if none found).
  `snapshot(file_path: Path, vendor_id: str, archive_dir: Path, label:
  str | None = None) -> Path` (returns the path it copied to). Task 8's
  CLI commands call both and print their results.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stakeholder_review.py -- add to the existing file
from datetime import date

from core.stakeholder_review import snapshot, validate_workbook


def test_validate_workbook_flags_dispute_without_rationale_and_invalid_score(tmp_path):
    file_path = _generate_two_stakeholders(tmp_path, "review.xlsx")
    wb = load_workbook(file_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c1")
    ws[f"{cols['Jane Doe (DAST SME) Dispute?']}{row}"] = "Y"
    row2 = _row_for(ws, cols, "c2")
    ws[f"{cols['Dev Lead Score']}{row2}"] = 9.0
    wb.save(file_path)

    issues = validate_workbook(file_path)
    assert len(issues) == 2


def test_validate_workbook_returns_empty_list_for_clean_file(tmp_path):
    file_path = _generate_two_stakeholders(tmp_path, "review.xlsx")
    assert validate_workbook(file_path) == []


def test_snapshot_copies_file_into_archive_dir(tmp_path):
    file_path = _generate_two_stakeholders(tmp_path, "review.xlsx")
    archive_dir = tmp_path / "archive"
    result = snapshot(file_path, "v1", archive_dir, label="baseline")
    assert result.exists()
    assert result.parent == archive_dir
    assert "v1" in result.name
    assert "baseline" in result.name
    assert result.read_bytes() == file_path.read_bytes()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_workbook'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/stakeholder_review.py -- add to the existing file
import shutil
from datetime import date


def validate_workbook(file_path: Path) -> list[str]:
    wb = load_workbook(file_path)
    issues: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        cols = _column_map(ws)
        crit_col = cols["_criterion_id"]
        for base in _stakeholder_bases(cols):
            score_h, dispute_h, rationale_h = f"{base} Score", f"{base} Dispute?", f"{base} Rationale"
            for row in range(FIRST_DATA_ROW, ws.max_row + 1):
                criterion_id = ws[f"{crit_col}{row}"].value
                if not criterion_id:
                    continue
                score = ws[f"{cols[score_h]}{row}"].value
                dispute = ws[f"{cols[dispute_h]}{row}"].value
                rationale = ws[f"{cols[rationale_h]}{row}"].value
                if score is not None and score not in SCORE_VALUES:
                    issues.append(f"{sheet_name}/{criterion_id}: '{base}' score {score!r} is not a valid value")
                if dispute == "Y" and not rationale:
                    issues.append(f"{sheet_name}/{criterion_id}: '{base}' disputed with no rationale")
        resolved_h = "Resolved Score"
        by_h = "Resolved By"
        ts_h = "Resolved Timestamp"
        for row in range(FIRST_DATA_ROW, ws.max_row + 1):
            criterion_id = ws[f"{crit_col}{row}"].value
            if not criterion_id:
                continue
            resolved = ws[f"{cols[resolved_h]}{row}"].value
            resolved_by = ws[f"{cols[by_h]}{row}"].value
            resolved_ts = ws[f"{cols[ts_h]}{row}"].value
            if resolved is not None and not (resolved_by and resolved_ts):
                issues.append(f"{sheet_name}/{criterion_id}: resolved score present without Resolved By/Timestamp")
    return issues


def snapshot(file_path: Path, vendor_id: str, archive_dir: Path, label: str | None = None) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{label}" if label else ""
    dest = archive_dir / f"{date.today().isoformat()}-{vendor_id}{suffix}.xlsx"
    shutil.copy2(file_path, dest)
    return dest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stakeholder_review.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add core/stakeholder_review.py tests/test_stakeholder_review.py
git commit -m "feat: add validate and snapshot commands for stakeholder review"
```

---

### Task 8: CLI wiring (`dast-bench stakeholder-review ...`)

**Files:**
- Modify: `core/cli.py`
- Test: `tests/test_cli_stakeholder_review.py`

**Interfaces:**
- Consumes: `generate_workbook`, `compute_priority_order` from
  `core.render.stakeholder_workbook`; `populate`, `merge`,
  `validate_workbook`, `snapshot` from `core.stakeholder_review`;
  `storage.load_vendor`, `storage.load_criteria`,
  `storage.load_research_cache`, `storage.research_cache_path` (all
  exist today — see Global Constraints); `CANDIDATES_DIR`,
  `CRITERIA_PATH`, `RESEARCH_CACHE_DIR`, `DATA_DIR` module constants
  (already defined near the top of `core/cli.py`).
- Produces: `dast-bench stakeholder-review generate|populate|merge|validate|snapshot`,
  wired into the existing `app` the same way `candidate_app`/`scan_app`/
  `cache_app` already are.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_stakeholder_review.py
import yaml
from openpyxl import load_workbook
from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()


def _setup_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "candidates").mkdir(parents=True)
    (tmp_path / "data" / "research-cache").mkdir(parents=True)
    criteria = {
        "version": 1,
        "criteria": [
            {"id": "c1", "category": "Coverage", "name": "Coverage One", "description": "d", "weight": 100.0, "rubric": "r"},
        ],
    }
    (tmp_path / "data" / "criteria.yaml").write_text(yaml.safe_dump(criteria))
    vendor = {
        "id": "v1",
        "name": "Vendor One",
        "source": "discovered",
        "status": "finalist",
        "scores": [{"criterion_id": "c1", "score": 4.0, "evidence": "ev1", "confidence": "paper", "timestamp": "2026-01-01T00:00:00"}],
        "hands_on_results": [],
        "observations": [],
    }
    (tmp_path / "data" / "candidates" / "v1.yaml").write_text(yaml.safe_dump(vendor))


def test_cli_stakeholder_review_generate_creates_workbook(tmp_path, monkeypatch):
    _setup_repo(tmp_path, monkeypatch)
    out_path = tmp_path / "review.xlsx"
    result = runner.invoke(
        app,
        [
            "stakeholder-review", "generate",
            "--vendor-id", "v1",
            "--stakeholder", ":DAST SME",
            "--out", str(out_path),
        ],
    )
    assert result.exit_code == 0, result.output
    wb = load_workbook(out_path)
    assert "v1" in wb.sheetnames


def test_cli_stakeholder_review_generate_fails_on_unscored_criterion(tmp_path, monkeypatch):
    _setup_repo(tmp_path, monkeypatch)
    extra_criteria = yaml.safe_load((tmp_path / "data" / "criteria.yaml").read_text())
    extra_criteria["criteria"].append(
        {"id": "c2", "category": "DX", "name": "DX One", "description": "d", "weight": 0.0, "rubric": "r"}
    )
    (tmp_path / "data" / "criteria.yaml").write_text(yaml.safe_dump(extra_criteria))
    result = runner.invoke(
        app,
        [
            "stakeholder-review", "generate",
            "--vendor-id", "v1",
            "--stakeholder", ":DAST SME",
            "--out", str(tmp_path / "review.xlsx"),
        ],
    )
    assert result.exit_code == 1
    assert "error:" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_stakeholder_review.py -v`
Expected: FAIL — `Error: No such command 'stakeholder-review'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/cli.py -- add these imports near the top, alongside the existing ones
from .render.stakeholder_workbook import compute_priority_order, generate_workbook
from .stakeholder_review import merge as merge_stakeholder_copy
from .stakeholder_review import populate as populate_pending
from .stakeholder_review import snapshot as snapshot_workbook
from .stakeholder_review import validate_workbook

# add near the other DATA_DIR-derived constants:
STAKEHOLDER_REVIEW_ARCHIVE_DIR = DATA_DIR / "stakeholder-reviews-archive"

# add near the other `_app = typer.Typer()` / `app.add_typer(...)` pairs:
stakeholder_review_app = typer.Typer()
app.add_typer(stakeholder_review_app, name="stakeholder-review")


def _parse_stakeholder(raw: str) -> tuple[str | None, str]:
    name, _, role = raw.partition(":")
    return (name or None, role)


def _parse_pending_criteria(raw_list: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for raw in raw_list:
        vendor_id, _, criteria_csv = raw.partition(":")
        result.setdefault(vendor_id, set()).update(c.strip() for c in criteria_csv.split(",") if c.strip())
    return result


@stakeholder_review_app.command("generate")
def stakeholder_review_generate(
    vendor_id: list[str] = typer.Option(..., "--vendor-id"),
    stakeholder: list[str] = typer.Option(..., "--stakeholder"),
    pending_criteria: list[str] = typer.Option([], "--pending-criteria"),
    out: Path = typer.Option(...),
) -> None:
    taxonomy = storage.load_criteria(CRITERIA_PATH)
    vendors = []
    for vid in vendor_id:
        path = storage.vendor_path(CANDIDATES_DIR, vid)
        if not path.exists():
            typer.echo(f"error: vendor '{vid}' not found")
            raise typer.Exit(code=1)
        vendor = storage.load_vendor(path)
        for criterion in taxonomy.criteria:
            if vendor.score_for(criterion.id) is None:
                typer.echo(f"error: vendor '{vid}' has no score for criterion '{criterion.id}'")
                raise typer.Exit(code=1)
        vendors.append(vendor)

    stakeholders = [_parse_stakeholder(s) for s in stakeholder]
    pending = _parse_pending_criteria(pending_criteria)
    research_caches = {
        v.id: storage.load_research_cache(storage.research_cache_path(RESEARCH_CACHE_DIR, v.id), v.id)
        for v in vendors
    }
    generate_workbook(taxonomy, vendors, stakeholders, pending, research_caches, out)
    typer.echo(f"generated stakeholder review workbook at {out}")


@stakeholder_review_app.command("populate")
def stakeholder_review_populate(
    vendor_id: str = typer.Option(...),
    file: Path = typer.Option(...),
) -> None:
    path = storage.vendor_path(CANDIDATES_DIR, vendor_id)
    if not path.exists():
        typer.echo(f"error: vendor '{vendor_id}' not found")
        raise typer.Exit(code=1)
    vendor = storage.load_vendor(path)
    typer.echo(populate_pending(vendor, file))


@stakeholder_review_app.command("merge")
def stakeholder_review_merge(
    into: Path = typer.Option(...),
    from_: Path = typer.Option(..., "--from"),
) -> None:
    if not into.exists() or not from_.exists():
        typer.echo("error: both --into and --from files must exist")
        raise typer.Exit(code=1)
    typer.echo(merge_stakeholder_copy(into, from_))


@stakeholder_review_app.command("validate")
def stakeholder_review_validate(file: Path = typer.Option(...)) -> None:
    if not file.exists():
        typer.echo(f"error: file not found: {file}")
        raise typer.Exit(code=1)
    issues = validate_workbook(file)
    if not issues:
        typer.echo("no issues found")
        return
    for issue in issues:
        typer.echo(issue)


@stakeholder_review_app.command("snapshot")
def stakeholder_review_snapshot(
    file: Path = typer.Option(...),
    vendor_id: str = typer.Option(...),
    label: str = typer.Option(None),
) -> None:
    if not file.exists():
        typer.echo(f"error: file not found: {file}")
        raise typer.Exit(code=1)
    dest = snapshot_workbook(file, vendor_id, STAKEHOLDER_REVIEW_ARCHIVE_DIR, label)
    typer.echo(f"snapshotted to {dest}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_stakeholder_review.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no regressions in the existing suite

- [ ] **Step 6: Commit**

```bash
git add core/cli.py tests/test_cli_stakeholder_review.py
git commit -m "feat: wire dast-bench stakeholder-review CLI commands"
```
