## Why

Every match in the system is invented. `contracts/fixtures/snapshots/*.json` holds eight
fabricated fixtures, and `scripts/demo.sh` scores them, so nothing a collaborator sees
corresponds to a match anyone can watch. The cheapest way to make the skeleton mean
something is to fill it with matches that are really on, and to say where a US viewer can
actually watch them — which is also the product's stated scope, and the one part of it
that has never been computable.

This change is deliberately narrow: **which matches exist, and where a US viewer can watch
them.** Nothing a model consumes is in scope — acquisition sits upstream of scoring, and
what models read is the collector tier's concern. That has a consequence worth stating
plainly rather than discovering later: neither registered model's declared features are
satisfied by anything this change produces, so every match is returned with a recorded skip
reason and no composed score. That is the partial-coverage path working correctly on real
data, not a regression, and it is why this change is worth landing before a model-facing
one.

## What Changes

- Ingestion acquires the upcoming slate from a live source (goal.com) rather than reading
  fixture files: home team, away team, kickoff, competition, and US TV providers.
- **BREAKING (internal):** external access is no longer confined to collectors. A second
  tier is permitted it — the schedule source — because it runs *before* a slate exists and
  therefore cannot be a collector, whose interface takes a slate as input.
- The slate selection rule becomes `us-watchable` over a **10-day window from query time**,
  replacing the `league-allowlist` placeholder. A match is admitted only when a US provider
  is known for it. `us-watchable` is already in the `slate.json` enum; no schema change.
- Broadcast providers resolve in two steps: per-match data from the source, falling back to
  a hand-maintained `league -> US providers` rights table for leagues whose rights are
  league-wide and constant.
- Availability is persisted and served for real. The API stops returning a hardcoded
  `{"status": "unknown", "providers": []}`.
- Fixture ingestion remains the default path so a fresh clone still runs `./scripts/demo.sh`
  with no credentials and no network.

## Capabilities

### New Capabilities

- `schedule-acquisition`: how the set of upcoming matches and their US broadcast providers
  is acquired before a slate exists — the source, the window, provider resolution and its
  precedence, the `us-watchable` rule, and what happens when the source is unavailable.

### Modified Capabilities

- `data-collection`: the requirement "Collectors are the only tier permitted external
  access during a run" is restated. External access is confined to two tiers distinguished
  by when they run relative to the slate — the schedule source before it, collectors after
  it. Models and the API may touch neither.
- `public-api`: availability becomes substantiated rather than always `unknown`. The
  existing requirement that the system must not assert an answer it cannot substantiate is
  unchanged and now has real cases to govern.

## Impact

**Zones.** Zone B for `packages/ingestion/` and `packages/api/`. Zone C for
`infra/migrations/` and the rights table, which is configuration in the same sense as
`composition/recipes/*.yaml`. Zone A only for added golden fixtures under `contracts/`; no
schema or OpenAPI change is required, because `slate.json` already admits `us-watchable`
and `openapi.yaml` already defines `Availability`.

**Code.** `packages/ingestion/` gains a schedule source and its first network dependency.
`packages/store/` and a new migration gain availability persistence. `packages/api/`
reads availability from the store instead of hardcoding it at `main.py:88`.

**Placeholders resolved in `docs/STUBS.md`.** Three entries: **Ingestion** (`fixture_payloads()`
reads from disk), **The slate rule** (`league-allowlist` placeholder), and **Broadcast
availability** (always answers `unknown`). Each is resolved in part rather than wholly —
acquisition establishes matches and availability, not anything a model reads — and
`docs/STUBS.md` must say so rather than delete the rows.

**Not resolved.** Model input remains entirely on fixture data, so no model scores. Which
tier supplies it is out of scope here and is expected to be the collector tier, since
model-facing data is what that tier exists to fetch. This change takes the schedule half of
`add-live-ingestion` and the whole of `add-broadcast-availability`.

**External dependency.** goal.com is a third-party site with no API contract and no
stability guarantee, read via its published JSON-LD and page state. Its `robots.txt` is
`User-agent: * / Allow: /` with no disallowed paths. It must be recorded in `docs/STUBS.md`
as an unofficial source, and the failure path must be a first-class case rather than an
exception, because it will break without notice.
