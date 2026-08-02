## ADDED Requirements

### Requirement: Raw scores are calibrated onto a common comparable scale

The platform SHALL convert each model's `raw_score` into a `calibrated_score` on a common 0–100 scale by computing the model's percentile rank within a cohort of matches. Calibration SHALL be performed per model, so that each model's scores are ranked only against other scores from the same model and version. Models SHALL NOT perform their own calibration.

#### Scenario: Two models with different native scales are compared

- **WHEN** one model emits probabilities in [0,1] and another emits unbounded z-scores for the same cohort
- **THEN** both are calibrated to 0–100 percentile ranks and become directly comparable

#### Scenario: Uncalibrated scores are combined

- **WHEN** a composition is requested
- **THEN** it operates on calibrated scores, never on raw scores

### Requirement: The calibration cohort is selected by the caller at request time

The calibration cohort SHALL be a request-time parameter, not a stored property of a score. The API and client applications SHALL be able to request a different cohort per request. The system SHALL support at minimum these cohort definitions:

- `window` — all matches in the requested date range
- `league` — all matches within each match's own league, over a defined trailing period
- `season` — all matches within each match's own league for the current season
- `global` — all matches across all covered leagues over a defined trailing period

#### Scenario: The same match is calibrated two ways in two requests

- **WHEN** a client requests a match's score with cohort `window` and then with cohort `season`
- **THEN** the returned calibrated scores may differ, both are valid, and the response states which cohort produced each

#### Scenario: A quiet weekend is scored

- **WHEN** the best available match on a weekend is mediocre by season standards and the cohort is `window`
- **THEN** it calibrates near the top of the 0–100 scale because the cohort contains only that weekend's matches

#### Scenario: No cohort is specified

- **WHEN** a request omits the cohort parameter
- **THEN** a documented default cohort is applied and named in the response

### Requirement: Calibration is deterministic and reproducible

For a fixed set of raw scores and a fixed cohort definition, calibration SHALL produce identical results on every evaluation. The cohort used SHALL be reported alongside any calibrated score.

#### Scenario: A calibrated score is returned without context

- **WHEN** any calibrated score is returned by the API
- **THEN** the response identifies the cohort definition and the cohort's match count

### Requirement: Insufficient cohorts are reported, not silently produced

The system SHALL define a minimum cohort size below which percentile calibration is not meaningful. When a cohort falls below that size, the system SHALL either fall back to a documented wider cohort or return the score marked as low-confidence, and SHALL indicate which occurred.

#### Scenario: A cohort contains too few matches

- **WHEN** a requested cohort resolves to fewer matches than the configured minimum
- **THEN** the response indicates that the cohort was insufficient and states the fallback or low-confidence status applied

### Requirement: Calibration results may be cached but not treated as truth

Calibrated scores MAY be materialized for performance, keyed by model identity, cohort definition, and the underlying raw-score generation. Any cache SHALL be invalidated when new raw scores enter the cohort.

#### Scenario: New scores enter a cached cohort

- **WHEN** a new raw score row is inserted for a match inside a previously cached cohort
- **THEN** the cached calibration for that cohort is invalidated and recomputed on next read
