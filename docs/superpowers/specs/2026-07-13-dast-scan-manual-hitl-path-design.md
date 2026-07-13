# dast-scan Manual/HITL Hands-On Path — Design

## Purpose & Context

`dast-scan` currently has a dead end. Step 2 checks whether a finalist
vendor's tool is wired into the CI benchmark workflow
(`.github/workflows/dast-benchmark.yml`); if it isn't, the skill says so
and stops — "Stop here for this vendor," verbatim. The only way forward
was `dast-onboard-tool`, which wires a tool into full CI automation (a
new workflow step, docker/CLI invocation, a normalize script) — real,
durable infrastructure investment, appropriate for a tool worth testing
repeatedly, but disproportionate for getting **one** hands-on data point
on a vendor you may only ever test once.

This gap surfaced directly from re-examining the project's own direction:
the vendors likely to actually appear on a real Fortune 500
financial-services shortlist are more likely to be commercial,
cloud-orchestrated DAST platforms (Tier 2/3 in `dast-onboard-tool`'s own
tiering) than self-hostable, dockerizable tools like ZAP/Nuclei (Tier 1) —
the tier this project's CI automation was actually built and dogfooded
against. The manual/HITL path is therefore not a fallback edge case; it's
plausibly the **primary** way most real candidates will ever get hands-on
tested. It has never been made a first-class, well-specified path — this
design fixes that, without touching any of the working Tier 1 CI
automation (`dast-onboard-tool`, the ZAP/Nuclei workflow, their normalize
scripts) that this session's dogfood run already validated.

## Goals

- Replace `dast-scan` Step 2's dead end with a real branch: full CI
  automation via `dast-onboard-tool` (unchanged, for a tool worth
  repeated testing) **or** a new manual/HITL path (for a single hands-on
  data point, no CI investment required).
- The manual path requires no normalizer script and no workflow edit —
  the evaluator (or the skill, on their behalf) hand-authors the generic
  findings JSON directly from whatever report the vendor's own tool
  produces, reconciling vuln IDs against the existing ground-truth
  vocabulary where a clear match exists, same discipline the automated
  normalizers already follow.
- The manual path targets `https://demo.owasp-juice.shop` — OWASP's own
  officially-hosted public Juice Shop demo instance, maintained
  explicitly for this kind of practice/testing — so a commercial vendor's
  cloud scanner has something publicly reachable to point at, with zero
  new infrastructure to stand up.
- VAmPI is explicitly out of scope for the manual path (no equivalent
  public instance exists), so `dast-scan`'s "wait for both targets" gate
  must have an explicit exception: a manually-tested vendor with only a
  Juice-Shop result can still have refined scores proposed, with the
  evidence text stating plainly that VAmPI wasn't covered.
- Everything else about `dast-scan` (ground-truth seeding, revision
  detection, score refinement math, the `evaluated` transition, logging
  qualitative observations) applies identically to both paths.

## Non-Goals / Out of Scope

- Hosting VAmPI publicly. Explicitly deferred — solve it only if a real
  shortlisted vendor specifically needs API-focused testing, not
  speculatively now.
- Any change to `dast-onboard-tool`, the ZAP/Nuclei CI workflow, or their
  normalize scripts. This design adds an alternative path; it doesn't
  touch the Tier 1 automation already built and validated.
- Building a reference implementation of "point a real commercial
  vendor's scanner at the demo instance" — this design specifies the
  *skill's instructions* for that flow; actually exercising it requires
  real account access to a real commercial vendor, which isn't available
  yet.
- A general-purpose "convert any vendor's report format" tool. The manual
  path is explicitly hand-authored, one-off, and not expected to scale to
  repeated use — that's what upgrading to `dast-onboard-tool`'s formal
  path is for.

## Architecture

This is a content change to the existing `.claude/skills/dast-scan/SKILL.md`
prompt file — no new CLI commands or model changes. `scan
ingest-scan-result` already accepts any findings JSON file matching the
generic shape (`{vuln_id, severity, description}`) regardless of how that
file was produced; the manual path simply exercises that existing,
already-tested command with a hand-authored file instead of a
CI-artifact-downloaded one.

**Step 2 becomes a real fork:**
- `ci_tool_id` unset or unsupported, and the vendor is worth full CI
  automation → point at `dast-onboard-tool` (unchanged referral).
- `ci_tool_id` unset or unsupported, and the evaluator just wants one
  hands-on data point → proceed directly into the new manual path below,
  no detour through `dast-onboard-tool` required.

**The manual path (new steps, replacing the dead end):**
1. Confirm the evaluator has trial/account access to the vendor's tool.
2. Evaluator points it at `https://demo.owasp-juice.shop` and runs the
   scan themselves, outside this project's CI, using whatever the
   vendor's own tool/workflow normally looks like.
3. Evaluator obtains the vendor's own findings report (dashboard export,
   CSV, JSON — whatever the vendor provides).
4. The generic findings JSON is hand-authored directly (by the evaluator
   or by Claude on their behalf) from that report: for each finding,
   reconcile its vuln ID against the existing Juice Shop ground-truth
   vocabulary (`data/benchmarks.yaml`) wherever a clear match exists;
   findings that don't correspond to a ground-truth entry keep the
   vendor's own native identifier (correctly not matching, same honest
   behavior as the automated normalizers).
5. `dast-bench scan ingest-scan-result --vendor-id <id> --benchmark-id
   juice-shop --file <hand-authored.json> --test-id manual-<date>
   --description "Manual hands-on test, no CI wiring"` — the exact same
   command every other path uses.

**Step 6/7's "both targets" exception:** for a vendor whose only
hands-on result is via the manual path (Juice Shop only, no VAmPI
result exists or ever will), the skill proposes refined
`detection-accuracy`/`false-positive-rate` scores from that single
result once it exists, rather than waiting indefinitely for a VAmPI
result. The proposed evidence text must state explicitly that the score
is based on Juice Shop only and VAmPI wasn't covered — this caveat is
mandatory, not optional, so a reader of the eventual scorecard
understands the evidence is narrower than a CI-tested vendor's.

## Data Flow

1. Skill identifies which finalist to scan (unchanged from today).
2. Skill checks `ci_tool_id` (unchanged from today).
3. **If unset/unsupported:** skill asks the evaluator directly — full CI
   automation via `dast-onboard-tool`, or a quick manual data point right
   now? This is the new fork.
4. **Manual path chosen:** skill confirms the evaluator has access to the
   vendor's tool, tells them to point it at
   `https://demo.owasp-juice.shop`, and waits for them to report back
   with the vendor's findings (however the evaluator obtained them).
5. Skill (or the evaluator) hand-authors the generic findings JSON from
   that report, reconciling vuln IDs against the existing Juice Shop
   ground truth where a match exists.
6. Skill runs `scan ingest-scan-result` exactly as any other path does.
7. Skill checks: does this vendor now have a Juice-Shop result? If so
   (regardless of whether a VAmPI result exists or ever will for this
   vendor), proceed to score refinement, with the mandatory
   Juice-Shop-only caveat in the evidence text if VAmPI genuinely isn't
   covered.
8. Everything downstream (persisting scores, the `evaluated` transition,
   qualitative observations via `log-observation`) is unchanged from the
   existing skill.

## Error Handling

- If the evaluator doesn't have access to the vendor's tool at all (no
  trial, no account), the skill says so plainly and stops for this
  vendor — same as any other genuinely blocking gap, not a new failure
  mode to invent handling for.
- If the vendor's findings report can't be meaningfully translated into
  the generic shape (e.g., a report with no clear per-finding structure),
  the skill says so explicitly rather than fabricating a findings file,
  consistent with this project's "state uncertainty rather than a
  falsely confident result" discipline used everywhere else.

## Testing

This is a prompt-file-only change — no new CLI commands or model
changes, so no new automated tests. The skill file itself isn't
unit-tested, consistent with every other skill in this project — reviewed
by the evaluator (and, since this is a revision to an already-shipped
skill, by a final whole-branch-style review before considering it
complete).
