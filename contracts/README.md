# contracts/

The seam between every tier. Language-neutral definitions that ingestion, scoring,
the API, and the clients all agree on.

**This directory contains no executable application code.** If logic belongs
somewhere, it belongs in the consuming package.

```
schemas/          JSON Schema definitions
  match-snapshot.json   ingestion  ->  scoring
  model-score.json      scoring    ->  store  ->  API
openapi.yaml      API  ->  all clients
fixtures/         golden examples, shared by every tier's tests
```

## Why this exists

Tiers are built in parallel by different people, often before the tier upstream of
them exists. That only works if the interface is agreed and there is real data to
develop against. `contracts/` is both.

A web developer with no API deployed generates a client from `openapi.yaml`, serves
`fixtures/` from a mock, and builds the whole interface. A data scientist with no
ingestion pipeline loads a snapshot fixture and iterates on a model. Neither waits
for anyone.

## Two kinds of fixture

Most fixtures here are **authored contract examples**: written by us, validated
against a schema in CI, and used by both sides of a seam. They are the contract.

`fixtures/schedule/` is different. Those are **captured third-party responses** —
reduced copies of goal.com pages. They validate against no schema, because the shape
is not ours to define, and they may be refreshed wholesale when the source changes.
They are test input for the parsers, not an agreement between tiers. Two tools produce
them, and neither paraphrases: each keeps the source's own bytes for a chosen subset.

- `scripts/capture_schedule_fixture.py` writes the dated pages beside this file,
  trimmed to a chosen set of competitions, keeping the schema.org blocks and the page
  state — the two halves the schedule parsers read.
- `scripts/capture_results_fixture.py` writes `fixtures/schedule/results/`, walking
  backwards from a date and trimming each page to matches involving the teams in
  `fixtures/snapshots/`. These carry no schema.org blocks, because scores live only in
  the page state and a fixture holding data nothing reads invites a reader to believe
  it matters. They are what lets `./scripts/demo.sh` run the real `recent-results` scan
  over real historical results with no network.

The distinction matters when one breaks. A failing authored fixture means a producer
violated the contract. A failing captured fixture means somebody else changed their
website, and the fix is usually to recapture and adapt the parser. See `docs/STUBS.md`
for why the project depends on an unofficial source at all.

## Rules

- Fixtures are validated against their schemas in CI. A producer that emits
  non-conforming output fails before it can reach a consumer. Captured fixtures are
  exempt, since there is no schema to validate them against.
- The same fixture files are used by both the producing and the consuming side's
  tests — that is what makes them a contract rather than two sets of sample data.
- `openapi.yaml` is the source of truth for the API. The API is validated *against*
  it; it is not generated *from* the API. Getting this backwards inverts the
  contract-first design.
- Changes here are Zone A: they always require an OpenSpec change with spec deltas,
  and `CODEOWNERS` requires team review.

See `docs/architecture.md` for how the tiers fit together and `docs/zones.md` for
what Zone A means.
