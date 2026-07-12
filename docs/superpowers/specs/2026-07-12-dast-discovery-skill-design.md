# dast-discovery Skill Design

## Purpose & Context

`dast-discovery` is Phase 2 of the dast-bench evaluation workflow: it
builds the **candidate list** — the set of DAST vendors that will later be
scored (`dast-shortlist`) and, for finalists, hands-on tested
(`dast-scan`). It merges two sources: live research into the current DAST
tool market, and any stakeholder-seeded "must include" vendors the
evaluator already knows about. It does not score or evaluate anything —
that is `dast-shortlist`'s job. `dast-criteria` (built 2026-07-12) is the
precedent this design follows: a Claude Code skill (prompt file, no code
of its own) that converses with the evaluator before persisting anything,
and mutates data only through the existing `dast-bench` CLI.

## Goals

- Build/extend the candidate list via live web research (not a fixed
  baseline — the DAST market changes continuously, unlike a criteria
  taxonomy, so freshness matters more than determinism here).
- Merge in stakeholder-seeded must-include vendors, which can also anchor
  the market search ("find more tools like these").
- Every candidate's rationale must cite its actual sources (URLs, report
  names) — never a paraphrased summary standing alone as unverifiable
  fact.
- Support re-invocation non-destructively: research from a later run adds
  new, dated notes to existing candidates rather than overwriting or
  discarding what an earlier run already captured.
- Support evaluator-supplied reference material (a URL or local file for a
  specific candidate — e.g. a non-public product PDF) without requiring
  any new ingestion infrastructure.

## Non-Goals / Out of Scope

- Scoring or ranking candidates against criteria — `dast-shortlist`'s job.
- Deciding finalists or running hands-on tests — `dast-shortlist`'s and
  `dast-scan`'s jobs respectively.
- **A formal RAG / reference-document-corpus system** — considered and
  explicitly rejected for this project. RAG's value is fast repeated
  retrieval over a large, relatively static corpus you've already indexed;
  discovery's "corpus" (which vendors currently exist) changes
  continuously and is queried once per discovery run, not repeatedly
  against a fixed index — so building a vector-indexed corpus just to do
  one discovery pass is pure overhead with no reuse benefit. The narrower,
  real need (occasionally hand the skill one reference document) is
  supported directly via `WebFetch`/`Read` with no new infrastructure. A
  genuinely reusable, multi-skill reference-corpus system remains a
  plausible future idea but is out of scope here — not deferred to a
  roadmap doc, since the evaluator judged it unwarranted for this
  project's actual scale, not merely postponed.
- Building the other three remaining skills (`dast-shortlist`, `dast-scan`,
  `dast-report`) — each gets its own brainstorm.

## Architecture

`dast-discovery` is a Claude Code skill: a prompt file at
`.claude/skills/dast-discovery/SKILL.md`, invoked as `/dast-discovery`. It
contains no code — it is instructions for an LLM agent that (a) checks
current candidate state via the CLI, (b) researches live using
`WebSearch`/`WebFetch` (no baked-in baseline, unlike `dast-criteria`,
since market data goes stale), and (c) persists every new or updated
candidate by shelling out to `dast-bench candidate` commands, never
editing YAML directly.

One CLI change is included in this plan: **`log-observation` relocates
from the `scan` command group to `candidate`** (becoming
`candidate log-observation`). It is a phase-agnostic "attach a dated note
to a vendor record" capability — useful to discovery, shortlist, and scan
alike — that only ended up under `scan` as a leftover from when that phase
was named `handson`. `ingest-scan-result` stays under `scan`, since it is
genuinely scan-specific (DAST tool output ingestion). This is a pure
relocation: the function body, its tests' assertions, and its behavior are
unchanged — only the Typer sub-app it's registered under, and therefore
its invoked command path, changes.

Evaluator-supplied reference material (a URL or local file path for a
specific candidate) is handled directly by the skill using `WebFetch`/
`Read` — no new data model field, storage location, or CLI command. The
resulting information is folded into that candidate's rationale note like
any other research finding.

## Components

1. **`.claude/skills/dast-discovery/SKILL.md`** — the skill file: checks
   existing candidates, asks about seeded must-includes, researches the
   market (optionally anchored by seeded vendors and/or evaluator-supplied
   reference material), presents findings with sources, and persists only
   after the evaluator confirms.
2. **CLI relocation in `core/cli.py`**: `log_observation` moves from
   `scan_app` to `candidate_app`, registered as `candidate log-observation`.
   Its existing tests move from `tests/test_cli_scan.py` to
   `tests/test_cli_candidate.py` with the invoked command list updated from
   `["scan", "log-observation", ...]` to `["candidate", "log-observation", ...]`
   — same assertions, same behavior, corrected location only.
3. **No model changes.** `Vendor`, `VendorSource`, `VendorStatus`, and
   `Observation` (with its existing `context`/`note`/`tags`/`timestamp`
   fields) are reused exactly as-is — `Observation`'s shape already
   satisfies "dated, append-only, source-citing note."

## Data Flow

1. Skill runs `dast-bench candidate list` to see current candidates —
   never re-researches or re-proposes a vendor already known.
2. Skill asks the evaluator: any stakeholder-seeded must-include vendors
   for this round? These can double as search anchors for the broader
   market research that follows.
3. Skill performs live market research via `WebSearch`/`WebFetch`,
   cross-referencing findings against the existing candidate list.
4. If the evaluator hands the skill a URL or local file path for a
   specific candidate, the skill `WebFetch`/`Read`s it directly and folds
   the findings into that candidate's rationale, alongside or instead of
   general web research for that vendor.
5. Skill presents every new candidate found — name, website, rationale,
   and the actual sources (URLs, report names) it drew on — to the
   evaluator before persisting anything.
6. Once confirmed, for each new candidate: `dast-bench candidate add --id
   <id> --name <name> --source <seeded|discovered> --website <website>
   --notes <notes>`, then `dast-bench candidate log-observation
   --vendor-id <id> --context "discovery research" --note "<rationale
   with cited sources>" --tags discovery` to capture the dated, sourced
   rationale.
7. For existing candidates where research surfaces genuinely new
   information on a later invocation, the skill logs an *additional*
   `log-observation` entry — it never edits or removes a prior one.
8. Skill summarizes what was added/updated as confirmation.

## Error Handling

- `candidate add` on a duplicate id (shouldn't occur in practice, since
  the skill checks `candidate list` first, but could on an id collision)
  — relay the `error: ...` message verbatim and pick a different id or ask
  the evaluator; do not retry blindly.
- `candidate log-observation` on an unknown vendor-id — same
  relay-verbatim handling, though this shouldn't occur since it is always
  called immediately after a successful `add`.
- Research is inherently uncertain: if sources conflict or a claim can't
  be corroborated, the skill states that uncertainty directly in the
  rationale rather than presenting a guess as settled fact.
- If an evaluator-supplied URL or file can't be fetched/read (broken link,
  corrupt file, access denied), the skill reports this to the evaluator
  directly and continues with the rest of discovery rather than blocking
  on it.

## Testing

The CLI relocation is a real code change and gets real TDD: move
`log_observation`'s existing tests from `tests/test_cli_scan.py` to
`tests/test_cli_candidate.py`, updating only the invoked command list;
`tests/test_cli_scan.py` keeps just the `ingest-scan-result` tests. The
skill file itself is not unit-tested (same reasoning as `dast-criteria`)
— reviewed by the evaluator reading it once written, not by an automated
test.
