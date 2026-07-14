# Research Cache & Gap-Check Reviewer — Design

## Purpose & Context

A real research defect was found (not hypothetical): Veracode was scored
`≤2.5` (mostly "inferred absence") on 5 criteria — `shadow-api-discovery`,
`asset-discovery-inventory`, `historical-risk-trend-dashboards`,
`aspm-integration`, `multi-tenancy-access-control` — when the vendor in
fact has real, well-documented, named products/features addressing every
one of them (EASM, Risk Manager — an IDC MarketScape Leader-recognized
ASPM product, Analytics with MTTR tracking, and documented RBAC roles).

Root cause, traced to the actual research process used: `dast-shortlist`'s
research for Veracode ran 3 broad, bundled `WebSearch` queries covering
many unrelated criteria at once, in generic rubric language (e.g. "RBAC
roles", "ASPM integration"), without first learning the vendor's own
branded product/module names. Generic functional searches surface
third-party marketing and forum questions far more readily than a
vendor's own product page, because search relevance rewards exact
terminology matches — a search for "ASPM integration" doesn't easily find
"Veracode Risk Manager" if you don't already know that name. When a
bundled search came back thin on a given sub-topic, the process concluded
"inferred absence" without a targeted follow-up search first.

The evaluator caught this by cross-checking against an external agent's
"audit" — which itself contained a mix of real findings and fabricated
claims (specific SIEM/SOAR integrations that don't check out, and a
wrong RBAC role name), independently verified before this design work
began. That outcome is itself informative: a second opinion that doesn't
do real, citable research is not a safety net — it can add false
confidence rather than remove it. The fix adopted here is the pattern
already proven elsewhere in this project (the implementer-then-fresh-
reviewer discipline used for every code change this session): a
genuinely independent reviewer, held to the same citation discipline as
the original research, checking only where the failure mode actually
lives.

Separately, the evaluator wants research findings cached durably (in
git) so that future re-runs of the same vendor don't re-pay the token
cost of re-searching criteria whose research is still valid, while
allowing targeted, selective invalidation when something specific should
be refreshed.

## Goals

- `dast-discovery` captures a vendor's own named major product lines/
  modules (not just its core DAST product) as part of its research,
  logged in the discovery observation — this is what would have
  surfaced "EASM", "Risk Manager", "Analytics" before any criterion
  scoring began.
- A new **research cache**, one file per vendor
  (`data/research-cache/<vendor-id>.yaml`), storing the actual search
  queries used and findings (URL + snippet) per criterion, with a
  timestamp — durable, versioned in git, written only through the CLI
  (same "nothing hand-edited" rule as every other data file in this
  project).
- New `dast-bench cache` CLI commands: `record` (write a cache entry),
  `show` (inspect cached entries), `invalidate` (mark entries stale) —
  supporting all three invalidation modes discussed: single
  vendor+criterion, a score-threshold bulk operation ("invalidate
  everything currently scored `≤N`"), and a full-vendor wipe.
- `dast-shortlist` becomes cache-aware: before researching a criterion,
  check for a fresh (non-stale) cache entry and reuse it instead of a
  new `WebSearch` if one exists.
- `dast-shortlist` gains a **gap-check step**: any criterion that scores
  `≤2.5` after the normal research pass automatically gets a second,
  independent investigation by a **fresh reviewer subagent** — no shared
  context with the original research, real cited searches only, using
  the vendor's own product terminology captured by `dast-discovery`.
  This is a standing rule for every future vendor scored, not a one-time
  patch.
- The gap-check reviewer's findings are *proposed* revisions, presented
  to the evaluator before persisting — same "present before persisting"
  gate `dast-shortlist` already uses for its normal research.

## Non-Goals / Out of Scope

- No change to what the existing `score`/`evidence`/`confidence` fields
  in `data/candidates/*.yaml` mean or how they're structured — the cache
  is new, additional, separate data, not a replacement.
- No automatic cache expiration/staleness-by-age — invalidation is
  always a deliberate, explicit action via one of the three CLI modes.
- The immediate re-audit of all 5 current candidates only re-investigates
  criteria currently scored `≤2.5` — criteria that scored higher are not
  redone; this isn't the failure mode that was found, and redoing
  everything would be significant, mostly-redundant effort.
- The gap-check reviewer never auto-applies a score change — every
  finding is presented for evaluator confirmation first.
- Running the actual 5-vendor re-audit is a follow-up action taken once
  this plan ships, using the fixed skills — not a task inside this
  plan's implementation (matching how every other skill-instruction
  change this session was verified: ship the mechanism, then really use
  it).

## Architecture

**New data model (`core/models.py`):**
```python
class ResearchFinding(BaseModel):
    url: str
    snippet: str

class CriterionResearchCache(BaseModel):
    researched_at: datetime
    queries: list[str]
    findings: list[ResearchFinding]
    reviewed_by_gap_check: bool = False
    stale: bool = False

class VendorResearchCache(BaseModel):
    vendor_id: str
    criteria: dict[str, CriterionResearchCache] = {}
```

**New storage functions (`core/storage.py`):** `load_research_cache(path)
-> VendorResearchCache`, `save_research_cache(cache, path)`, and a path
helper `research_cache_path(base_dir, vendor_id) -> Path` mirroring the
existing `vendor_path()` helper — files live at
`data/research-cache/<vendor-id>.yaml`.

**New CLI command group (`core/cli.py`):**
- `dast-bench cache record --vendor-id <id> --criterion-id <id> --query <q> [--query <q> ...] --findings-file <path> [--reviewed-by-gap-check]`
  — `--query` is repeatable (one or more search queries used);
  `--findings-file` points to a small JSON file
  (`[{"url": "...", "snippet": "..."}, ...]`) rather than cramming
  structured list data into shell flags. Writes/overwrites the cache
  entry for that vendor+criterion, `stale` reset to `false`.
- `dast-bench cache show --vendor-id <id> [--criterion-id <id>]` — prints
  the cached entry (or all entries for the vendor if no criterion given):
  timestamp, queries, findings, flags.
- `dast-bench cache invalidate --vendor-id <id>` with exactly one of:
  `--criterion-id <id>` (single entry), `--max-score <n>` (every cached
  entry whose *current* score in `data/candidates/<id>.yaml` is `<= n`),
  or `--all` (every entry for that vendor) — sets `stale: true` on the
  matched entries without deleting their prior queries/findings (a
  subsequent `record` call overwrites them).

**Skill changes:**
- `.claude/skills/dast-discovery/SKILL.md`'s Step 3 (Research the market
  live) gains an instruction to identify and log the vendor's own named
  major product lines/modules as part of the discovery observation.
- `.claude/skills/dast-shortlist/SKILL.md`'s Step 4 gains a preliminary
  cache-check sub-step (read `dast-bench cache show` for a criterion
  before searching; if a fresh entry exists, reuse its findings instead
  of a new `WebSearch`, and write a fresh cache entry via `cache record`
  after any new research). A new step is inserted after the initial
  scoring pass and before Step 5 (Present the complete proposed
  scoring): for every criterion scored `≤2.5`, dispatch a fresh
  subagent — no shared context with the original research — instructed
  to independently investigate that specific criterion for that vendor,
  using the vendor's own product terminology from the `dast-discovery`
  observation, with the same real-citation discipline as normal
  research. Its findings become part of what's presented to the
  evaluator in Step 5, clearly marked as gap-check findings.

## Data Flow

1. `dast-discovery` researches a vendor, logs its rationale as today,
   plus the vendor's own named product lines/modules in the same
   observation note.
2. `dast-shortlist`, researching a criterion: checks
   `dast-bench cache show --vendor-id <id> --criterion-id <id>`. If a
   non-stale entry exists, reuse its findings to compose the
   score/evidence without a new `WebSearch`. Otherwise, research fresh
   and call `dast-bench cache record` afterward with the queries and
   findings used.
3. After the full criterion pass, any criterion scoring `≤2.5` triggers
   a fresh-subagent gap-check dispatch, which does its own real research
   (also cached via `cache record`, `reviewed_by_gap_check: true`) and
   reports back proposed findings/score.
4. Step 5 (unchanged in spirit) presents the complete proposed scoring —
   now including any gap-check revisions, clearly marked — to the
   evaluator for confirmation before any `record-score` CLI call.
5. `dast-bench cache invalidate` is a standalone, on-demand action the
   evaluator can run any time (not part of the normal `dast-shortlist`
   flow) to force specific entries stale ahead of a future re-run.

## Error Handling

- `cache show`/`cache invalidate` on a vendor or criterion with no
  existing cache entry: relay a clear `error: ...` message verbatim,
  same convention as every other CLI command in this project — no
  silent no-ops.
- `cache record --findings-file` pointing to a missing or malformed
  (invalid JSON, wrong shape) file: fail with a clear error rather than
  writing a partial/corrupt cache entry.
- `cache invalidate --max-score`: if the vendor has no cache entries at
  or below that score, this is not an error — it's a valid "nothing
  matched" outcome, reported as such (e.g. "0 entries invalidated").

## Testing

Real code (models, storage, CLI), so real TDD:
- `ResearchFinding`/`CriterionResearchCache`/`VendorResearchCache`:
  round-trip YAML serialization tests.
- `load_research_cache`/`save_research_cache`: read/write tests
  following the existing `storage.py` test patterns.
- `cache record`/`show`/`invalidate` (all three invalidation modes):
  CLI-invocation tests following the existing `tests/test_cli_*.py`
  pattern — including the `--max-score` mode's cross-reference against
  a candidate's actual current score.
- Skill-instruction changes (`dast-discovery`, `dast-shortlist`) are
  prompt-file edits, verified via the same grep/diff structural checks
  used for every other skill-file change this session, not pytest.
- The true acceptance test — actually running the fixed
  `dast-discovery`/`dast-shortlist` against all 5 current candidates,
  targeting criteria scored `≤2.5` — happens after this plan ships, as a
  live follow-up action, not a task inside the plan itself.
