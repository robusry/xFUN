# data-collection Specification

## Purpose
TBD - created by archiving change add-collector-tier. Update Purpose after archive.
## Requirements
### Requirement: Collection runs against a slate

A collection run SHALL operate on a slate — the complete set of matches to be scored in that run. The slate SHALL be determined before collection begins, SHALL be recorded with the run, and SHALL be supplied whole to every collector. The rule that selects matches into a slate SHALL be replaceable without changing the collector interface.

#### Scenario: A collector chooses its own fan-out

- **WHEN** a collection run begins with a slate of forty matches across five leagues
- **THEN** each collector receives the whole slate and decides how many external requests to make, and the platform does not impose one invocation per match

#### Scenario: The slate rule changes

- **WHEN** the rule selecting matches into a slate changes from a league allowlist to matches determined to be watchable in the US
- **THEN** collectors continue to operate unchanged, and runs made under the previous rule remain interpretable because each run records the slate it used

#### Scenario: A match enters the slate after collection has run

- **WHEN** a match is added to the slate after a collection run completed
- **THEN** that match carries no collected signals until a subsequent run, and models requiring those signals skip it with a recorded reason rather than scoring it from partial data

### Requirement: Collectors are the only tier permitted external access during a run

External access SHALL be confined to two tiers, distinguished by when they run relative to the slate: the **schedule source**, which runs before a slate exists and produces it, and **collectors**, which run after and enrich it. Both MAY perform network calls, read credentials, and depend on third-party libraries. Models SHALL remain pure as specified in `scoring-contract`, and SHALL NOT import a collector package or the schedule source. The API SHALL NOT import a collector package or the schedule source.

#### Scenario: A model imports a collector

- **WHEN** a model package imports a collector package or declares a network dependency
- **THEN** CI fails the dependency check for that package

#### Scenario: A collector declares an HTTP client

- **WHEN** a collector package declares a dependency on an HTTP client library
- **THEN** the dependency check passes, because collectors are the tier where external access is expected

#### Scenario: The schedule source declares an HTTP client

- **WHEN** the package containing the schedule source declares a dependency on an HTTP client library
- **THEN** the dependency check passes, because acquiring the slate requires external access that no collector can perform

#### Scenario: A model reaches the schedule source

- **WHEN** a model package imports the schedule source
- **THEN** CI fails the dependency check, for the same reason it fails on a collector import: scoring must not depend on the network

### Requirement: Collector output is keyed by an entity and joined onto matches

A collector SHALL declare the entity kind its output is keyed by: `match`, `team`, or `league`. The platform SHALL join collected values onto matches mechanically — match-keyed values by identity, team-keyed values onto the home and away sides of each match the team plays, and league-keyed values onto every match in that league. A collector SHALL NOT be required to attribute its output to matches itself.

#### Scenario: Team-keyed output reaches both sides of a match

- **WHEN** a collector keyed by `team` returns a value for a team playing a given match
- **THEN** that value is readable on the match under the home or away side according to which side the team is on

#### Scenario: A team-keyed value is available for only one side

- **WHEN** a collector keyed by `team` returns a value for the home team but not the away team
- **THEN** the home value is present, the away value is absent, and a model requiring the away value skips that match with a recorded reason

#### Scenario: League-keyed output covers every match in the league

- **WHEN** a collector keyed by `league` returns one value for a league in the slate
- **THEN** every match in that league carries the value, and matches in other leagues do not

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

### Requirement: Every signal path has exactly one producer

Collected signals SHALL be addressed as `signals.<namespace>.<leaf>`, where the namespace denotes a subject area rather than the identity of the producer. Exactly one registered producer SHALL claim any given leaf path. Which producer supplied a value SHALL be recorded in the run record and SHALL NOT be encoded in the path.

#### Scenario: Two producers claim the same path

- **WHEN** two collectors are registered that both declare they provide the same leaf path
- **THEN** registration fails with an error naming the contested path

#### Scenario: A signal changes producer

- **WHEN** the producer of a leaf path is replaced by a different producer of the same path
- **THEN** models declaring that path continue to resolve it unchanged, and the run record reflects the new producer

### Requirement: Collector failure is recorded distinctly from absence of data

A collector SHALL distinguish between having no data for an entity and having failed to determine whether data exists. The run record SHALL capture which occurred. A skip caused by collector failure SHALL be distinguishable from a skip caused by data that is legitimately absent.

#### Scenario: A source is unreachable

- **WHEN** a collector cannot reach its source for a run
- **THEN** the run record states the collector failed, models depending on it skip the affected matches, and those skips are attributable to failure rather than to absent data

#### Scenario: A source has nothing for a match

- **WHEN** a collector successfully queries its source and finds no data for a particular match
- **THEN** the run record states the collector succeeded, and the resulting skip is attributable to absent data rather than to failure

#### Scenario: One collector fails and others succeed

- **WHEN** one collector fails during a run and the remaining collectors succeed
- **THEN** the run completes, matches are scored by every model whose declared features are present, and the failure is recorded rather than aborting the run

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

### Requirement: A collector whose values are invented is never registered by a running system

A collector that produces values it did not obtain from a source SHALL NOT be
registered by the pipeline a person runs. Such collectors SHALL be registered only by
the project's own verification, where the invented values are the point.

The reason is that a corpus does not record whether a value was collected or
fabricated. Once both are written by the same run into the same store, nothing
downstream — no snapshot, no score, no run record — can tell a reader which it is
looking at, and the distinction cannot be recovered afterwards.

A model whose declared signal paths are provided only by such a collector SHALL
likewise not be registered by the running system. Registration fails a model declaring
a path nothing provides, and that failure is correct: the alternative is a model that
silently scores nothing on every run.

#### Scenario: A run writes to the corpus

- **WHEN** a pipeline run collects and persists collector output
- **THEN** every row it writes came from a source the collector read, and no row holds
  a fabricated value

#### Scenario: A model reads only fabricated signals

- **WHEN** the only collector providing a model's declared signal paths is one that
  invents its values
- **THEN** neither the collector nor the model is registered by the running system, and
  the model produces no scores rather than scores derived from invented input

#### Scenario: The entity joins are verified

- **WHEN** the project verifies that match-keyed, team-keyed, and league-keyed
  collector output joins onto matches correctly
- **THEN** collectors with invented values are used for that verification, including a
  team-keyed collector that returns a value for one side of a match only, so the
  partial-coverage path is exercised

#### Scenario: A contributor finds an unregistered collector package

- **WHEN** a contributor encounters a collector or model package that nothing in the
  running system registers
- **THEN** the package's README and `docs/STUBS.md` state that it exists to verify the
  platform and why removing it would lose coverage

