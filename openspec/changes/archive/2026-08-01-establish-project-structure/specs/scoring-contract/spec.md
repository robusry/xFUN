## ADDED Requirements

### Requirement: Models are pure functions over a match snapshot

Every scoring model SHALL be implemented as a pure function accepting a `MatchSnapshot` and returning a `ModelScore`. A model SHALL NOT perform network calls, read from or write to a database, read from the filesystem at scoring time, or depend on wall-clock time. All inputs a model uses SHALL arrive through its `MatchSnapshot`.

#### Scenario: A model is run twice on identical input

- **WHEN** a model is invoked twice with byte-identical `MatchSnapshot` input
- **THEN** it returns identical `ModelScore` output

#### Scenario: A model attempts direct data access

- **WHEN** a model package declares a dependency on a database driver or HTTP client
- **THEN** CI fails the model package's purity check

#### Scenario: A model is evaluated in a notebook

- **WHEN** a data scientist loads a snapshot fixture from `contracts/fixtures/snapshots/` and calls the model directly
- **THEN** the model produces a score with no supporting services running

### Requirement: Models declare their required features

Each model SHALL declare the set of snapshot features it requires. The scoring runtime SHALL assemble only the declared features for that model, and SHALL skip a match for a model whose required features are unavailable for that match, recording the skip and its reason rather than emitting a score.

#### Scenario: Required data is missing for some matches

- **WHEN** a model requires shot-level data and that data is unavailable for a given league
- **THEN** the model produces no rows for matches in that league, other models continue to produce rows for those matches, and the pipeline run succeeds

#### Scenario: A model declares an unknown feature

- **WHEN** a model declares a required feature that is not defined in `contracts/schemas/match-snapshot.json`
- **THEN** model registration fails with an error naming the unknown feature

### Requirement: Models are mutually independent

A model package SHALL NOT import another model package, and a model SHALL NOT read any other model's output. Model packages SHALL depend only on `packages/scoring-contract/`.

#### Scenario: A model attempts to consume another model's score

- **WHEN** a model package imports another model package or queries the score store
- **THEN** CI fails the dependency check for that package

#### Scenario: Models are run in arbitrary order

- **WHEN** the scoring runtime executes registered models in any order, or in parallel
- **THEN** the resulting scores are identical regardless of ordering

### Requirement: Model identity and versioning

Each model SHALL have a stable kebab-case `model_id` that never changes for the lifetime of the model, and a `model_version` that SHALL be incremented whenever a change alters the model's output for unchanged input. Every `ModelScore` SHALL carry both.

#### Scenario: A model's weights are retuned

- **WHEN** a model's parameters change such that it produces different scores for the same snapshot
- **THEN** its `model_version` is incremented and its `model_id` is unchanged

#### Scenario: A model is refactored without behavior change

- **WHEN** a model's implementation is restructured but produces identical output for all fixture snapshots
- **THEN** `model_version` may remain unchanged, and the fixture-based regression test confirms output equivalence

### Requirement: ModelScore carries a raw score, components, and provenance

A `ModelScore` SHALL contain a `raw_score` on the model's own native scale, a `components` map decomposing the score into named contributing factors for explanation, and the `snapshot_hash` of the input it was computed from. Models SHALL NOT emit a calibrated or normalized score; normalization is the platform's responsibility.

#### Scenario: A user asks why a match scored highly

- **WHEN** a score is retrieved for a match
- **THEN** the `components` map is available and identifies the named factors that drove the score

#### Scenario: Models use different native scales

- **WHEN** one model emits a probability in [0,1] and another emits an unbounded z-score
- **THEN** both are valid `raw_score` values and neither model is required to rescale its output
