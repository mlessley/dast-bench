# core/render/html.py
from __future__ import annotations

import html as html_lib
from pathlib import Path

from ..models import CriteriaTaxonomy, Vendor
from .markdown import weighted_score

_SORT_SCRIPT = """
<script>
function sortTable(colIndex) {
  const table = document.querySelector('table');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const asc = table.dataset.sortCol == colIndex && table.dataset.sortDir !== 'asc';
  rows.sort((a, b) => {
    const av = a.children[colIndex].textContent.trim();
    const bv = b.children[colIndex].textContent.trim();
    const an = parseFloat(av);
    const bn = parseFloat(bv);
    const cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
    return asc ? cmp : -cmp;
  });
  rows.forEach((r) => tbody.appendChild(r));
  table.dataset.sortCol = colIndex;
  table.dataset.sortDir = asc ? 'asc' : 'desc';
}
</script>
"""


def write_html(taxonomy: CriteriaTaxonomy, vendors: list[Vendor], out_path: Path) -> None:
    header_cells = ["Criterion", "Category"] + [html_lib.escape(v.name) for v in vendors]
    header_html = "".join(f'<th onclick="sortTable({i})">{name}</th>' for i, name in enumerate(header_cells))

    rows = []
    for criterion in taxonomy.criteria:
        cells = "".join(
            f"<td>{(entry.score if (entry := v.score_for(criterion.id)) else '-')}</td>" for v in vendors
        )
        rows.append(f"<tr><td>{html_lib.escape(criterion.name)}</td><td>{html_lib.escape(criterion.category)}</td>{cells}</tr>")

    totals = "".join(f"<td>{weighted_score(taxonomy, v):.2f}</td>" for v in vendors)

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DAST Comparison Matrix</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
th {{ cursor: pointer; }}
tfoot td {{ font-weight: bold; }}
</style>
</head>
<body>
<h1>DAST Tool Comparison Matrix</h1>
<table>
<thead><tr>{header_html}</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
<tfoot><tr><td>Weighted Total</td><td></td>{totals}</tr></tfoot>
</table>
{_SORT_SCRIPT}
</body>
</html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
