# dast-eval

A small, git-native toolkit for running a structured, evidence-backed
evaluation of DAST (Dynamic Application Security Testing) tools/frameworks —
built as a personal utility for a single evaluator, not a multi-user product.

YAML files are the single source of truth. A Python CLI (`dast-eval`) is the
only sanctioned way to mutate that data, so nothing gets edited by hand. LLM
agents (Claude Code skills, still to be built) are expected to drive the
research/judgment phases and shell out to this CLI for every write.

Full context, rationale, and phased rollout: see [Docs](#docs) below —
start with the Phase 1 design spec if you want the "why."

## Status

**Phase 1 core library and CLI: done.** Five command groups (`criteria`,
`candidate`, `handson`, `status`, `render`), YAML round-tripping via
Pydantic, and Markdown/XLSX/HTML report rendering are implemented and
tested (55 tests passing).

**DAST benchmark CI pipeline: built, not yet live-verified.** A GitHub
Actions `workflow_dispatch` pipeline
(`.github/workflows/dast-benchmark.yml`) spins up OWASP Juice Shop or VAmPI
as an ephemeral service container, runs a ZAP full active scan, and uploads
both the raw and (for ZAP) normalized report as build artifacts. It hasn't
been dispatched against a real GitHub-hosted run yet — see the plan's
manual-verification note.

**Not yet built:**
- The `dast-handson` Claude Code skill (the orchestrator that will trigger
  the CI pipeline above, download its artifacts, and call `ingest-scan-result`).
- The `dast-criteria`, `dast-discovery`, `dast-paper-cut`, `dast-report` skills.
- Production-safe scanning (drift/misconfiguration detection against a real
  or staging target, as opposed to the ephemeral benchmark targets above) —
  deliberately deferred; see the roadmap doc.

## Quick start

Requires Python >=3.11 and [`uv`](https://docs.astral.sh/uv/) — this
project uses `uv` for all dependency management, not `pip`.

```bash
uv sync --extra dev      # installs the package + pytest into .venv
uv run pytest -v         # run the test suite
uv run dast-eval --help  # see all CLI commands
```

## CLI reference

All commands take explicit `--flag value` options (no positional
arguments), so they're unambiguous when invoked by an LLM-driven skill.

```
dast-eval criteria add-criterion --id --category --name --description --weight --rubric
dast-eval criteria set-weight --id --weight
dast-eval criteria list

dast-eval candidate add --id --name --source --website --notes
dast-eval candidate set-status --id --status
dast-eval candidate record-score --vendor-id --criterion-id --score --evidence --confidence
dast-eval candidate list

dast-eval handson log-observation --vendor-id --context --note --tags
dast-eval handson ingest-scan-result --vendor-id --benchmark-id --file --test-id --description --automated

dast-eval status   # reports vendors missing a score for any current criterion, and weight-total warnings
dast-eval render   # renders reports/scorecard-<id>.md, comparison-matrix.md, comparison-matrix.xlsx, dashboard.html
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
reports/                   # generated output — never hand-edited, regenerated via `dast-eval render`
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
