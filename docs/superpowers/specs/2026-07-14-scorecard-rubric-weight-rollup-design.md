# Scorecard Rubric, Weight & Category Roll-Up — Design

## Purpose & Context

A senior-architect-style review of `dast-bench`'s output artifacts (the
29-criterion scorecard and the skill-authored executive summary) flagged
five gaps. Three of the five ("Where They Win" vendor comparison table,
new taxonomy criteria, narrative format polish) are being handled
separately — through `dast-report` skill-template edits or the
`dast-criteria`/`dast-shortlist` skills directly, not this spec. This
design covers the remaining two, both scoped to the deterministic markdown
rendering engine (`core/render/markdown.py`) only — XLSX and HTML
renderers are explicitly out of scope for now and may follow later:

1. **Expose scoring rubric anchors and weights.** Every `Criterion` in
   `data/criteria.yaml` already carries a bespoke `rubric` field (tailored
   1/3/5 anchor text — verified across all 29 criteria, not a single
   generic scale) and a `weight` field (0-100, category-grouped, already
   summing to 100). `render_scorecard()` and `render_comparison_matrix()`
   currently render Criterion/Category/Score/Evidence/Confidence but never
   surface rubric or weight — this is a pure rendering gap, not a
   data-model gap.
2. **Category-level roll-up (numeric only).** No aggregation exists today
   between the 29 individual criterion rows and the single grand
   `Weighted Total`. This adds a deterministic, pure-math per-category
   subtotal. The review's "Enterprise Takeaway / Fit" narrative text per
   category is explicitly out of scope here — that's interpretive
   judgment, deferred to a separate `dast-report` skill-template track.

## Goals

- Add a `Weight` column to the existing per-criterion tables in both
  `render_scorecard()` and `render_comparison_matrix()`.
- Add a `## Scoring Legend` section to `render_comparison_matrix()` only
  (not repeated per-vendor in scorecards): one shared listing of every
  criterion's 1/3/5 rubric anchors, grouped under a `### <Category>`
  subheading per category, in the taxonomy's existing category order.
- Add a `category_weighted_score()` function and a rendered category
  roll-up table (`Category | Weight | Weighted Score`) to both
  `render_scorecard()` (single vendor) and `render_comparison_matrix()`
  (one column per vendor), placed between the per-criterion table and the
  existing grand-total line/row.
- Keep all existing exact function signatures for `weighted_score()`,
  `render_scorecard()`, `render_comparison_matrix()`, and `write_markdown()`
  unchanged — this is strictly additive to their output.

## Non-Goals / Out of Scope

- XLSX (`core/render/xlsx.py`) and HTML (`core/render/html.py`) renderers —
  not touched by this spec; may get equivalent treatment in a follow-up.
- The "Enterprise Takeaway / Fit" narrative text per category, and the
  "Where They Win" vendor comparison table — both are skill-authored
  judgment calls that belong to `dast-report`, not this deterministic
  renderer.
- Any change to `data/criteria.yaml`'s schema or the `Criterion`/`Vendor`
  models — `rubric` and `weight` already exist; this spec only renders
  them.
- Any change to `reports/`'s gitignore policy or to `sample-report/`'s
  manual-refresh convention.
- Renormalizing category weights or changing what's already scored — this
  is a rendering-only change over existing data.

## Architecture

Three new functions in `core/render/markdown.py`, plus targeted additions
to the two existing render functions:

- **`_ordered_categories(taxonomy: CriteriaTaxonomy) -> list[str]`** —
  private helper. Returns each distinct `category` value from
  `taxonomy.criteria`, deduplicated, preserving first-occurrence order.
  No new field on `CriteriaTaxonomy` — category order is already implicit
  in how criteria were added (verified: Coverage → Detection Quality →
  Production Safety & Operability → Developer Experience → Reporting &
  Extensibility → Deployment & Data Governance).

- **`category_weighted_score(taxonomy: CriteriaTaxonomy, vendor: Vendor, category: str) -> float`**
  — mirrors the existing `weighted_score()`'s formula shape, restricted to
  one category:
  ```python
  total = 0.0
  category_weight = 0.0
  for criterion in taxonomy.criteria:
      if criterion.category != category:
          continue
      category_weight += criterion.weight
      entry = vendor.score_for(criterion.id)
      if entry:
          total += entry.score * criterion.weight
  return total / category_weight if category_weight else 0.0
  ```
  Deliberately mirrors `weighted_score()`'s existing behavior: an unscored
  criterion contributes 0 rather than being excluded from the denominator,
  so a partially-scored category shows a proportionally low score — the
  same behavior the existing overall total already has for incomplete
  scoring. `category_weight` is a real, known-positive constant for every
  category actually present in the taxonomy (guarded against division by
  zero only for the theoretical empty-taxonomy case).

- **`render_scoring_legend(taxonomy: CriteriaTaxonomy) -> str`** — for each
  category (in `_ordered_categories` order), emits a `### <Category>`
  subheading, then for each criterion in that category: a bold criterion
  name, followed by three bullets parsed from `criterion.rubric` using the
  verified marker pattern (every rubric string contains exactly one `1:`,
  `3:`, `5:` in that order — confirmed via regex against all 29 current
  criteria, safe to split on `re.split(r'(?<!\d)([135]):\s', rubric)`).
  Returns a `## Scoring Legend` section as a single string.

**Changes to `render_scorecard(taxonomy, vendor)`:**
- Existing per-criterion table gains a `Weight` column, inserted right
  after `Category` (new header order: `Criterion | Category | Weight |
  Score | Evidence | Confidence`), value from `criterion.weight` formatted
  `:g` matching the existing score formatting convention.
- A new `## Category Breakdown` table is inserted between the per-criterion
  table and the existing `**Weighted score: X.XX / 5.00**` line: one row
  per category (`_ordered_categories` order) with columns `Category |
  Weight | Weighted Score`, using `category_weighted_score()`.

**Changes to `render_comparison_matrix(taxonomy, vendors)`:**
- A `## Scoring Legend` section (from `render_scoring_legend()`) is
  inserted at the top, before the existing per-criterion comparison table.
- The per-criterion table's existing header is `Criterion | <vendor 1> |
  <vendor 2> | ...` — there is no `Category` column today. A `Weight`
  column (single column, since weight doesn't vary per vendor) is inserted
  right after `Criterion` (new header order: `Criterion | Weight | <vendor
  1> | <vendor 2> | ...`).
- A category roll-up table is inserted between the per-criterion table and
  the existing `**Weighted Total**` row: one row per category, columns
  `Category | Weight | <vendor 1> | <vendor 2> | ...`, using
  `category_weighted_score()` per vendor.

`write_markdown()` itself is unchanged — it already just calls
`render_scorecard`/`render_comparison_matrix` and writes their string
output.

## Data Flow

1. `dast-bench render` (unchanged CLI entry point) calls `write_markdown()`
   exactly as today.
2. `render_comparison_matrix()` now additionally calls
   `render_scoring_legend()` once and `category_weighted_score()` once per
   `(vendor, category)` pair, purely from already-loaded `taxonomy` and
   `vendors` — no new data loading.
3. `render_scorecard()` now additionally calls `category_weighted_score()`
   once per category for the single vendor being rendered.
4. Both existing consumers of this output are unaffected: `dast-report`'s
   Step 4 reads `reports/comparison-matrix.md` only to confirm the
   `Weighted Total` figure matches — that line is untouched, only
   preceded by new sections; `tests/test_render_markdown.py`'s existing
   assertions are all substring checks, none of which break from
   additions.

## Error Handling

No new error paths. `category_weighted_score()` guards division by zero
for a category with zero total weight (only reachable with an empty or
malformed taxonomy, already an edge case the rest of the codebase doesn't
specially handle either). Rubric-string parsing has no failure mode to
handle given the verified 100%-consistent `1:`/`3:`/`5:` marker format
across all current criteria — if a future criterion's rubric ever doesn't
match, the split degrades to returning the whole string as a single
"anchor," which still renders (no exception), just less cleanly.

## Testing

All additive to `tests/test_render_markdown.py`:
- `category_weighted_score`: normal case (multiple scored criteria in one
  category), missing-score case (one criterion unscored, score drags
  down proportionally per the mirrored formula), fully-unscored category
  (returns 0.0, no exception).
- `_ordered_categories`: dedups and preserves first-occurrence order given
  a taxonomy with categories in a known non-alphabetical order.
- `render_scoring_legend`: given a taxonomy with a known rubric string,
  asserts the three parsed anchor bullets appear, grouped under the
  correct category subheading.
- `render_scorecard`: existing tests still pass unmodified; new assertions
  confirm `Weight`, `Category Breakdown`, and a known category name appear.
- `render_comparison_matrix`: existing tests still pass unmodified; new
  assertions confirm `Scoring Legend`, `Weight`, and a known category
  roll-up row appear.
