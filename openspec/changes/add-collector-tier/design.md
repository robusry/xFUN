## Context

Today a model's entire input is a `MatchSnapshot` whose shape is fixed by `contracts/schemas/match-snapshot.json`, a closed schema. `Registry.register` rejects any `required_features` path the schema does not define, so a model cannot ask for data the platform has not already agreed to carry. Data arrives through `SourceAdapter`, which yields whole snapshot payloads and therefore offers no way for several models to share one fetch of a source.

The constraint bundles two separate things. **Purity at scoring time** — no network, no clock, no filesystem inside `score()` — buys reproducibility, fixture-testability, and order-free parallel fan-out, and is worth keeping. **A closed, centrally-owned feature vocabulary** buys much less, and is what actually blocks a developer who wants to try a new signal.

This design separates them: scoring stays pure, and data acquisition moves into a tier that is allowed to be impure, owned by whoever needs it, and shared by everyone who declares it.

The walking-skeleton state helps here. `FixtureFileAdapter` is the only `SourceAdapter` implementation and is a documented placeholder, so replacing the interface costs almost nothing today and costs a great deal after `add-live-ingestion` writes real adapters against it.

## Goals / Non-Goals

**Goals:**

- A model developer can bring a new data source without amending the shared schema or asking another tier for work.
- A source is fetched once per slate no matter how many models consume it.
- Each collector chooses its own fan-out strategy; the platform does not impose per-match iteration.
- Attribution of loosely-keyed data to matches stays a model-level choice rather than a collector-level one.
- Scoring keeps every property it has today: purity, determinism, order independence, skip-with-reason.
- Follow-ups B and C extend this without amending requirements frozen here.

**Non-Goals:**

- The corpus escape hatch, content-addressed corpus storage, and model abstention. Follow-up **B**.
- Derivers — pure transforms publishing into `signals.*`. Follow-up **C**.
- Selecting a real data provider or writing a real collector. `add-live-ingestion`.
- Any change to API response shapes.
- Persisting assembled snapshots. `add-score-provenance`.

## Decisions

### D1. The slate is the input to collection, not the match

A collection run begins with the full set of matches to be scored. Collectors receive it whole and fan out however suits their source: an odds collector iterates matches and queries each; a Reddit collector reads `slate.teams()` and polls team subreddits plus general ones; a league-table collector makes one call per league.

*Rejected:* `collect(match) -> features`, invoked per match. It forces N calls where one would do, and pushes batching into every collector as a private cache. The slate is knowable in advance — the product scope is a defined set of watchable matches — so there is no reason to hide it.

*Cost accepted:* A collector cannot be invoked for a single ad-hoc match without constructing a one-match slate. Acceptable; scoring is a batch pipeline by design.

### D2. Collectors are a tier, not a model capability

An earlier sketch hung an impure `collect()` off the model itself. Sharing kills it: if three models want Reddit data, no one model owns the fetch. Collectors get their own identity, their own package directory, and their own registration.

*Rejected:* model-owned collectors. Simpler to explain, but every shared source would be fetched once per consuming model, which is the problem this change exists to solve.

*Cost accepted:* A developer contributing a new signal writes two packages rather than one — a collector and a model. Both are small, and the split is what makes the signal reusable.

### D3. Collector output is entity-keyed; the join set is closed

A collector declares the entity its output is keyed by. The platform joins onto matches mechanically:

| Keyed by | Join | Result |
|---|---|---|
| `match` | identity | scalar |
| `team` | fans into the two sides | `{home, away}` pair |
| `league` | broadcast to every match in the league | scalar |

The team case already has a precedent: `form.home` / `form.away` are a team-keyed value joined onto a match. This generalises an existing pattern rather than inventing one.

*Rejected:* requiring every collector to return `match_id -> features`. That forces the collector to solve post-to-match attribution, which is a judgement call, not a mechanical one — strict match-thread matching and loose team-mention matching are both defensible, and a collector that picks one forecloses the other for every consumer.

*Cost accepted:* Three join kinds is a small amount of machinery that did not exist before, and the set is deliberately not extensible without a spec change. A genuinely unkeyed source has no home until follow-up B.

### D4. Two phases, not a collector graph

Collection is one pass over independent collectors. No collector consumes another's output. Follow-up C adds a second pass of pure derivers, which read collector output but not each other — so the pipeline is always collect-then-derive, never an arbitrary DAG.

*Rejected:* a general collector DAG. It reintroduces exactly what the project forbids among models: ordered execution, sequenced backfills, and a dependency graph that makes reversal expensive. The fetch-once-derive-many shape that motivates a DAG is served by the fixed two-phase split instead.

*Cost accepted:* A collector that wants to derive several values from one fetch must publish them all itself until C lands.

### D5. One flat signal namespace; provenance never appears in the path

Collector output is addressed as `signals.<namespace>.<leaf>`. The namespace is a subject area, not a producer id: several producers may contribute to one namespace, and the registry enforces that exactly one producer claims any given leaf path. Which producer supplied a value, and whether it was fetched or computed, is recorded in the collector run record and is queryable there.

*Rejected:* splitting by provenance — `signals.*` for fetched, `derived.*` for computed. It reads well until a producer changes. If `reddit-attribution` computes `match_volume` today and Reddit later exposes it directly, swapping the deriver for a collector would move the path, breaking every model that declares it. A path is the model-facing vocabulary; it should encode what a value means, not how it was obtained. This mirrors the alias indirection already used for composition, where `default` is a stable public name over a swappable recipe.

*Cost accepted:* Provenance requires a lookup rather than being legible from the path. Worth it — the alternative makes a cheap producer swap into a tier-wide migration.

### D6. Resolution is driven by declared model features

The union of the active models' declared features determines which collectors run. A collector no active model depends on does not run. A model declaring a path no registered producer provides fails at registration.

This extends the existing registration philosophy: a typo in `required_features` should be a loud registration error, not a model that quietly never scores anything. Today that check is against the schema; it becomes a check against the schema *and* the provider registry, since a path can now be schema-valid and produced by nobody.

*Rejected:* running every registered collector regardless of demand. Simpler, but pays network cost and rate limits for data nothing consumes.

*Cost accepted:* Registration order matters — collectors must be registered before models are validated against them.

### D7. Collector failure is recorded distinctly from legitimate absence

"This obscure match has no Reddit thread" is permanent and correct. "The Reddit API returned 503" is transient and worth retrying. Both currently surface identically as a missing feature. The collector run record captures which occurred, per collector per slate, and the skip reason reflects it.

*Rejected:* treating all absence alike. It is cheaper, and it makes coverage statistics silently wrong — a source that is down for a week looks like a source that has nothing to say.

*Cost accepted:* A run record is new persisted state, and collectors must distinguish the two cases rather than returning nothing in both.

### D8. Retention policy is decided here, enforced in B

The forcing question is not how long corpora live but what happens to a score whose input is gone — and since the score store is append-only, deleting the score is not available. So:

- Retention is declared per collector, defaulting to indefinite. Payload size is a property of the source, not the platform; a text corpus and a video corpus are different conversations, and the author knows which they have.
- A platform-wide floor no collector may declare below, proposed as the current season — already a meaningful unit here, since `season` is a named calibration cohort.
- When retained data expires, referencing scores remain and are flagged non-reproducible. Never deleted, never silently implied re-derivable. This is the same move as broadcast availability answering `unknown`: an admitted gap beats confident wrongness.
- Data no stored score references is collectable immediately.

The flag is computed at read time from whether the input is still present, not stored on the score row — consistent with calibration and composition being derived rather than materialised, because it is a property of current state rather than of the row.

*Rejected:* keeping everything forever unconditionally (unbounded cost the first time a collector returns media), and a global TTL (ignores that collectors differ by orders of magnitude in payload size).

*Cost accepted:* Reproducibility becomes a promise with a horizon rather than an absolute. Stating the horizon is better than implying an absolute the system cannot honour.

### D9. Feature declaration is extensible, not closed

The declaration mechanism is specified as open to additional kinds, with dotted paths as the only kind this change defines. Follow-up B adds a corpus-shaped declaration whose coverage is determined by the model rather than the platform.

*Rejected:* closing the declaration to dotted paths now and amending it in B. Cleaner as a single artifact, but it would freeze a requirement we already know is wrong, and spend a spec amendment to unfreeze it.

*Cost accepted:* A slightly looser requirement now, in exchange for not writing a known-wrong one.

### D10. Model independence is unchanged

Three models reading `signals.reddit.home.sentiment` is coupling through shared *input*, exactly as three models reading `odds.total_line` are coupled today. The requirement that survives is the one that was always the point: a model never reads another model's *output*. A new CI rule keeps it honest — a model package may name a signal path but may not import a collector package.

*Cost accepted:* None. This decision is recorded because the objection is predictable in review, not because a trade is being made.

### D11. `SourceAdapter` is replaced, not kept alongside

`FixtureFileAdapter` becomes a collector. The old interface is removed rather than deprecated.

*Rejected:* running both interfaces during a transition. There is one implementation and it is a placeholder; a compatibility shim would outlive its usefulness immediately and would still be there when `add-live-ingestion` lands.

*Cost accepted:* A breaking change, with a blast radius of one placeholder class.

## Risks / Trade-offs

**Sharing concentrates failure** → Reddit goes down and three models skip instead of one. Mitigated by D7 making the cause legible rather than by avoiding the concentration, which is inherent to fetching once.

**Collector cadence silently multiplies stored scores** → a chatty collector changes the assembled snapshot often, and every change mints a new append-only row for every dependent model. Mitigated by making refresh cadence an explicit per-collector declaration reviewed alongside the collector, rather than an emergent property of how often the pipeline runs.

**The slate is defined by something that does not exist** → "matches watchable in the US" is what broadcast availability determines, and that endpoint always answers `unknown`. Mitigated by making the slate definition pluggable and recorded with the run: it starts as a league allowlist within a window and becomes broadcast-derived later, without the collector interface changing.

**Collector purity cannot be enforced the way model purity is** → the whole point of the tier is that it does I/O, so CI cannot check it by banning imports. Mitigated by inverting the rule: CI enforces that models and the API do not import collectors, and collectors are constrained by review and by their declared retention and cadence instead.

**The tier could accumulate business logic** → a collector that starts interpreting rather than fetching becomes an unversioned, untestable model. Mitigated by C giving interpretation a proper home, and by keeping the join set closed so collectors cannot express match-level judgement through it.

## Migration Plan

No data migration: there is no production data, and the score store is untouched by this change.

1. Land `add-collector-tier`: slate, collector interface, registry, resolution, join, run record, CI rules. `FixtureFileAdapter` becomes a collector; `SourceAdapter` is removed. `docs/STUBS.md` records that the ingestion placeholder now targets the collector interface.
2. Land `add-collector-corpora` (B): corpus escape hatch, content-addressed storage, retention enforcement, model abstention. Coordinates with `add-score-provenance`.
3. Land `add-signal-derivers` (C): the pure second phase.
4. Then `add-live-ingestion` selects a provider and writes real collectors against a settled interface.

Rollback is a revert while the tier has no real collectors. After step 4 it is not, which is the argument for the sequencing.

## Open Questions

- **The retention floor.** "Current season" is proposed but not settled, and it interacts with how far back the evaluation harness will eventually want to look — a question that cannot be answered before there is a ground-truth label.
- **Slate identity.** A slate must be addressable so that collected data is interpretable alongside the slate that produced it. Whether that is a content hash, a run id, or both is unresolved.
- **Whether provenance eventually surfaces publicly.** The run record is internal in this change. If consumers should be able to ask why a match went unscored in more detail than the current reason string, that is a `public-api` change, deliberately not made here.
- **Whether cadence belongs to the collector or the run.** Declared per collector in this design, but a slate close to kickoff plausibly wants everything refreshed regardless of individual declarations.
