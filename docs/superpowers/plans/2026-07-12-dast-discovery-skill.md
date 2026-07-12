# dast-discovery Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate the `log-observation` CLI command from the `scan` group to `candidate` (where it semantically belongs — a phase-agnostic vendor-note capability, not scan-specific), then write the `dast-discovery` Claude Code skill file itself, per `docs/superpowers/specs/2026-07-12-dast-discovery-skill-design.md`.

**Architecture:** Task 1 is a pure relocation within the existing `core/cli.py` — same function body, same behavior, only the Typer sub-app it's registered under (and therefore its invoked command path) changes, with its tests moved to match. Task 2 writes `.claude/skills/dast-discovery/SKILL.md` — a complete, self-contained prompt file (no code) instructing an LLM agent to check existing candidates, research the DAST market live (no fixed baseline, unlike `dast-criteria`), and persist findings via the CLI only after the evaluator confirms.

**Tech Stack:** Python 3.11+ (via `uv`), Typer, pytest — no new dependencies.

## Global Constraints

- This project uses `uv` for all Python package management — every command uses `uv run ...`, never bare `pip`.
- No placeholder/TODO code.
- Every mutation to `data/candidates/*.yaml` goes through the `dast-bench candidate` CLI — the skill file must never instruct direct YAML edits.
- The relocation of `log-observation` must not change its behavior — same options, same success/error output, same effect on the vendor record. Only its command group changes.
- Every candidate's rationale, as instructed by the skill, must cite actual sources (URLs, report names) — never a paraphrased summary standing alone as unverifiable fact.
- Re-invocation must be non-destructive: new research adds dated notes to existing candidates, never overwrites or removes a prior one.
- Existing test suite (62 tests as of the last commit) must continue passing, accounting for the relocation (a moved test still counts, just in a different file).

---

### Task 1: Relocate `log-observation` from `scan` to `candidate`

**Files:**
- Modify: `core/cli.py` (move the `log_observation` function and its decorator)
- Modify: `tests/test_cli_candidate.py` (append the relocated test, rewritten to use the file's existing `_add_vendor` helper)
- Modify: `tests/test_cli_scan.py` (remove the relocated test — it no longer needs the `Observation`-related setup)

**Interfaces:**
- Consumes: `_load_vendor_or_exit`, `storage.{save_vendor, vendor_path}`, `Observation`, `CANDIDATES_DIR` (all already imported/defined in `core/cli.py` — no import changes needed since `log_observation`'s body is unchanged).
- Produces: `candidate log-observation --vendor-id --context --note --tags` (previously `scan log-observation`) — consumed by the `dast-discovery` skill written in Task 2, and still usable by any other skill/human directly.

- [ ] **Step 1: Write the failing test in `tests/test_cli_candidate.py`**

Append to the end of `tests/test_cli_candidate.py`:

```python
def test_log_observation_appends_to_vendor(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "candidate", "log-observation",
            "--vendor-id", "v1", "--context", "juice-shop crawl",
            "--note", "UI felt sluggish", "--tags", "ux-friction,setup-cost",
        ],
    )
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.observations[0].note == "UI felt sluggish"
    assert vendor.observations[0].tags == ["ux-friction", "setup-cost"]
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `uv run pytest tests/test_cli_candidate.py::test_log_observation_appends_to_vendor -v`
Expected: FAIL — `No such command 'log-observation'` (the `candidate` group doesn't have it yet).

- [ ] **Step 3: Move the command in `core/cli.py`**

Find this block (currently right after `list_candidates`, before `scan_app = typer.Typer()`):

```python
scan_app = typer.Typer()
app.add_typer(scan_app, name="scan")


@scan_app.command("log-observation")
def log_observation(
    vendor_id: str = typer.Option(...),
    context: str = typer.Option(...),
    note: str = typer.Option(...),
    tags: str = typer.Option(""),
) -> None:
    vendor = _load_vendor_or_exit(vendor_id)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    vendor.observations.append(Observation(context=context, note=note, tags=tag_list))
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, vendor_id))
    typer.echo(f"logged observation for '{vendor_id}'")


@scan_app.command("ingest-scan-result")
def ingest_scan_result(
```

Replace it with (the `log_observation` function moves up, before `scan_app` is even defined, registered on `candidate_app` instead; `scan_app` now only ever gets `ingest_scan_result` registered on it):

```python
@candidate_app.command("log-observation")
def log_observation(
    vendor_id: str = typer.Option(...),
    context: str = typer.Option(...),
    note: str = typer.Option(...),
    tags: str = typer.Option(""),
) -> None:
    vendor = _load_vendor_or_exit(vendor_id)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    vendor.observations.append(Observation(context=context, note=note, tags=tag_list))
    storage.save_vendor(vendor, storage.vendor_path(CANDIDATES_DIR, vendor_id))
    typer.echo(f"logged observation for '{vendor_id}'")


scan_app = typer.Typer()
app.add_typer(scan_app, name="scan")


@scan_app.command("ingest-scan-result")
def ingest_scan_result(
```

This is a pure cut-and-paste-and-relabel: the function body is byte-for-byte identical, only its decorator (`@scan_app.command` → `@candidate_app.command`) changed, and it now sits before the `scan_app` Typer instance is created instead of after.

- [ ] **Step 4: Run the new test to verify it passes**

Run: `uv run pytest tests/test_cli_candidate.py -v`
Expected: PASS (7 passed — 6 existing + 1 new).

- [ ] **Step 5: Remove the now-duplicated test from `tests/test_cli_scan.py`**

Remove this function from `tests/test_cli_scan.py` (it has been relocated to `tests/test_cli_candidate.py` in Step 1):

```python
def test_log_observation_appends_to_vendor(tmp_path, monkeypatch):
    _setup_vendor_and_benchmark(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "scan", "log-observation",
            "--vendor-id", "v1", "--context", "juice-shop crawl",
            "--note", "UI felt sluggish", "--tags", "ux-friction,setup-cost",
        ],
    )
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.observations[0].note == "UI felt sluggish"
    assert vendor.observations[0].tags == ["ux-friction", "setup-cost"]
```

Leave everything else in `tests/test_cli_scan.py` unchanged (the `_setup_vendor_and_benchmark` helper and both `ingest-scan-result` tests still need it and stay exactly as they are).

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass (62 total — same count as before, since one test moved files rather than being added or removed: 61 remaining in their original files + 1 relocated = 62), zero failures.

- [ ] **Step 7: Commit**

```bash
git add core/cli.py tests/test_cli_candidate.py tests/test_cli_scan.py
git commit -m "Relocate log-observation from scan to candidate command group"
```

---

### Task 2: The `dast-discovery` skill file

**Files:**
- Create: `.claude/skills/dast-discovery/SKILL.md`

**Interfaces:**
- Consumes: `dast-bench candidate {list, add, log-observation}` (Task 1 + existing commands) — the skill only ever calls these via Bash, never edits YAML. Also consumes the `WebSearch`/`WebFetch`/`Read` tools available in any Claude Code session (not a `dast-bench` interface — general agent tooling).
- Produces: nothing consumed by another task — this is the final deliverable of this plan. Not unit-tested (a prompt file); reviewed by the evaluator reading it.

- [ ] **Step 1: Create the directory and write the complete skill file**

Create `.claude/skills/dast-discovery/SKILL.md` with exactly this content:

````markdown
---
name: dast-discovery
description: Use to build or extend the DAST vendor candidate list via live market research merged with stakeholder-seeded must-include vendors. Re-invocable anytime — each run adds new, dated, sourced findings without overwriting prior research.
---

# dast-discovery

This skill builds and extends the **candidate list** for the DAST tool
evaluation — the vendors that will later be scored (by `dast-shortlist`)
and, for finalists, hands-on tested (by `dast-scan`). It does not score or
rank anything itself, and it never touches vendor scores.

Never edit `data/candidates/*.yaml` directly. Every change happens through
`dast-bench candidate` CLI commands: `add`, `log-observation`, `list`.

Unlike `dast-criteria`, there is no fixed baseline here — the DAST tool
market changes continuously, so this skill always researches live rather
than starting from baked-in content.

## Step 1: Check current candidates

Run `dast-bench candidate list`. Never re-research or re-propose a vendor
that's already in this list — only look for genuinely new information
about it (see Step 5).

## Step 2: Ask about stakeholder-seeded must-includes

Ask the evaluator: are there any specific DAST vendors — from existing
relationships, stakeholder requests, or prior knowledge — that must be
included in this evaluation regardless of what market research turns up?

If yes, these become candidates with `--source seeded`. They can also
anchor the research in Step 3 — e.g. "find other tools similar to these."

## Step 3: Research the market live

Use `WebSearch`/`WebFetch` to research the current DAST tool market:
established players, newer entrants, tools with strong API/SPA coverage
or shadow-API discovery (per this project's evaluation priorities — see
`dast-criteria`'s baseline taxonomy if you want the full priority list).
Cross-reference findings against the existing candidate list from Step 1
so you don't waste effort re-discovering what's already known. These
candidates get `--source discovered`.

## Step 4: Incorporate evaluator-supplied reference material

If the evaluator hands you a URL or a local file path for a specific
candidate (for example, a non-public product PDF or datasheet), fetch or
read it directly (`WebFetch` for URLs, `Read` for local files) and fold
what you find into that candidate's rationale, alongside or instead of
general web research for that vendor. If the fetch/read fails (broken
link, corrupt file, access denied), tell the evaluator directly and
continue with the rest of discovery — do not let this block anything
else.

## Step 5: Present findings before persisting anything

For every new candidate found (from Step 2 or Step 3), present to the
evaluator: name, website, a rationale, and the actual sources you drew on
(URLs, report names — never an unsourced summary presented as fact). Do
not call any CLI command yet. If a source conflicts with another or a
claim can't be corroborated, say so explicitly rather than presenting a
guess as settled fact.

For candidates that already exist (from Step 1) where your research in
Step 3 or Step 4 turned up genuinely new information, prepare that as an
addition, not a replacement — it will become an additional dated note in
Step 6, never an edit to what's already recorded.

Wait for the evaluator's confirmation before moving to Step 6.

## Step 6: Persist via the CLI

For each new candidate the evaluator confirmed:

```
dast-bench candidate add --id <id> --name <name> --source <seeded|discovered> --website <website> --notes <short summary>
dast-bench candidate log-observation --vendor-id <id> --context "discovery research" --note "<full rationale with cited sources>" --tags discovery
```

For an existing candidate with genuinely new information:

```
dast-bench candidate log-observation --vendor-id <id> --context "discovery research" --note "<what's new, with cited sources>" --tags discovery
```

This never touches or removes an existing `log-observation` entry — it
only adds another one, so the full research history for a candidate stays
intact and dated.

If `candidate add` reports `error: vendor '<id>' already exists` (an id
collision, since Step 1 should have already ruled this out) or
`log-observation` reports an unknown vendor id, relay the message verbatim
to the evaluator and ask how to proceed rather than retrying blindly or
guessing a workaround.

## Step 7: Summarize

Once everything agreed in Step 5 has been persisted, summarize for the
evaluator what was added and what was updated, so they have a clear record
of what this run changed.
````

- [ ] **Step 2: Verify the file is valid, complete Markdown with YAML frontmatter**

Run: `head -5 .claude/skills/dast-discovery/SKILL.md`
Expected output starts with:
```
---
name: dast-discovery
description: Use to build or extend the DAST vendor candidate list via live market research merged with stakeholder-seeded must-include vendors. Re-invocable anytime — each run adds new, dated, sourced findings without overwriting prior research.
---
```

Run: `grep -c '^## Step' .claude/skills/dast-discovery/SKILL.md`
Expected: `7` (one per numbered step — confirms none were dropped while writing the file).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/dast-discovery/SKILL.md
git commit -m "Add dast-discovery skill"
```

---

## Self-Review Notes

- **Spec coverage:** the design doc's Architecture section (CLI relocation + skill file), Components (both explicitly covered), Data Flow (Steps 1–7 in the skill file mirror the design doc's 8-step flow, condensed since one design-doc step — "presents findings" — spans what the skill file splits across Steps 4 and 5 for clarity), Error Handling (relay `error:` verbatim, uncertain sources stated explicitly, fetch/read failures don't block), and Testing (Task 1 has real TDD via a moved test; Task 2 is explicitly not unit-tested, matching the `dast-criteria` precedent) are all covered.
- **Placeholder scan:** no TODO/TBD markers; every step has complete content, including the full skill file text.
- **Type consistency:** `log-observation`'s options (`--vendor-id`, `--context`, `--note`, `--tags`) are unchanged from their pre-relocation names, so the skill file's example invocations in Step 6 match exactly what Task 1 produces. `--source <seeded|discovered>` in the skill file matches the existing `VendorSource` enum values exactly (`"seeded"`, `"discovered"`), already used unchanged since the core library was built.
