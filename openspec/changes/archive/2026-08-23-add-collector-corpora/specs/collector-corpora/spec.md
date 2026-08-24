## ADDED Requirements

### Requirement: Collected signal values are persisted between runs

The platform SHALL persist the signal values a collector returns, keyed by
collector and by the entity the collector keyed them to. Persisted values SHALL
remain readable by later runs, including runs operating on a different slate.

Persisted values SHALL be append-only: a later collection SHALL insert new values
rather than modify or delete existing ones, and reads SHALL resolve the most
recently collected value for a given collector and entity.

#### Scenario: A value outlives the run that produced it

- **WHEN** a collector returns values for a set of entities in one run, and a later run is performed
- **THEN** the later run can read those values without invoking the collector

#### Scenario: Re-collection supersedes without erasing

- **WHEN** a collector is invoked again and returns a different value for an entity it has previously covered
- **THEN** the new value resolves as current, and the previous value remains queryable

#### Scenario: An entity the collector has never covered

- **WHEN** a persisted corpus is read for an entity no collection has ever returned a value for
- **THEN** the read reports the entity as absent from the corpus, distinct from reporting a stored empty value

### Requirement: A collector is not invoked while its persisted output is still usable

The platform SHALL decide whether to invoke a required collector by consulting its
persisted output. A collector SHALL NOT be invoked when both of the following hold:

- its persisted output is younger than the collector's declared
  `refresh_after_seconds`, measured against the run's start time; and
- its persisted output covers every entity the slate asks about.

When either condition fails, the collector SHALL be invoked for the whole slate.

A collector declaring no `refresh_after_seconds` SHALL be invoked on every run.

#### Scenario: Output is fresh and complete

- **WHEN** a required collector's persisted output covers every entity on the slate and is younger than its declared refresh window
- **THEN** the collector is not invoked, and models consuming its signals score from the persisted values

#### Scenario: Output is fresh but does not cover the whole slate

- **WHEN** a required collector's persisted output is younger than its refresh window but the slate contains an entity the corpus has no value for
- **THEN** the collector is invoked, rather than the uncovered entity being treated as having no data

#### Scenario: Output has aged past its declared window

- **WHEN** a required collector's persisted output is older than its declared refresh window
- **THEN** the collector is invoked

#### Scenario: A collector declares no refresh window

- **WHEN** a required collector declares no `refresh_after_seconds`
- **THEN** the collector is invoked on every run regardless of what is persisted

### Requirement: Reuse of persisted output is recorded distinctly

The run record SHALL distinguish a collector that was not invoked because its
persisted output was still usable from a collector that was not invoked because no
active model declared anything it provides. The record SHALL state how many
entities were served from persisted output.

#### Scenario: Telling reuse apart from having no consumer

- **WHEN** an operator reads the run record for a run in which one collector was skipped as still-fresh and another was skipped as having no consumer
- **THEN** the two are recorded as different outcomes, and the still-fresh one reports the number of entities served from persisted output

#### Scenario: Explaining a score produced without a network call

- **WHEN** an operator asks how a match was scored in a run where the source was never contacted
- **THEN** the run record identifies which collector's persisted output was reused, and when that output was originally collected

### Requirement: Collection failure does not overwrite or consume persisted output

When a collector fails, the platform SHALL NOT persist any value for that run and
SHALL NOT substitute previously persisted output in its place. The failure SHALL be
recorded as it is for a collector with no persisted output, and models depending on
the collector SHALL skip the affected matches with the skip attributable to
failure.

Previously persisted values SHALL remain intact and available to later runs.

#### Scenario: A source is unreachable and a corpus exists

- **WHEN** a collector that has previously persisted values fails to reach its source
- **THEN** the run records the failure, no value is persisted for the run, models depending on it skip the affected matches, and the previously persisted values are unchanged

#### Scenario: A previously failing source recovers

- **WHEN** a collector that failed in one run succeeds in a later run
- **THEN** the values from the successful run resolve as current

### Requirement: Collection can be forced regardless of persisted output

The platform SHALL provide an explicit way to invoke every required collector
regardless of the freshness or coverage of persisted output. Forcing collection
SHALL NOT delete persisted values.

#### Scenario: An operator knows the source has changed

- **WHEN** collection is forced for a run
- **THEN** every required collector is invoked, its results are persisted, and previously persisted values remain queryable
