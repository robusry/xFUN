## MODIFIED Requirements

### Requirement: The system runs without network access or credentials

The fixture-backed path SHALL remain the default, and SHALL require no network access and
no credentials. Live acquisition SHALL be selected explicitly.

The two paths SHALL differ in where they take their notion of the present. Live
acquisition SHALL derive the run's timestamps from the time the run occurs. The
fixture-backed path SHALL derive them from a fixed anchor, so that repeated runs
over unchanged fixtures produce identical output, including identical stored
timestamps and identical run identifiers.

The fixed anchor SHALL NOT be treated as a placeholder awaiting replacement by the
clock. The captured pages the fixture path reads exist only for a bounded range of
dates, and a scan anchored to the present would run off the end of them and report
an absence of data that is an artefact of the anchor rather than a fact about any
source.

#### Scenario: A fresh clone runs the demo

- **WHEN** a collaborator clones the repository and runs the demo with nothing configured
- **THEN** the pipeline completes against fixture data without contacting any external
  service

#### Scenario: Live acquisition is requested explicitly

- **WHEN** the pipeline is invoked with live acquisition selected
- **THEN** the schedule source is contacted, and the run records which source produced the
  slate

#### Scenario: The offline demo is run twice

- **WHEN** the fixture-backed path is run twice over unchanged fixtures
- **THEN** both runs produce identical output, and the timestamps and run identifiers stored by the second are indistinguishable from the first

#### Scenario: A live run records when it happened

- **WHEN** live acquisition is performed
- **THEN** the timestamps stored against that run reflect when the run occurred, not a fixed value shared with every other run
