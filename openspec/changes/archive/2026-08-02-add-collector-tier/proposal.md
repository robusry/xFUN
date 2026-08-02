## Why

A model can only consume what `contracts/schemas/match-snapshot.json` defines, and that schema is closed (`additionalProperties: false` at every level). A model developer who wants a signal the schema does not carry — pre-match Reddit sentiment, say — must first get a field added to the shared schema and then get another tier to populate it. That is a Zone A change plus work owned by someone else, in order to run an experiment that may not survive the week. The organising principle of this project is that changing your mind should be cheap, and here it is expensive.

The second half of the problem is that nothing shares. `SourceAdapter` yields whole snapshot payloads, so if three models each want Reddit data there is no mechanism that fetches it once. The natural workaround — each model fetching its own — is barred by model purity, and rightly so.

**Why now:** `add-live-ingestion` is the change that selects a data provider and writes real adapters, and it would write them against `SourceAdapter`. Settling the collection interface afterwards means writing those adapters twice. This change, and its two named follow-ups, should land first.

## What Changes

- **The slate becomes a first-class input.** A scoring run begins with the set of matches to be scored — currently a league allowlist within a time window, eventually the matches actually watchable in the US. Collectors receive the whole slate up front and decide their own fan-out, rather than being invoked per match.

- **A collector tier**, sitting between the slate and snapshot assembly. Collectors are impure by design: network access, credentials, and third-party dependencies are expected. They are the only tier permitted to reach outside the process during a scoring run.

- **Collector output is keyed by entity, not always by match.** A collector declares whether it produces values per match, per team, or per league, and the platform joins them onto matches mechanically. Forcing per-match output would make every collector solve attribution, and attribution is opinionated — one model wants strict match-thread matching, another wants loose team-mention sentiment, and baking either into the collector forecloses the other.

- **Dedup resolution.** The union of the active models' declared features determines which collectors run, and each runs exactly once per slate regardless of how many models consume it. A model requiring a feature no collector provides fails at registration rather than silently skipping every match.

- **One flat signal namespace.** Collector output is addressed as `signals.<namespace>.<leaf>`, where the namespace is a subject area rather than a producer identity. Provenance is recorded in the collector run record and is queryable, but never appears in the path — so replacing one producer with another is invisible to every model that declares the path.

- **Collector failure is distinguished from legitimate absence.** "This obscure match has no Reddit thread" and "the Reddit API returned 503" both currently present as a missing feature. They are recorded distinctly, because one is permanent and the other is worth retrying.

- **Feature declaration stays extensible.** The declaration mechanism is specified as open to additional kinds rather than closed to dotted paths, so the corpus-shaped declaration that arrives in follow-up **B** does not require amending a requirement this change froze.

- **BREAKING — `SourceAdapter` is replaced by the collector interface.** The only implementation is `FixtureFileAdapter`, a documented placeholder, so the blast radius is confined to the walking skeleton.

- **CI boundary rules change.** `scripts/check_dependencies.py` gains rules for the new tier: collectors may declare network dependencies, models may not import a collector package, and the API still may not import either.

### Deliberately out of scope

Both are named follow-ups, and this change is sequenced ahead of both:

- **B — `add-collector-corpora`**: the unkeyed corpus escape hatch, content-addressed corpus storage, retention enforcement, and a model's ability to abstain from scoring with a reason. Entangled with `add-score-provenance`, since a corpus is the input a stored score would need to be re-derived.
- **C — `add-signal-derivers`**: pure transforms that publish into the same `signals.*` namespace, so a conventional attribution is available to models that want the easy answer without being mandatory for models that want their own. Mostly pointless before B, since attributing a corpus is the motivating use case.

## Capabilities

### New Capabilities

- `data-collection`: The slate as the unit of a collection run; the collector interface and its impurity boundary; entity-keyed output and the join onto matches; dedup resolution from declared model features; the distinction between collector failure and legitimate absence; and signal namespace ownership.

### Modified Capabilities

- `scoring-contract`: Feature declaration is validated against the set of paths some registered producer provides, not only against `contracts/schemas/match-snapshot.json` — a path that is schema-valid but produced by nobody becomes a registration error. The declaration mechanism is specified as extensible. Models remain pure and mutually independent; sharing a collector's output is coupling through shared input, exactly as two models reading `odds.total_line` are coupled today, and does not weaken the independence requirement.
- `repo-structure`: Adds `packages/collectors/<id>/` to the prescribed layout, revises the tier diagram for the collect → join → score phases, and states the dependency rules CI enforces for the new tier.

## Impact

- **Zones touched: A and B.** Zone A because it changes `contracts/`, `packages/scoring-contract/`, and `packages/scoring-runtime/`. Zone B because `packages/ingestion/` changes observable behaviour — `SourceAdapter` is replaced.
- **Code**: new `packages/collectors/`; `scoring-contract` (declaration types, slate types); `scoring-runtime` (collector registry, resolution, join, run record); `contracts/schemas/match-snapshot.json` (the `signals` namespace) plus a slate schema and fixtures; `packages/ingestion/` (`FixtureFileAdapter` becomes a collector); `scripts/check_dependencies.py`.
- **Not affected**: `packages/api/` (no response shape changes in this change), `packages/composition/`, `packages/store/` score tables, `packages/web/`, `clients/ts/`.
- **Replaces no `docs/STUBS.md` entry.** The ingestion placeholder remains a placeholder — this change reshapes the interface its replacement will implement against, and `docs/STUBS.md` is updated to say so.
- **Sequencing**: `add-collector-tier` → `add-collector-corpora` → `add-signal-derivers` → `add-live-ingestion`.
