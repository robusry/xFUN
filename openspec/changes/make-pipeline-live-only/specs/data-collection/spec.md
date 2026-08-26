## ADDED Requirements

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
