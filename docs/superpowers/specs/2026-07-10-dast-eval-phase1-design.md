# DAST Tool Evaluation — Agentic Workflow (Phase 1 MVP)

## Purpose & Context

This project supports a formal vendor evaluation of DAST (Dynamic Application
Security Testing) tools/frameworks. The audience and decision process (SME
recommendation vs. committee vote) are not assumed to be fixed in advance,
and existing vendor relationships may or may not be in play. The workflow
must produce defensible, evidence-backed artifacts that work regardless of
how the decision ultimately gets made.

The project is also intended as a demonstration of a small, well-bounded
multi-agent system design applied to a real-world evaluation workflow.

## Goals

- Stay organized, consistent, and impartial across a multi-vendor evaluation.
- Reduce/eliminate administrative and paperwork overhead so effort goes into
  actual evaluation work.
- Produce professional, exec/technical-audience-consumable outputs: a
  comparison matrix and per-vendor scorecards.
- Support a funnel process: broad discovery → paper-based first cut → deep
  hands-on testing of finalists (mixing automated benchmarking with
  subjective "feel" testing).
- Keep a criteria taxonomy that starts from an industry-standard baseline but
  is trivially editable as requirements/feedback evolve, without code
  changes.
- Emphasize evaluation criteria suited to modern application security:
  API/SPA coverage, shadow/zombie API discovery, safe production scanning
  with low instrumentation overhead, and developer-experience-focused
  capabilities (triage, remediation guidance, auto-PR, noise/signal quality)
  as first-class criteria — reducing developer friction is a named goal, not
  an afterthought.
- Design the data/interface layer so that a later port to a different
  orchestration runtime (Phase 2) reuses the same validated data model and
  business logic, minimizing risk of functional drift between phases.

## Non-Goals / Out of Scope (Phase 1)

- No standalone web application or UI (React/Vue explicitly rejected — this
  is a personal utility for one evaluator, not a product for others to use).
- No pre-built automation adapters for every possible DAST tool. Only OWASP
  ZAP is built as a reference adapter in Phase 1; other tools are documented
  as future candidates (see "Hands-On Automation & Benchmarks").
- No modeling of any specific organization's internal decision process
  (voting, committee workflows) — the artifacts are designed to be usable
  under any such process, not tailored to one.
- No database; YAML files are the source of truth (SSoT).
- Phase 2 (porting orchestration to AWS Strands Agents SDK or similar) is
  referenced for forward-compatibility but not designed here.

## Process Overview

Five phases, run roughly in order, with the human evaluator reviewing and
approving before advancing between phases:

1. **Criteria setup** — establish/revise the scoring taxonomy and weights.
   Re-invocable at any time, not a one-time step.
2. **Discovery** — build a candidate shortlist via market research, merged
   with any stakeholder-seeded "must include" vendors.
3. **Shortlist** — desk-research every candidate against the criteria
   taxonomy, record scores with evidence citations, recommend finalists.
4. **Scan** — deeper testing of finalists only: benchmark scans against
   known-vulnerable reference targets (automated where tooling allows) plus
   free-form "play with the tool" observation capture.
5. **Report** — render the SSoT into presentation artifacts (Markdown, HTML,
   spreadsheet); never hand-edited.

## Architecture

Two layers, intentionally decoupled:

- **Core library** (`dast_bench_core`, Python + Pydantic): owns all data
  models, validation rules, and a CLI that is the only sanctioned way to
  mutate the YAML SSoT. This layer is the "interface" that is expected to
  survive a Phase 2 port unchanged — only the orchestration shell around it
  would change (e.g., its functions become native tool definitions for an
  AWS Strands agent).
- **Claude Code skills** (one per workflow phase): each skill is a
  prompt/instruction set that drives an LLM agent through one phase,
  performing the research/reasoning/judgment work, then calling the core CLI
  via Bash for every data mutation rather than editing YAML directly. This
  avoids schema drift or malformed data from freehand LLM file edits.

No standalone server process; this runs as Claude Code sessions against a
local git repository. No separate API metering — Phase 1 usage rides on the
evaluator's existing Claude Code usage.

### Invocation model

- **Phase-advancing steps** (discovery research, shortlist scoring, scan
  test planning, report narrative) require LLM judgment and run as Claude
  Code slash-command skills: `/dast-criteria`, `/dast-discovery`,
  `/dast-shortlist`, `/dast-scan`, `/dast-report`. Internally each shells
  out to the core CLI to persist validated data.
- **Deterministic operations** (checking status/gaps, re-rendering reports
  from existing data, ingesting a scan result file already in hand, manual
  score correction) don't need an LLM and can be run directly from bash via
  the core CLI, e.g. `dast-bench status`, `dast-bench render`, `dast-bench
  scan ingest-scan-result ...`.

## Data Model (Pydantic)

- **`Criterion`**: id, category, name, description, weight, scoring rubric
  (what a 1/3/5 means).
- **`CriteriaTaxonomy`**: versioned list of `Criterion` plus category
  groupings; validates that weights sum to 100%.
- **`Vendor`**: id, name, source (`seeded` vs `discovered`), status
  (`candidate` → `finalist`/`rejected` → `evaluated`), website/notes.
- **`ScoreEntry`**: criterion_id, score, evidence citation, confidence
  (`paper` vs `hands-on`), timestamp.
- **`HandsOnResult`**: test id/description, automated flag, benchmark target
  reference, outcome, observations, timestamp.
- **`Observation`**: freeform ad hoc note captured during "play" sessions —
  vendor, context/benchmark, note text, tags (e.g. `ux-friction`,
  `false-positive`, `setup-cost`).
- **`Benchmark`**: id, name, target type (general/API/SPA), known
  ground-truth vulnerability list, used to compute detection rate and
  false-positive rate per tool.

Each vendor is one YAML file containing its `Vendor` record plus its
`ScoreEntry`, `HandsOnResult`, and `Observation` lists — giving a diffable,
git-native audit trail of how scores and rationale evolved over the
evaluation (including before/after hands-on testing).

## File Layout

```
dast-bench/
  core/                      # Python package: Pydantic models + CLI
    models.py
    cli.py
    render/
      markdown.py
      html.py
      xlsx.py
  data/
    criteria.yaml
    benchmarks.yaml
    candidates/<slug>.yaml
  .claude/skills/
    dast-criteria/
    dast-discovery/
    dast-shortlist/
    dast-scan/
    dast-report/
  reports/                   # generated output — never hand-edited
```

## Agent Roles / Skills

| Skill | Job | Reads | Writes |
|---|---|---|---|
| `dast-criteria` | Scaffold/revise the criteria taxonomy from an industry-standard baseline (OWASP-style categories, informed by DAST vendor-evaluation checklists but reviewed for vendor bias), let evaluator adjust weights. Re-invocable anytime. | — | `criteria.yaml` |
| `dast-discovery` | Research the DAST market, build a candidate shortlist with rationale + sources, merge in stakeholder-seeded must-include vendors. | `criteria.yaml` | `candidates/*.yaml` (status: `candidate`) |
| `dast-shortlist` | Research each candidate against every criterion, record score + evidence + confidence, recommend finalists. | `criteria.yaml`, `candidates/*.yaml` | `candidates/*.yaml` (scores, status transitions) |
| `dast-scan` | For finalists: run/guide benchmark scans against reference targets, capture automated results and ad hoc observations, refine scores. | `candidates/*.yaml`, `benchmarks.yaml` | `candidates/*.yaml` (hands-on results, observations, status: `evaluated`) |
| `dast-report` | Render SSoT into presentation artifacts; surface any criteria/score gaps. | `criteria.yaml`, `candidates/*.yaml` | `reports/` (Markdown, HTML, XLSX) |

## Criteria Extensibility & Gap Detection

The taxonomy is pure data (`criteria.yaml`); adding, removing, or reweighting
criteria never requires a code change. Because criteria can change after some
vendors are already scored, the core CLI provides a gap-detection command
(`dast-bench status`) that reports vendors missing a score for any current
criterion. This check also runs automatically as part of `dast-report`, so
stale/incomplete scoring surfaces before it reaches a presentation artifact
rather than being silently missed.

## Hands-On Automation & Benchmarks

- **Benchmark targets** are first-class config (`benchmarks.yaml`): known
  deliberately-vulnerable applications used for apples-to-apples comparison
  across tools, each with a recorded ground-truth vulnerability list so
  detection rate and false-positive rate can be computed rather than
  eyeballed. Initial targets: OWASP Juice Shop (general/SPA coverage) and an
  API-focused target such as crAPI or VAmPI (matching the priority on
  API/shadow-API detection).
- **Generic scan ingestion**, not bespoke adapters per vendor: `dast-bench
  scan ingest-scan-result` accepts normalized findings (CLI/API JSON output,
  a SARIF file, or manually transcribed results) and maps them against a
  benchmark's ground truth. This is deliberately tool-agnostic since the
  finalist tool set isn't known until after the shortlist cut.
- **One reference adapter in Phase 1: OWASP ZAP.** Free, scriptable
  (CLI/API), and sufficient to prove the automated-scan-to-scorecard pipeline
  end to end. The `dast-scan` skill can drive ZAP directly and pipe output
  into `ingest-scan-result`.
  - **Documented future adapter candidates** (not built in Phase 1): Nuclei
    (free, actively developed, template-based, strong for API/modern-stack
    scanning, complements rather than replaces ZAP's crawler), and Burp Suite
    Professional (self-serve purchase, no sales gate, industry-standard
    scanner) as a commercial-tier reference point.
- **Ad hoc observation capture**: `dast-bench scan log-observation` records
  freeform notes (vendor, context, tags) during unstructured "play with the
  tool" sessions, so impressions aren't lost to a separate notebook and feed
  the same data model as structured results.

## Output Rendering

All formats generated on demand from the YAML SSoT, never hand-edited:

- **Markdown** — per-vendor scorecard + comparison matrix table (wiki/doc
  friendly).
- **HTML** — interactive comparison dashboard rendered via the Artifact tool
  (sortable, presentable live to a technical/exec audience).
- **XLSX** — flattened scorecard export for the familiar "pass it around,
  people annotate it" workflow common in past vendor evaluations.

## Phase 2 (Noted, Not Designed)

When the workflow is validated, `dast_bench_core`'s Pydantic models and CLI
functions are expected to become native tool definitions for an AWS Strands
Agents SDK implementation (or a hybrid Claude Agent SDK + AWS-deployed
shell), reusing the same YAML schema and validation logic. Only the
orchestration layer changes; this design's data contracts are intended to be
the stable surface across that port. Full Phase 2 design is deferred until
Phase 1 is validated in use.
