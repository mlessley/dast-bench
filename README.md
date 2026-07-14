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

**Phase 1 core library and CLI: done.** Command groups for `criteria`,
`candidate`, `scan`, `benchmark`, plus `status` and `workflow` for
orienting yourself in the pipeline, and `render`, YAML round-tripping via
Pydantic, and Markdown/XLSX/HTML report rendering are implemented and
tested (104 tests passing).

**All six Claude Code skills built and run end to end on a real
evaluation.** `dast-criteria` (taxonomy), `dast-discovery` (candidate
list), `dast-shortlist` (scoring + finalist decisions), `dast-onboard-tool`
(wires a new tool into CI, or produces a manual runbook for tools that
can't be), `dast-scan` (hands-on benchmark scanning — CI-automated or a
manual/HITL path), and `dast-report` (presentation/narrative layer) took a
proof-of-concept batch of three real DAST tools — ZAP, Nuclei, and
StackHawk — through a full evaluation against a 29-criterion taxonomy
spanning coverage, detection quality, production safety, developer
experience, reporting, and deployment/data governance. Those three exist to
exercise every phase of the pipeline end to end; they aren't a fixed or
preferred vendor list — the framework is tool-agnostic, and `dast-discovery`
can surface any number of additional candidates for a real procurement.
See [`sample-report/`](sample-report/) for a committed snapshot of that
evaluation's real output (executive summary, scorecards, comparison
matrix) — the live version is `reports/`, generated locally via `dast-bench
render` + the `dast-report` skill, not tracked in git.

**CI benchmarking pipeline: built, live-verified, multi-tool.** A GitHub
Actions `workflow_dispatch` pipeline (`.github/workflows/dast-benchmark.yml`)
spins up OWASP Juice Shop or VAmPI as an ephemeral service container,
authenticates a test user against it, then dispatches either ZAP or Nuclei
(`tool`/`target` inputs) as the active scanner, uploading both the raw and
normalized report as build artifacts — the normalize step is
tool-parameterized (`.github/scripts/normalize/<tool>.py`), not hardcoded
to one scanner. Ground truth for both benchmark targets
(`data/benchmarks.yaml`) was rebuilt from the union of multiple tools' real
observed findings rather than curated from documentation, so scores
reflect empirically-verified detection rates. Vendors that can't be
dockerized into this pipeline (most commercial/cloud platforms, including
StackHawk in this run) go through `dast-scan`'s manual/HITL path instead,
hand-tested against OWASP's public Juice Shop demo instance.

**Not yet built:**
- Production-safe scanning (drift/misconfiguration detection against a real
  or staging target, as opposed to the ephemeral benchmark targets above) —
  deliberately deferred; see the roadmap doc.
- A TUI or interactive visual dashboard for pipeline progress — considered
  and deliberately deferred in favor of the leaner `dast-bench
  workflow`/`status` text UX above; see the roadmap doc.

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

dast-bench benchmark add --id --name --target-type
dast-bench benchmark add-vulnerability --benchmark-id --vuln-id --name --severity
dast-bench benchmark remove-vulnerability --benchmark-id --vuln-id
dast-bench benchmark list

dast-bench status   # reports vendors missing a score for any current criterion, and weight-total warnings, plus a Progress/Next summary of the whole pipeline
dast-bench render   # renders reports/scorecard-<id>.md, comparison-matrix.md, comparison-matrix.xlsx, dashboard.html
dast-bench workflow # static reference: what each of the six skills does, reads, and writes
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
reports/                   # generated output — never hand-edited, regenerated via `dast-bench render` (plus `dast-report`'s skill-authored `executive-summary.md`); gitignored
sample-report/             # committed, manually-updated snapshot of reports/ for reviewers who aren't running the tool
.github/
  workflows/dast-benchmark.yml       # CI pipeline: ephemeral benchmark target + tool-dispatched active scan (ZAP or Nuclei)
  scripts/normalize/{zap,nuclei}.py  # per-tool report -> generic findings JSON
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
- [TUI visualization roadmap](docs/superpowers/specs/2026-07-11-tui-visualization-roadmap.md) — deferred, parking-lot notes only
