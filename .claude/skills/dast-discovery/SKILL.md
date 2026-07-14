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

For every new candidate being researched (whether stakeholder-seeded from
Step 2 or discovered here), also identify the vendor's own named major
product lines or modules — not just its core DAST product (for example,
a dedicated ASPM platform, an attack-surface-management module, or an
analytics/reporting product with its own brand name). Log these in the
discovery observation alongside the rest of the rationale. This matters
downstream: `dast-shortlist`'s later criterion-by-criterion research
searches using generic rubric language (e.g. "ASPM integration"), which
can miss a vendor's own specifically-named product page if that name
isn't already known going in — capturing it here lets that later
research search precisely instead of generically.

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
