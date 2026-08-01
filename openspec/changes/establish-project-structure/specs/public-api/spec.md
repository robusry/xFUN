## ADDED Requirements

### Requirement: The API is a read-only, versioned, contract-first surface

The public API SHALL be read-only with respect to scores and SHALL be defined by `contracts/openapi.yaml` as its source of truth. Client libraries SHALL be generated from that document rather than hand-written. The API SHALL be versioned in its path, and a released version's response shapes SHALL NOT change incompatibly.

#### Scenario: The OpenAPI document and implementation diverge

- **WHEN** the API implementation returns a response that does not conform to `contracts/openapi.yaml`
- **THEN** CI fails the contract conformance check

#### Scenario: A breaking response change is needed

- **WHEN** a change would alter an existing response shape incompatibly
- **THEN** it is introduced under a new API version, and the previous version's behavior is preserved

### Requirement: Scores are addressed by alias, with the calibration cohort as a request parameter

Score requests SHALL accept a score alias (defaulting to `default`) and a calibration cohort parameter. Every response containing scores SHALL state which alias and which cohort produced them.

#### Scenario: A client requests the day's matches

- **WHEN** a client requests matches for a date without specifying alias or cohort
- **THEN** documented defaults are applied and the response names the alias and cohort used

#### Scenario: A client requests a specific model's scores

- **WHEN** a client requests scores under an alias that resolves to a single model
- **THEN** that model's calibrated scores are returned in the same response shape as a composed score

### Requirement: Individual model scores are exposed alongside composites

The API SHALL expose each model's calibrated score for a match in addition to any composed score, enabling consumers to build their own blends. The API SHALL expose a registry endpoint listing available models — including retired ones, marked as such — and available compositions and aliases.

#### Scenario: A third party builds a custom blend

- **WHEN** a third-party consumer retrieves per-model scores for a set of matches
- **THEN** it has sufficient information to compute its own weighted composition without access to the score store

#### Scenario: A consumer discovers what is available

- **WHEN** a consumer queries the registry endpoint
- **THEN** it receives the current model identifiers and versions, retirement status, and the available composition aliases

### Requirement: Score responses are explainable

Every score returned SHALL be accompanied by the information needed to explain it: the contributing models and their weights for composed scores, each contributing model's calibrated score, and each model's components map.

#### Scenario: A user asks why a match ranks first

- **WHEN** a client requests the explanation for a match's score
- **THEN** the response identifies which models contributed, at what weights, with what calibrated scores, and the named factors within each model

### Requirement: The API does not execute models

The API SHALL NOT invoke scoring models during request handling and SHALL NOT depend on any model package. It SHALL read raw scores from the score store and apply calibration and composition, which are arithmetic over stored rows.

#### Scenario: All models are unavailable

- **WHEN** every model package is broken or absent from the API's runtime environment
- **THEN** the API continues to serve scores computed from previously stored rows

### Requirement: Availability of a match to US viewers is a distinct concern

Broadcast availability SHALL be modeled and served separately from scoring, with its own update cadence, and SHALL be able to express that availability is unknown. The system SHALL NOT assert an availability answer it cannot substantiate.

#### Scenario: Availability data is stale or missing for a match

- **WHEN** no reliable broadcast information exists for a match
- **THEN** the response reports availability as unknown rather than omitting the match or guessing a provider
