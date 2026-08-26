## MODIFIED Requirements

### Requirement: Single monorepo with a language-neutral contract seam

The project SHALL be organized as a single Git repository containing all tiers. A top-level `contracts/` directory SHALL hold the language-neutral interface definitions shared between tiers — the OpenAPI document, JSON Schema definitions for `MatchSnapshot` and `ModelScore`, and golden fixtures. `contracts/` SHALL contain no executable application code.

`contracts/` SHALL hold only material that is authored by this project and agreed
between tiers. Captured responses from an external source SHALL NOT be stored there:
they validate against no schema of ours, their shape is not ours to define, and they
are refreshed wholesale when the source changes. Such captures SHALL live under a
path that identifies them as verification input, alongside a statement of what they
are and which tool regenerates them.

#### Scenario: Contract change spans multiple tiers

- **WHEN** a contributor changes an interface definition in `contracts/`
- **THEN** the contract change and every affected tier's code change are reviewable in a single pull request against a single repository

#### Scenario: Executable code is proposed for the contracts directory

- **WHEN** a pull request adds application logic to `contracts/`
- **THEN** the change is rejected and the logic is relocated to the consuming package

#### Scenario: A captured third-party response is proposed for the contracts directory

- **WHEN** a pull request adds a captured page or response from an external source to `contracts/`
- **THEN** the change is rejected and the capture is relocated to the verification input path

#### Scenario: A reader asks whether a file is a contract or a capture

- **WHEN** a contributor encounters a data file used by tests
- **THEN** its location alone answers whether it is an agreement between tiers or a captured artefact of somebody else's system, without their having to read a document to find out

### Requirement: Tiers are developable against fixtures before upstream tiers exist

Every tier SHALL be buildable and testable using only `contracts/` definitions and the golden fixtures in `contracts/fixtures/`, without requiring any other tier to be running. Fixtures SHALL be validated against their JSON Schema in CI, and the same fixture files SHALL be used by both the producing and consuming tiers' tests.

This SHALL remain true of development and testing, and SHALL NOT be read as a claim
about running the system. The pipeline itself requires access to the schedule source
and has no fixture-backed mode; a contributor can build and test any tier offline, but
cannot produce a slate offline.

#### Scenario: Website development begins before the API is deployed

- **WHEN** a web developer starts work and no API instance exists
- **THEN** they generate a typed client from `contracts/openapi.yaml`, serve `contracts/fixtures/` from a local mock, and build the full interface against it

#### Scenario: A producer emits output violating the shared schema

- **WHEN** an ingestion or scoring package produces output that does not validate against its JSON Schema in `contracts/schemas/`
- **THEN** CI fails before the output can reach a consuming tier

#### Scenario: A contributor with no network runs the test suite

- **WHEN** a contributor with no external access runs the tests
- **THEN** every test passes, because all of them supply their own inputs rather than acquiring any

#### Scenario: A contributor with no network runs the pipeline

- **WHEN** a contributor with no external access runs the pipeline
- **THEN** acquisition fails, the run records a source failure and exits, and no fixture-backed alternative is offered
