## MODIFIED Requirements

### Requirement: A collection run is recorded

Each collection run SHALL record the slate it operated on, which collectors were invoked, and the outcome of each. Collectors that were not invoked SHALL be recorded together with which reason applied — that no active model declared anything they provide, or that their persisted output was still usable. The record SHALL be queryable after the run.

A run identifier SHALL distinguish one run from another wherever runs are expected to differ. Where a path is required to be reproducible, repeated runs MAY share an identifier, since they are the same run repeated rather than two runs; where a path takes its timestamps from the time it occurs, each run SHALL be separately identified and SHALL NOT overwrite the record of an earlier one.

#### Scenario: Explaining why a match went unscored

- **WHEN** an operator asks why a given match carries no score from a given model
- **THEN** the run record identifies whether the required collector was invoked, whether it succeeded, and whether it returned data for that match

#### Scenario: Explaining why a source was not contacted

- **WHEN** an operator asks why a collector made no request to its source during a run
- **THEN** the run record distinguishes a collector no active model needed from one whose persisted output was still usable

#### Scenario: Two live runs on the same day

- **WHEN** live collection is performed twice with different outcomes
- **THEN** both runs are recorded and separately identifiable, and the earlier record is not replaced by the later one

#### Scenario: Asking what happened on a past run

- **WHEN** an operator asks which collectors succeeded during a particular earlier live run
- **THEN** that run's record is retrievable and distinguishable from every other run's
