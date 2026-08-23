# recent-goal-form Specification

## Purpose
TBD - created by archiving change add-recent-goals-model. Update Purpose after archive.
## Requirements
### Requirement: Recent goal form is the goals a team scored in its last five completed matches

The system SHALL provide, per team, the sum of goals that team scored in its five most recent
completed matches. Matches SHALL be counted from every competition the source reports, not
only the competition the upcoming match belongs to, and SHALL be counted across season
boundaries where five matches require it. The five SHALL be the five most recent by kickoff
time, regardless of which competition each belongs to.

#### Scenario: Five league matches

- **WHEN** a team's five most recent completed matches are league matches in which it scored
  2, 0, 1, 3, and 1 goals
- **THEN** its recent goal form is 7

#### Scenario: A cup match interleaves with league matches

- **WHEN** a team's five most recent completed matches include a domestic cup tie played
  between two league matches
- **THEN** the cup tie is counted, and the sixth-most-recent match is not

#### Scenario: The five span two seasons

- **WHEN** a team has played two completed matches in the current season and its three
  previous completed matches fall in the previous season
- **THEN** all five are counted and the value crosses the season boundary without comment

#### Scenario: Goals scored, not goals in the match

- **WHEN** a team's five most recent completed matches ended 3-1, 0-0, 1-2, 2-2, and 0-4,
  with the team playing at home in the first and away in the last
- **THEN** only the goals that team scored are summed — 3, 0, 1, 2, and 4 — and its
  opponents' goals are not

### Requirement: Only completed matches count

A match SHALL be counted only when the source reports it as having finished. A match that was
postponed, cancelled, abandoned, or is in progress SHALL NOT be counted, and SHALL NOT be
counted merely because a score is present for it. A match whose reported state the system does
not recognise SHALL NOT be counted.

#### Scenario: A postponed match carries a score

- **WHEN** a postponed match appears in the scanned span carrying a 0-0 score
- **THEN** it is not counted, and the next older completed match is counted in its place

#### Scenario: A match is in progress during collection

- **WHEN** a match is being played at the moment of collection and carries a running score
- **THEN** it is not counted, and the team's value is computed from completed matches only

#### Scenario: An unrecognised state

- **WHEN** the source reports a match in a state the system does not recognise
- **THEN** the match is not counted, so that an unrecognised state produces a team that is
  short of matches rather than a total that includes an unfinished one

### Requirement: The search for completed matches is bounded

The search backwards for a team's five completed matches SHALL stop at a fixed bound of 120
days before the run. The search SHALL stop earlier as soon as every team on the slate has five
completed matches. The bound SHALL NOT be configurable per run.

#### Scenario: Every team is satisfied early

- **WHEN** every team on the slate has five completed matches within 40 days of the run
- **THEN** the search stops there and no older dates are read

#### Scenario: A team's fifth match falls outside the bound

- **WHEN** a team has four completed matches within 120 days of the run and its fifth is older
- **THEN** the search stops at the bound and that team is treated as having fewer than five

### Requirement: Fewer than five completed matches yields no value

A team with fewer than five completed matches within the bound SHALL carry no recent goal form
value at all. A partial sum SHALL NOT be provided, and no substitute, average, or scaled value
SHALL be provided in its place.

#### Scenario: A promoted team early in a season

- **WHEN** a team has three completed matches within the bound
- **THEN** no value is provided for that team, and the run records that the collector
  succeeded and had no data for it rather than that it failed

#### Scenario: A match with one side short

- **WHEN** the home team has five completed matches and the away team has two
- **THEN** the home value is present, the away value is absent, and the match is skipped by
  any model requiring both with the missing path named in the recorded reason

### Requirement: Failure to read the source is not absence of matches

When the source cannot be read or cannot be parsed during the search, the collector SHALL
report failure for the whole run rather than returning the values gathered so far. Partial
results SHALL NOT be reported as though the teams they cover were the only teams with data.

#### Scenario: The source becomes unreachable partway through the search

- **WHEN** the source answers for 30 dates and then cannot be reached
- **THEN** the collector reports failure, no values are provided for any team, and skips
  caused by it are attributable to failure rather than to teams not having played

#### Scenario: The source changes shape

- **WHEN** a page is fetched successfully but no longer has the structure the parser reads
- **THEN** the collector reports failure naming the parse problem, rather than reporting that
  no team has played

### Requirement: A match is scored by the two sides' recent goal form added together

A model SHALL score a match as the home team's recent goal form plus the away team's. The
score SHALL be reported on that native scale without normalisation, and SHALL expose each
side's contribution. A match SHALL be scored only when both sides carry a value.

#### Scenario: Both sides carry a value

- **WHEN** the home team's recent goal form is 8 and the away team's is 5
- **THEN** the raw score is 13, and the components report 8 for the home side and 5 for the
  away side

#### Scenario: One side carries no value

- **WHEN** the away team has no recent goal form value
- **THEN** the match is not scored, and the recorded reason names the missing away path

#### Scenario: The score is not normalised

- **WHEN** a match is scored
- **THEN** the raw score is the goal total itself, not a probability, a percentile, or a value
  rescaled against other matches, and ranking against other matches happens at read time

