## MODIFIED Requirements

### Requirement: Serving reads resolve to the current score per model

For serving, the store SHALL expose the most recent score row per (`match_id`, `model_id`) based on `computed_at`, while retaining all superseded rows for audit and evaluation.

`computed_at` SHALL distinguish score generations that are expected to differ. A scoring run that takes its timestamps from the time it occurs SHALL record that time, so that "most recent" is decided by when the score was computed rather than by insertion order. Where a path is required to be reproducible, repeated runs over unchanged inputs MAY share a `computed_at`, because they produce identical rows and there is no generation to distinguish.

#### Scenario: Multiple score generations exist for one match

- **WHEN** a match has been scored three times by the same model as odds moved
- **THEN** a serving read returns only the most recent row, and an evaluation read can access all three

#### Scenario: A match is rescored after new data arrives

- **WHEN** a model scores a match, new signals are collected, and the same model version scores it again
- **THEN** the later row carries a later `computed_at`, and a serving read resolves to it rather than to whichever row happened to be written last

#### Scenario: A reproducible run is repeated

- **WHEN** a reproducible path is run twice over unchanged inputs
- **THEN** the second run produces rows identical to the first, including `computed_at`, and no new generation is created
