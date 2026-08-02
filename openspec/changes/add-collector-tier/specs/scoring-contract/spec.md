## MODIFIED Requirements

### Requirement: Models declare their required features

Each model SHALL declare the set of snapshot features it requires. The scoring runtime SHALL assemble only the declared features for that model, and SHALL skip a match for a model whose required features are unavailable for that match, recording the skip and its reason rather than emitting a score.

A declaration SHALL be validated at registration against both the snapshot schema and the set of paths some registered producer provides. A path that is well-formed but that nothing produces SHALL fail registration, because a model that can never be satisfied should fail loudly rather than skip every match in silence.

The declaration mechanism SHALL be open to further kinds of declaration beyond dotted feature paths. Dotted feature paths are the only kind defined by this specification; a kind whose coverage is determined by the model rather than by the platform is anticipated and SHALL NOT require this requirement to be replaced.

#### Scenario: Required data is missing for some matches

- **WHEN** a model requires shot-level data and that data is unavailable for a given league
- **THEN** the model produces no rows for matches in that league, other models continue to produce rows for those matches, and the pipeline run succeeds

#### Scenario: A model declares an unknown feature

- **WHEN** a model declares a required feature that is not defined in `contracts/schemas/match-snapshot.json`
- **THEN** model registration fails with an error naming the unknown feature

#### Scenario: A model declares a feature that no producer provides

- **WHEN** a model declares a feature path that the snapshot schema permits but that no registered collector provides
- **THEN** model registration fails with an error naming the unprovided path

#### Scenario: A model declares a collected signal

- **WHEN** a model declares a feature path under `signals.` that a registered collector provides
- **THEN** registration succeeds, and the model is invoked for matches where that signal is present and skipped with a recorded reason where it is not

#### Scenario: Two models declare the same collected signal

- **WHEN** two models declare the same collected feature path
- **THEN** both are invoked with the same value for a given match, and neither model's registration or execution depends on the other
