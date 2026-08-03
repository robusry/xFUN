## ADDED Requirements

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

#### Scenario: The source names providers for a match

- **WHEN** the source returns one or more US providers for a match whose league also appears
  in the rights table
- **THEN** the providers from the source are used, because league-level rights cannot express
  a split-rights competition

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

### Requirement: The system runs without network access or credentials

The fixture-backed path SHALL remain the default, and SHALL require no network access and
no credentials. Live acquisition SHALL be selected explicitly.

#### Scenario: A fresh clone runs the demo

- **WHEN** a collaborator clones the repository and runs the demo with nothing configured
- **THEN** the pipeline completes against fixture data without contacting any external
  service

#### Scenario: Live acquisition is requested explicitly

- **WHEN** the pipeline is invoked with live acquisition selected
- **THEN** the schedule source is contacted, and the run records which source produced the
  slate
