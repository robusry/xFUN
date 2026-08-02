> **Scope: the collection mechanism, not real data.** This change delivers the slate,
> the collector tier, the entity join, and dedup resolution. Every collector it ships is a
> placeholder reading fixtures — selecting a real provider is `add-live-ingestion`, which is
> sequenced after this change and its two follow-ups. Anything placeholder MUST be marked as
> such and name the follow-up change that replaces it (see section 10).

## 1. Contracts

- [x] 1.1 Add the `signals` object to `contracts/schemas/match-snapshot.json`, open under `signals.<namespace>` so a collector can add a namespace without amending the core schema, while the rest of the schema stays closed
- [x] 1.2 Define `contracts/schemas/slate.json` — the match set for a run, plus the identity by which the run records which slate it used
- [x] 1.3 Define `contracts/schemas/collection-run.json` — collectors invoked, outcome of each, and the failure-versus-absence distinction
- [x] 1.4 Add golden fixtures covering a team-keyed signal present on one side only, a league-keyed signal, and a collector failure
- [x] 1.5 Extend `scripts/validate_contracts.py` to cover the new schemas and fixtures — schema coverage; the `slate_id` content-hash consistency check lands with `Slate` in 2.1

## 2. Scoring contract

- [x] 2.1 Add `Slate` and `MatchRef` types — enough match identity for a collector to fan out, and nothing more
- [x] 2.2 Add the `Collector` protocol: identity, declared entity kind, declared provided paths, declared refresh cadence, and `collect(slate)`
- [x] 2.3 Add the `EntityKind` enumeration (`match`, `team`, `league`) as a closed set
- [x] 2.4 Express feature declaration so further declaration kinds can be added without replacing the existing one (see design D9; the corpus kind arrives in `add-collector-corpora`)
- [x] 2.5 Add a collection outcome type that distinguishes "no data for this entity" from "could not determine whether data exists"

## 3. Scoring runtime

- [x] 3.1 Add the collector registry: reject a duplicate collector id, and reject two producers claiming the same leaf path
- [x] 3.2 Validate model feature declarations against the union of provided paths as well as the snapshot schema; a well-formed path nothing provides fails registration
- [x] 3.3 Implement resolution — union the active models' declared features, map to the collectors that provide them, invoke each at most once, and skip collectors with no consumers
- [x] 3.4 Implement the three joins: match by identity, team onto home and away sides, league broadcast across the league
- [x] 3.5 Assemble joined signals into the snapshot before hashing, so a signal change is visible in `snapshot_hash`
- [x] 3.6 Record the collection run: slate, collectors invoked, per-collector outcome
- [x] 3.7 Carry the failure-versus-absence distinction into the skip reason recorded by the runner

## 4. Collector packages

- [x] 4.1 Create `packages/collectors/` with a README stating that this is the only tier permitted external access during a run
- [x] 4.2 **PLACEHOLDER** — port `FixtureFileAdapter` to a match-keyed fixture collector. Reads files, talks to nothing. *Replaced by `add-live-ingestion`.*
- [x] 4.3 **PLACEHOLDER** — add a team-keyed fixture collector so the home/away join is exercised end to end rather than only in tests. *Replaced by `add-live-ingestion`.*
- [x] 4.4 Mark both in each package README and in `docs/STUBS.md` — plus new STUBS entries for the collectors and the slate rule
- [x] 4.5 **PLACEHOLDER** — add a league-keyed fixture collector too, so the third join is not left unit-tested only. *Replaced by `add-live-ingestion`.*
- [x] 4.6 **PLACEHOLDER** — add a `social-buzz` model declaring `signals.*`, so the collector tier is reachable from the demo rather than dormant and the golden `signals` blocks are reproduced by a run rather than merely asserted. Kept out of `recipes/default.yaml`. *Replaced by the first validated social model.*

## 5. Ingestion and slate assembly

- [x] 5.1 **PLACEHOLDER** — assemble the slate from a league allowlist within a time window. *Replaced by `add-broadcast-availability`, which makes "watchable in the US" answerable.*
- [x] 5.2 Record the slate with the run so collected data stays interpretable alongside the slate that produced it
- [x] 5.3 **BREAKING** — remove `SourceAdapter` and its tests; the collector protocol replaces it
- [x] 5.4 Update `packages/ingestion/README.md` for the narrowed responsibility: slate assembly and snapshot writing, not source adapters

## 6. Store

- [ ] 6.1 Add a migration for the collection run record, following the existing plain-`.sql` filename-order convention
- [ ] 6.2 Add read paths for the run record sufficient to answer why a given match went unscored by a given model

## 7. CI and tier boundaries

- [ ] 7.1 Extend `scripts/check_dependencies.py`: no model package and no API package may import or depend on a collector package
- [ ] 7.2 Exempt collector packages from the model purity rules, with a comment stating why the inversion is deliberate
- [ ] 7.3 Confirm the existing rule that a model depends only on `xfun-scoring-contract` still holds unchanged

## 8. Tests

- [ ] 8.1 Resolution: three models sharing one collector invoke it once
- [ ] 8.2 Resolution: a collector with no consumers is not invoked
- [ ] 8.3 Registration: duplicate provider for a leaf path fails; a declared path nothing provides fails
- [ ] 8.4 Join: team-keyed value present for one side only leaves the other absent and produces a skip with a reason
- [ ] 8.5 Failure path: one collector fails, the run completes, dependent models skip, and the skip is attributable to failure rather than absence
- [ ] 8.6 Ordering: collectors run in any order and produce an identical assembled snapshot
- [ ] 8.7 Update `scripts/pipeline.py` so the end-to-end fixture run exercises collection, join, and scoring

## 9. Documentation

- [ ] 9.1 Update `docs/architecture.md` with the collect → join → score phases
- [ ] 9.2 Update `docs/zones.md`: the collection mechanism is Zone A, an individual collector is Zone B
- [ ] 9.3 Update `docs/STUBS.md` — the ingestion placeholder now targets the collector interface, and the fixture collectors are named
- [ ] 9.4 Update `CLAUDE.md` layout and design summary for the new tier

## 10. Follow-ups this change deliberately defers

- [ ] 10.1 Open `add-collector-corpora` (**B**) — unkeyed corpus escape hatch, content-addressed storage, retention enforcement per design D8, and model abstention. Coordinates with `add-score-provenance`
- [ ] 10.2 Open `add-signal-derivers` (**C**) — the pure second phase publishing into `signals.*`, giving shared attribution without making it mandatory
- [ ] 10.3 Confirm `add-live-ingestion` is re-scoped to write collectors rather than source adapters, and sequenced after B and C
