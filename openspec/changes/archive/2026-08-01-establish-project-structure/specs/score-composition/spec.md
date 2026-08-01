## ADDED Requirements

### Requirement: Compositions are declarative versioned configuration

A composition SHALL be expressed as declarative configuration data — not as code — naming a set of `model_id`s, their weights, a missing-model policy, and a minimum required model count. Each composition SHALL carry an identifier and a version. Changing a composition SHALL require only a configuration change, reviewable as a diff and revertable in a single commit.

#### Scenario: Weights are adjusted

- **WHEN** the team decides to change the relative weighting of models in a composition
- **THEN** the change is made by editing a configuration file, with no application code modified and no model re-executed

#### Scenario: A composition change is reverted

- **WHEN** a composition change produces undesirable rankings
- **THEN** reverting the configuration commit restores the previous behavior for all matches, including historical ones

#### Scenario: A composition references an unknown model

- **WHEN** a composition names a `model_id` that is not present in the model registry
- **THEN** validation fails at load time with an error naming the unknown model

### Requirement: Compositions declare an explicit missing-model policy

Every composition SHALL specify what happens when a referenced model has no score for a match. The policy SHALL be one of:

- `require-all` — produce no composed score unless every referenced model has a score
- `renormalize` — compose from available models, redistributing missing models' weight proportionally across those present
- `fallback` — substitute a named alternative model

A composition SHALL also specify `min_models`, the minimum number of contributing models below which no composed score is produced. The missing-model policy SHALL NOT be defaulted implicitly; it is a required field.

#### Scenario: A model has no score for a match

- **WHEN** a composed score is requested for a match where one referenced model produced no score, under the `renormalize` policy
- **THEN** the composed score is computed from the available models with weights renormalized to sum to one, and the response identifies which models contributed

#### Scenario: Too few models are available

- **WHEN** the number of contributing models for a match falls below `min_models`
- **THEN** no composed score is produced for that match and the reason is reported

#### Scenario: A composition omits its missing-model policy

- **WHEN** a composition configuration file has no missing-model policy
- **THEN** validation fails and the composition is not loaded

### Requirement: Composition operates on calibrated scores

Composition SHALL combine calibrated scores, using the calibration cohort supplied with the request. Composition SHALL NOT read raw scores directly.

#### Scenario: A composed score is requested with a specific cohort

- **WHEN** a client requests a composed score with a given calibration cohort
- **THEN** each contributing model's score is calibrated against that cohort before the weights are applied

### Requirement: Public score names are aliases that can be repointed

The system SHALL expose scores under stable public alias names. An alias SHALL resolve to either a specific composition version or a single model. Repointing an alias SHALL change what consumers receive without requiring any change on the consumer's part. The alias `default` SHALL always exist.

#### Scenario: The default blend is changed

- **WHEN** the `default` alias is repointed from one composition version to another
- **THEN** existing API consumers requesting `default` immediately receive scores from the new composition, with no client change and no contract change

#### Scenario: An alias points at a single model

- **WHEN** an alias is configured to resolve to one `model_id` rather than a composition
- **THEN** requests for that alias return that model's calibrated score through the same code path as a composed score

#### Scenario: A consumer requires stability

- **WHEN** a consumer needs deterministic behavior across time
- **THEN** it can address a pinned composition version directly instead of a repointable alias, and that pinned target is never repointed

### Requirement: Composition is cheap to recompute

Recomputing all composed scores from existing calibrated scores SHALL NOT require re-executing any model. The system SHALL support recomposing the full historical score set as a routine operation.

#### Scenario: A historical recompose is run

- **WHEN** a new composition version is introduced and applied across all historical matches
- **THEN** the operation reads existing raw scores, executes no models, and completes as a routine batch job
