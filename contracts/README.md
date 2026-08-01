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

## Rules

- Fixtures are validated against their schemas in CI. A producer that emits
  non-conforming output fails before it can reach a consumer.
- The same fixture files are used by both the producing and the consuming side's
  tests — that is what makes them a contract rather than two sets of sample data.
- `openapi.yaml` is the source of truth for the API. The API is validated *against*
  it; it is not generated *from* the API. Getting this backwards inverts the
  contract-first design.
- Changes here are Zone A: they always require an OpenSpec change with spec deltas,
  and `CODEOWNERS` requires team review.

See `docs/architecture.md` for how the tiers fit together and `docs/zones.md` for
what Zone A means.
