## MODIFIED Requirements

### Requirement: A collector runs once per slate, and only when a model needs it

The platform SHALL determine which collectors to run from the union of the features declared by the active models. A collector whose output no active model declares SHALL NOT be invoked.

A collector whose output an active model does declare SHALL be invoked exactly once per collection run, unless its persisted output is still usable for that slate, in which case it SHALL NOT be invoked and its persisted output SHALL be used instead. Usability is defined by the `collector-corpora` capability.

Being required by an active model is therefore necessary but no longer sufficient for invocation.

#### Scenario: Several models consume one source

- **WHEN** three active models each declare a feature produced by the same collector
- **THEN** that collector is invoked once for the run and its output is available to all three

#### Scenario: A collector has no consumers

- **WHEN** a registered collector produces only features that no active model declares
- **THEN** the collector is not invoked and the run succeeds

#### Scenario: A model declares a feature nothing produces

- **WHEN** a model declares a feature path that is well-formed but that no registered collector provides
- **THEN** registration fails with an error naming the unprovided path, rather than the model silently skipping every match

#### Scenario: A required collector's persisted output is still usable

- **WHEN** an active model declares a feature produced by a collector whose persisted output is fresh and covers the whole slate
- **THEN** the collector is not invoked, and the model scores from the persisted values

### Requirement: A collection run is recorded

Each collection run SHALL record the slate it operated on, which collectors were invoked, and the outcome of each. Collectors that were not invoked SHALL be recorded together with which reason applied — that no active model declared anything they provide, or that their persisted output was still usable. The record SHALL be queryable after the run.

#### Scenario: Explaining why a match went unscored

- **WHEN** an operator asks why a given match carries no score from a given model
- **THEN** the run record identifies whether the required collector was invoked, whether it succeeded, and whether it returned data for that match

#### Scenario: Explaining why a source was not contacted

- **WHEN** an operator asks why a collector made no request to its source during a run
- **THEN** the run record distinguishes a collector no active model needed from one whose persisted output was still usable
