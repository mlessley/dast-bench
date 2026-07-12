# DAST Bench

DAST Bench is a structured evaluation framework for comparing DAST (Dynamic
Application Security Testing) tools — replacing ad hoc bake-offs with a
repeatable, evidence-backed methodology: a versioned criteria taxonomy,
automated benchmark scoring against known-vulnerable reference targets, and
generated scorecards/comparison reports rendered straight from a single YAML
source of truth. Nothing gets hand-edited — a CLI (`dast-bench`) is the only
sanctioned way to mutate that data, so every score and observation carries a
clean, diffable audit trail.

The current implementation drives its research and orchestration phases
through Claude Code, with the agent doing the judgment work for each
evaluation phase and shelling out to the `dast-bench` CLI for every data
mutation. That orchestration layer is deliberately swappable, not
load-bearing: a planned Phase 2 port moves the same data model and CLI onto
a standalone agent runtime, so the evaluation engine itself isn't tied to
any one AI platform.

Full context, rationale, and phased rollout: see [Docs](#docs) below —
start with the Phase 1 design spec if you want the "why."

## Status

**Phase 1 core library and CLI: done.** Five command groups (`criteria`,
`candidate`, `scan`, `status`, `render`), YAML round-tripping via Pydantic,
and Markdown/XLSX/HTML report rendering are implemented and tested (55
tests passing).

**DAST benchmark CI pipeline: built, not yet live-verified.** A GitHub
Actions `workflow_dispatch` pipeline
(`.github/workflows/dast-benchmark.yml`) spins up OWASP Juice Shop or VAmPI
as an ephemeral service container, runs a ZAP full active scan, and uploads
both the raw and (for ZAP) normalized report as build artifacts. It hasn't
been dispatched against a real GitHub-hosted run yet — see the plan's
manual-verification note.

**Not yet built:**
- The `dast-scan` Claude Code skill (the orchestrator that will trigger
  the CI pipeline above, download its artifacts, and call `ingest-scan-result`).
- The `dast-criteria`, `dast-discovery`, `dast-shortlist`, `dast-report` skills.
- Production-safe scanning (drift/misconfiguration detection against a real
  or staging target, as opposed to the ephemeral benchmark targets above) —
  deliberately deferred; see the roadmap doc.

## Quick start

Requires Python >=3.11 and [`uv`](https://docs.astral.sh/uv/) — this
project uses `uv` for all dependency management, not `pip`.

```bash
uv sync --extra dev       # installs the package + pytest into .venv
uv run pytest -v          # run the test suite
uv run dast-bench --help  # see all CLI commands
```

## CLI reference

All commands take explicit `--flag value` options (no positional
arguments), so they're unambiguous when invoked by an LLM-driven skill.

```
dast-bench criteria add-criterion --id --category --name --description --weight --rubric
dast-bench criteria set-weight --id --weight
dast-bench criteria list

dast-bench candidate add --id --name --source --website --notes
dast-bench candidate set-status --id --status
dast-bench candidate set-ci-tool --id --tool
dast-bench candidate record-score --vendor-id --criterion-id --score --evidence --confidence
dast-bench candidate log-observation --vendor-id --context --note --tags
dast-bench candidate list

dast-bench scan ingest-scan-result --vendor-id --benchmark-id --file --test-id --description --automated

dast-bench status   # reports vendors missing a score for any current criterion, and weight-total warnings
dast-bench render   # renders reports/scorecard-<id>.md, comparison-matrix.md, comparison-matrix.xlsx, dashboard.html
```

## Project layout

```
core/                      # Python package: Pydantic models + CLI
  models.py                # Criterion, CriteriaTaxonomy, Vendor, ScoreEntry, Benchmark, ...
  storage.py                # YAML load/save for criteria, vendors, benchmarks
  cli.py                     # Typer CLI — the only sanctioned way to mutate data/
  status.py                  # gap-detection (missing scores, weight-total validation)
  render/
    markdown.py               # per-vendor scorecards + comparison matrix (Markdown)
    xlsx.py                    # comparison matrix (XLSX)
    html.py                    # self-contained, sortable comparison dashboard (HTML)
data/                      # YAML source of truth (criteria.yaml, benchmarks.yaml, candidates/*.yaml)
reports/                   # generated output — never hand-edited, regenerated via `dast-bench render`
.github/
  workflows/dast-benchmark.yml     # CI pipeline: ephemeral benchmark target + ZAP scan
  scripts/normalize/zap.py          # ZAP report -> generic findings JSON
tests/                     # pytest suite (unit + CLI-invocation + workflow-structure tests)
docs/superpowers/
  specs/                    # design docs (the "why" and "what")
  plans/                    # implementation plans (the "how", task-by-task)
```

## Docs

- [Phase 1 design spec](docs/superpowers/specs/2026-07-10-dast-eval-phase1-design.md) — overall purpose, five-phase workflow, data model, architecture
- [Core library implementation plan](docs/superpowers/plans/2026-07-10-core-library.md)
- [DAST benchmark CI pipeline design](docs/superpowers/specs/2026-07-11-dast-benchmark-ci-pipeline-design.md)
- [DAST benchmark CI pipeline implementation plan](docs/superpowers/plans/2026-07-11-dast-benchmark-ci-pipeline.md)
- [Production-safe scanning roadmap](docs/superpowers/specs/2026-07-11-production-safe-scanning-roadmap.md) — deferred, parking-lot notes only
