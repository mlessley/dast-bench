# Sample Report — Snapshot

This is a **point-in-time snapshot** of `dast-bench`'s generated output,
committed here so it's visible without cloning and running the tool.

**Snapshot date:** 2026-07-14 (refreshed), from the proof-of-concept
evaluation of ZAP, Nuclei, and StackHawk described in the main
[README](../README.md#status) — now scored against the full 33-criterion
taxonomy (expanded from 29 after a senior-architect review), with the
`dast-report` narrative including a Financial Sector Fit framing, a Where
They Win comparison table, and per-category takeaways.

This directory is *not* the live output — that's `reports/` (gitignored,
regenerated on demand, always current for whatever's in `data/*.yaml` right
now). This snapshot is a manually-updated copy, refreshed only when the
results change enough to be worth re-publishing.

## Contents

- `executive-summary.md` — narrative write-up (author: the `dast-report`
  skill), the best starting point
- `comparison-matrix.md` / `comparison-matrix.xlsx` — full scored matrix,
  every vendor × every criterion
- `scorecard-<vendor>.md` — one vendor's full scorecard with evidence per
  criterion
- `dashboard.html` — self-contained, sortable HTML view of the same data
  (download and open locally; GitHub won't render it inline)

## Regenerating this snapshot

```bash
uv run dast-bench render   # refreshes reports/*.md, *.xlsx, dashboard.html
# then re-run the dast-report skill to refresh reports/executive-summary.md
cp reports/{comparison-matrix.md,comparison-matrix.xlsx,dashboard.html,executive-summary.md,scorecard-*.md} sample-report/
```
