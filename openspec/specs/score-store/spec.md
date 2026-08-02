# score-store Specification

## Purpose
TBD - created by archiving change establish-project-structure. Update Purpose after archive.
## Requirements
### Requirement: Raw model scores are the system's only score truth

The score store SHALL persist raw model scores as produced by models. Calibrated scores and composed scores SHALL NOT be stored as authoritative data; they are derived views computed from raw scores. Any materialized calibrated or composed data SHALL be treated as a cache that can be discarded and rebuilt at any time without loss.

#### Scenario: Derived data is discarded

- **WHEN** all materialized calibration and composition caches are deleted
- **THEN** every calibrated and composed score can be recomputed from stored raw scores with identical results

#### Scenario: A composition recipe changes

- **WHEN** the weights in a composition recipe are changed
- **THEN** no model is re-executed and no raw score row is modified

### Requirement: Score rows are append-only and immutable

A stored score row SHALL never be updated in place or deleted. Recomputation SHALL insert new rows. Each row SHALL be identified by the tuple (`match_id`, `model_id`, `model_version`, `snapshot_hash`).

#### Scenario: A model is re-run after new odds arrive

- **WHEN** a model scores a match again from an updated snapshot
- **THEN** a new row is inserted with the new `snapshot_hash`, and the previous row remains queryable

#### Scenario: An update is attempted on an existing row

- **WHEN** a process attempts to modify or delete a persisted score row
- **THEN** the operation is rejected

### Requirement: Score rows are reproducible

Every score row SHALL record sufficient provenance to reproduce it: `model_id`, `model_version`, `snapshot_hash`, the raw score, the components map, and the timestamp at which it was computed. Given a row, it SHALL be possible to retrieve the exact snapshot that produced it.

#### Scenario: A past score is questioned

- **WHEN** someone asks why a specific match received a specific score on a specific date
- **THEN** the row identifies the model version and the exact input snapshot, and re-running that model version on that snapshot reproduces the score

### Requirement: Retired models retain their history

When a model is retired or superseded, its historical score rows SHALL be retained and remain queryable indefinitely. Retirement SHALL be expressed by removing the model from active scoring runs and from composition recipes, not by deleting its data.

#### Scenario: A model is superseded by a successor

- **WHEN** a model is retired in favor of a new one
- **THEN** the retired model produces no new rows, its existing rows remain readable, and historical comparisons between the retired and successor models remain possible

#### Scenario: A retired model is queried through the API

- **WHEN** a client requests scores for a retired model
- **THEN** historical scores are returned and the model is identified as retired

### Requirement: Serving reads resolve to the current score per model

For serving, the store SHALL expose the most recent score row per (`match_id`, `model_id`) based on `computed_at`, while retaining all superseded rows for audit and evaluation.

#### Scenario: Multiple score generations exist for one match

- **WHEN** a match has been scored three times by the same model as odds moved
- **THEN** a serving read returns only the most recent row, and an evaluation read can access all three

