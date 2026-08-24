## MODIFIED Requirements

### Requirement: The system runs without network access or credentials

The fixture-backed path SHALL remain the default, and SHALL require no network access and
no credentials. Live acquisition SHALL be selected explicitly.

The two paths SHALL differ in where they take their notion of the present. Live
acquisition SHALL derive the run's timestamps from the time the run occurs. The
fixture-backed path SHALL derive them from a fixed anchor, so that repeated runs
over unchanged fixtures store identical timestamps, identical run identifiers, and
identical scores.

Reproducibility constrains what a run STORES, not what it DOES. A repeated run may
legitimately reach the same stored state by a different route — reusing persisted
collector output rather than collecting it again — and the run record SHALL reflect
the route actually taken. What must not vary is the data the run leaves behind.

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
- **THEN** the scores, timestamps, and run identifier stored by the second run are indistinguishable from the first

#### Scenario: A repeated offline run reuses rather than re-collects

- **WHEN** the fixture-backed path is run a second time and a collector's persisted output is still usable
- **THEN** the stored scores and timestamps are unchanged, and the run record states that the collector's output was reused rather than that it was collected again

#### Scenario: The offline demo reaches a steady state

- **WHEN** the fixture-backed path is run a third time over unchanged fixtures
- **THEN** everything it stores, including the run record, is identical to the second run

#### Scenario: A live run records when it happened

- **WHEN** live acquisition is performed
- **THEN** the timestamps stored against that run reflect when the run occurred, not a fixed value shared with every other run
