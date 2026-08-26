# schedule-acquisition Specification

## Purpose
How the set of upcoming matches and their US broadcast providers is acquired, before
a slate exists. Covers the source, the window, provider resolution and its precedence,
the `us-watchable` selection rule, and what is recorded when the source cannot be read.
## Requirements
### Requirement: The set of upcoming matches is acquired before a slate exists

The system SHALL acquire the set of upcoming matches, and the US broadcast providers for
each, in a step that runs before slate assembly. This step SHALL write canonical match
entities, from which the slate is then assembled. It SHALL NOT be expressed as a collector,
because a collector receives a slate as input and therefore cannot produce one.

#### Scenario: Acquisition precedes collection in a run

- **WHEN** a run acquires the schedule and then assembles a slate
- **THEN** canonical match entities exist before any collector is invoked, and collectors
  receive the assembled slate

#### Scenario: Acquisition writes matches that were not previously known

- **WHEN** the source returns a match with no corresponding canonical entity
- **THEN** the match, its teams, and its competition are written as canonical entities
  before the slate is assembled

#### Scenario: Re-running acquisition does not duplicate matches

- **WHEN** acquisition runs twice over an overlapping window
- **THEN** entity writes converge on natural identifiers and the second run leaves the store
  in the same state as the first

### Requirement: The slate admits only matches watchable in the US within a bounded window

The slate SHALL be selected by the rule `us-watchable`: a match is admitted only when its
kickoff falls within 10 days of the time of the run AND at least one US broadcast provider
is known for it. The window SHALL be measured from the time of the run rather than from a
fixed date. The selection rule and window SHALL be recorded on the slate.

#### Scenario: A match with a known provider inside the window

- **WHEN** a match kicks off in 3 days and a US provider is known for it
- **THEN** it is admitted to the slate, and the slate records `rule: us-watchable` with the
  window bounds

#### Scenario: A match with no known provider

- **WHEN** a match kicks off in 3 days and no US provider can be determined for it
- **THEN** it is not admitted to the slate

#### Scenario: A match beyond the window

- **WHEN** a match kicks off in 14 days and a US provider is known for it
- **THEN** it is not admitted to the slate, because it falls outside the 10-day window

#### Scenario: No watchable match exists in the window

- **WHEN** the source is reached successfully and no match in the window has a known
  provider
- **THEN** the slate is empty, and the run records that the source succeeded

### Requirement: Broadcast providers resolve from per-match data before league-level rights

Provider resolution SHALL consult per-match data from the schedule source first. Where the
source names no provider for a match, resolution SHALL fall back to a configured
`league -> US providers` rights table. Where neither answers, availability SHALL be
`unknown`. The rights table SHALL record, per entry, the date on which it was last
verified.

A competition absent from the rights table SHALL NOT be excluded from the slate on that
basis alone. Absence from the table is not a statement that a competition is unwatchable
in the US; it is a statement that no single league-wide line about it is true. Where the
source answers per match for such a competition, that answer SHALL resolve availability
and the match SHALL be admitted on the same terms as any other.

#### Scenario: The source names providers for a match

- **WHEN** the source returns one or more US providers for a match whose league also appears
  in the rights table
- **THEN** the providers from the source are used, because league-level rights cannot express
  a split-rights competition, and the match is admitted to the slate

#### Scenario: A split-rights competition the rights table deliberately omits

- **WHEN** the source returns US providers for a match in a competition whose rights are held
  per club, and which therefore has no rights-table entry
- **THEN** availability is `known` with the providers the source named, and the match is
  admitted to the slate — the absent table entry neither supplies a provider nor withholds one

#### Scenario: The source names no provider but the league has constant rights

- **WHEN** the source returns no provider for a match, and the match's competition appears in
  the rights table
- **THEN** the providers from the rights table are used, and availability is `known`

#### Scenario: Neither source nor table answers

- **WHEN** the source returns no provider and the competition is absent from the rights table
- **THEN** availability for that match is `unknown` with an empty provider list, and the
  match is not admitted to the slate

#### Scenario: A rights table entry lacks a verification date

- **WHEN** the rights table contains an entry with no verification date
- **THEN** loading the table fails, rather than serving a provider of unknown vintage

### Requirement: Schedule source failure is recorded distinctly from an empty window

An unreachable, unauthorised, or unparseable schedule source SHALL be recorded as a failure
with a reason. The system SHALL NOT represent source failure as a window containing no
watchable match, because both produce an empty slate and only the record distinguishes
them.

#### Scenario: The source cannot be reached

- **WHEN** the schedule source returns an error status or the request times out
- **THEN** the run records a source failure with a reason, and does not record that the
  window contained no matches

#### Scenario: The source response cannot be parsed

- **WHEN** the source responds successfully but its payload no longer contains the expected
  structure
- **THEN** the run records a source failure naming the parse problem, rather than treating
  the absent structure as an absence of matches

#### Scenario: A prior run's matches are still in the store when acquisition fails

- **WHEN** acquisition fails and canonical matches from an earlier successful run remain
- **THEN** the failure is recorded, and the run does not silently proceed as though the
  stale matches were freshly acquired

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

