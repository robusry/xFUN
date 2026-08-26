## REMOVED Requirements

### Requirement: The system runs without network access or credentials

**Reason**: The fixture-backed path is no longer something a person can select. It
described a user-facing mode — "the default", "selected explicitly" — and the system
now has exactly one mode, which acquires from the schedule source. The reproducibility
property the requirement protected is not being dropped; it is restated below as a
property of the offline end-to-end check rather than of a runnable path.

**Migration**: Anyone who ran the pipeline with no arguments to see it work must now
provide network access to the schedule source. There is no flag, environment
variable, or configuration that restores fixture-backed acquisition. The equivalent
offline run exists only as the end-to-end test, invoked through `pytest`.

## ADDED Requirements

### Requirement: A pipeline run acquires from the schedule source

A pipeline run SHALL acquire the set of upcoming matches from the schedule source.
Acquisition SHALL NOT be conditional on a flag, an environment variable, or the
presence of previously stored matches: there is one path, and it contacts the source.

The run's notion of the present SHALL be derived from the time the run occurs, sampled
once and threaded through the run, so that timestamps, the run identifier, and every
collector's freshness comparison describe the same instant.

Where acquisition fails, the run SHALL record the failure and stop, rather than
proceeding into an empty slate or substituting matches from an earlier run. The system
SHALL NOT provide a fixture-backed or cached alternative to acquisition — a run that
could not reach the source produced nothing, and says so.

#### Scenario: A run is invoked with no arguments

- **WHEN** the pipeline is invoked with no arguments
- **THEN** the schedule source is contacted, and the run records which source produced
  the slate

#### Scenario: A run records when it happened

- **WHEN** a pipeline run completes
- **THEN** the timestamps stored against that run reflect when the run occurred, and
  the run identifier is distinct from every other run's

#### Scenario: The schedule source cannot be reached

- **WHEN** acquisition fails and no matches are acquired
- **THEN** the run records the failure, reports it as a source failure rather than as a
  window with nothing worth watching, and exits without scoring

#### Scenario: A caller looks for a way to run without the network

- **WHEN** a caller inspects the pipeline's arguments and configuration for an offline
  or fixture-backed mode
- **THEN** none is offered, and the documentation states that network access to the
  schedule source is required to run the system at all

### Requirement: The end-to-end behaviour of the pipeline is verifiable without network access

The pipeline's behaviour from acquisition through stored scores SHALL be verifiable
with no external access, by supplying the run with its schedule input, its collector
page source, and its notion of the present, rather than by selecting a mode.

Everything downstream of those supplied inputs SHALL be the same code that a live run
executes. A verification path that reimplements or bypasses the run is not sufficient,
because the property being checked is that the pipeline works, not that a parallel
implementation of it does.

When supplied with an unchanging schedule input, an unchanging page source, and a
fixed notion of the present, repeated runs SHALL store identical scores, identical
timestamps, and identical run identifiers.

Reproducibility constrains what a run STORES, not what it DOES. A repeated run may
legitimately reach the same stored state by a different route — reusing persisted
collector output rather than collecting it again — and the run record SHALL reflect
the route actually taken. What must not vary is the data the run leaves behind.

The fixed notion of the present SHALL NOT be treated as a placeholder awaiting
replacement by the clock. The captured pages this verification reads exist only for a
bounded range of dates, and a scan anchored to the present would run off the end of
them and report an absence of data that is an artefact of the anchor rather than a
fact about any source.

#### Scenario: Continuous integration verifies the pipeline

- **WHEN** continuous integration runs, with no access to any external service
- **THEN** the pipeline is exercised from schedule input through stored scores, and a
  regression in any tier between them fails the build

#### Scenario: The offline verification is run twice

- **WHEN** the pipeline is verified twice over unchanged inputs
- **THEN** the scores, timestamps, and run identifier stored by the second run are
  indistinguishable from the first

#### Scenario: A repeated verification reuses rather than re-collects

- **WHEN** the pipeline is verified a second time and a collector's persisted output is
  still usable
- **THEN** the stored scores and timestamps are unchanged, and the run record states
  that the collector's output was reused rather than that it was collected again

#### Scenario: The offline verification reaches a steady state

- **WHEN** the pipeline is verified a third time over unchanged inputs
- **THEN** everything it stores, including the run record, is identical to the second
  run

### Requirement: The path that contacts the schedule source is exercised by continuous integration

The code that performs the fetch — client construction, request headers, timeouts,
redirect handling, and the translation of transport and status failures into a
recorded source failure — SHALL be exercised by continuous integration against a
recorded response, without contacting any external service.

This verification SHALL be understood to establish that the fetching code works
against bytes shaped like the source's, and SHALL NOT be represented as establishing
that the source is reachable or still publishes that shape. Detecting a change at the
source is explicitly not within its reach.

#### Scenario: The fetching code is exercised

- **WHEN** continuous integration runs
- **THEN** the real client is constructed and driven against a recorded response, and a
  regression in client configuration or error translation fails the build

#### Scenario: The source returns a transport failure

- **WHEN** the recorded response is replaced by a transport failure
- **THEN** the failure is translated into a recorded source failure naming the problem,
  rather than into an empty set of matches

#### Scenario: The source changes shape in production

- **WHEN** the schedule source alters its payload structure after this verification was
  recorded
- **THEN** the verification continues to pass, and the change is detected only when a
  run contacts the source and its parser fails loudly
