## ADDED Requirements

### Requirement: The served date window is a response property, not an assumption

The match-list endpoint SHALL accept an optional date range. Where a bound is
omitted, the endpoint SHALL NOT substitute a window of its own choosing; it SHALL
answer over the range the store holds on that side.

Every match-list response SHALL state the date window it actually served,
regardless of whether the caller supplied one. A caller that supplied no range
SHALL be able to determine from the response alone what range it received.

This is the same obligation the API already carries for the calibration cohort and
the score alias: a result whose basis the caller did not choose is uninterpretable
unless the response names that basis.

#### Scenario: A client asks for matches without a date range

- **WHEN** a client requests the match list with neither bound supplied
- **THEN** the response contains the matches the store holds, and states the date window those matches span

#### Scenario: A client supplies a date range

- **WHEN** a client requests the match list with both bounds supplied
- **THEN** only matches within that range are returned, and the response states that window

#### Scenario: A client supplies one bound

- **WHEN** a client supplies only a lower bound
- **THEN** matches from that bound onward are returned, unbounded above, and the response states the window served

#### Scenario: The store holds no matches

- **WHEN** a client requests the match list with no date range and the store holds no matches
- **THEN** the response is an empty match list that states no window was served, rather than an error or an invented range

## MODIFIED Requirements

### Requirement: Scores are addressed by alias, with the calibration cohort as a request parameter

Score requests SHALL accept a score alias (defaulting to `default`) and a calibration cohort parameter. Every response containing scores SHALL state which alias and which cohort produced them, and — for responses covering a set of matches — which date window they were drawn from.

#### Scenario: A client requests the day's matches

- **WHEN** a client requests matches for a date without specifying alias or cohort
- **THEN** documented defaults are applied and the response names the alias and cohort used

#### Scenario: A client requests a specific model's scores

- **WHEN** a client requests scores under an alias that resolves to a single model
- **THEN** that model's calibrated scores are returned in the same response shape as a composed score

#### Scenario: A client requests matches without specifying anything

- **WHEN** a client requests the match list supplying neither dates, nor alias, nor cohort
- **THEN** the response names the alias, the cohort, and the date window it served, so that every basis of the result is recoverable from the result
