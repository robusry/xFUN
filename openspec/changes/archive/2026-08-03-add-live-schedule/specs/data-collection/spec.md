## MODIFIED Requirements

### Requirement: Collectors are the only tier permitted external access during a run

External access SHALL be confined to two tiers, distinguished by when they run relative to
the slate: the **schedule source**, which runs before a slate exists and produces it, and
**collectors**, which run after and enrich it. Both MAY perform network calls, read
credentials, and depend on third-party libraries. Models SHALL remain pure as specified in
`scoring-contract`, and SHALL NOT import a collector package or the schedule source. The
API SHALL NOT import a collector package or the schedule source.

#### Scenario: A model imports a collector

- **WHEN** a model package imports a collector package or declares a network dependency
- **THEN** CI fails the dependency check for that package

#### Scenario: A collector declares an HTTP client

- **WHEN** a collector package declares a dependency on an HTTP client library
- **THEN** the dependency check passes, because collectors are the tier where external access
  is expected

#### Scenario: The schedule source declares an HTTP client

- **WHEN** the package containing the schedule source declares a dependency on an HTTP client
  library
- **THEN** the dependency check passes, because acquiring the slate requires external access
  that no collector can perform

#### Scenario: A model reaches the schedule source

- **WHEN** a model package imports the schedule source
- **THEN** CI fails the dependency check, for the same reason it fails on a collector import:
  scoring must not depend on the network
