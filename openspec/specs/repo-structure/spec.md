# repo-structure Specification

## Purpose
TBD - created by archiving change establish-project-structure. Update Purpose after archive.
## Requirements
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

### Requirement: Prescribed package layout

The repository SHALL follow this top-level layout:

```
openspec/       OpenSpec specs and changes
contracts/      openapi.yaml, schemas/, fixtures/
packages/
  scoring-contract/       model interface and shared types
  scoring-runtime/        registry, feature assembly, model runner
  models/<model-id>/      one independently owned package per model
  collectors/<id>/        one independently owned package per data source
  composition/            recipes and composition logic
  evaluation/             labels, backtests, model leaderboard
  ingestion/              slate assembly and snapshot writing
  api/                    read-only public API
  web/                    website
  mobile/                 mobile app (future)
  clients/                generated API clients (ts, py)
infra/          database migrations, deployment, scheduling
docs/
```

Each package under `packages/` SHALL declare its own dependencies independently, so that a dependency required by one package is not imposed on the others.

#### Scenario: A model requires heavy machine-learning dependencies

- **WHEN** a model package declares a large dependency such as a deep-learning framework
- **THEN** that dependency is confined to that model's package and is absent from the dependency sets of the API, web, and other model packages

#### Scenario: A new model is added

- **WHEN** a contributor adds a new scoring model to the project
- **THEN** the change touches only a new directory under `packages/models/` and the model registry entry, and requires no modification to `packages/api/`, `packages/web/`, or any other model package

#### Scenario: A new data source is added

- **WHEN** a contributor adds a collector for a data source no existing collector covers
- **THEN** the change touches only a new directory under `packages/collectors/` and the collector registry entry, and requires no modification to `contracts/schemas/match-snapshot.json`, to any model package, or to `packages/api/`

#### Scenario: A collector's dependencies stay confined

- **WHEN** a collector package declares credentials handling or a third-party client library
- **THEN** that dependency is absent from the dependency sets of every model package and of `packages/api/`

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

### Requirement: Scores are precomputed in batch, never on request

Scores SHALL be computed by scheduled jobs and persisted. The API SHALL NOT invoke scoring models during request handling, and the API's runtime SHALL NOT depend on any model package.

#### Scenario: A scoring model fails or is slow

- **WHEN** a scoring model raises an error or takes an unbounded amount of time during a scheduled run
- **THEN** the API continues serving previously computed scores and remains available

#### Scenario: A model is rewritten in a different language

- **WHEN** a model implementation is replaced with one written in a different language or framework
- **THEN** no change is required in the API, clients, or web packages, provided the model still writes conforming rows to the score store

### Requirement: Continuous integration is scoped by path

CI SHALL run only the checks relevant to the packages a pull request modifies, except for contract validation and spec validation, which SHALL run on every pull request.

#### Scenario: A change touches only the website

- **WHEN** a pull request modifies files only under `packages/web/`
- **THEN** the Python model and ingestion test suites are not executed, while contract and spec validation still run

### Requirement: Tier boundaries for data collection are enforced by CI

CI SHALL verify that no model package and no API package imports a collector package or declares a collector package as a dependency. CI SHALL NOT apply the model purity rules to collector packages, since external access is the purpose of that tier.

#### Scenario: A model imports a collector to reach its source directly

- **WHEN** a model package imports a collector package
- **THEN** CI fails the dependency check, naming the model and the collector

#### Scenario: The API imports a collector

- **WHEN** the API package imports or declares a dependency on a collector package
- **THEN** CI fails the dependency check

#### Scenario: A collector declares dependencies a model could not

- **WHEN** a collector package declares an HTTP client, a database driver, or a credentials library
- **THEN** CI passes, because those constraints apply to models rather than to collectors

