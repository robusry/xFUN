## MODIFIED Requirements

### Requirement: Availability of a match to US viewers is a distinct concern

Broadcast availability SHALL be modeled and served separately from scoring, with its own
update cadence, and SHALL be able to express that availability is unknown. The system SHALL
NOT assert an availability answer it cannot substantiate. Availability SHALL be served from
stored data rather than returned as a fixed value, and SHALL NOT appear in the match
snapshot a model receives, so that no model can score a match differently according to who
broadcasts it.

#### Scenario: Availability data is stale or missing for a match

- **WHEN** no reliable broadcast information exists for a match
- **THEN** the response reports availability as unknown rather than omitting the match or
  guessing a provider

#### Scenario: Providers are known for a match

- **WHEN** providers were determined for a match during acquisition
- **THEN** the response reports availability as known and lists those providers

#### Scenario: A model requests broadcast data as a feature

- **WHEN** a model declares a required feature path referring to broadcast availability
- **THEN** registration fails, because availability is not part of the match snapshot
