## ADDED Requirements

### Requirement: Single monorepo with a language-neutral contract seam

The project SHALL be organized as a single Git repository containing all tiers. A top-level `contracts/` directory SHALL hold the language-neutral interface definitions shared between tiers — the OpenAPI document, JSON Schema definitions for `MatchSnapshot` and `ModelScore`, and golden fixtures. `contracts/` SHALL contain no executable application code.

#### Scenario: Contract change spans multiple tiers

- **WHEN** a contributor changes an interface definition in `contracts/`
- **THEN** the contract change and every affected tier's code change are reviewable in a single pull request against a single repository

#### Scenario: Executable code is proposed for the contracts directory

- **WHEN** a pull request adds application logic to `contracts/`
- **THEN** the change is rejected and the logic is relocated to the consuming package

### Requirement: Prescribed package layout

The repository SHALL follow this top-level layout:

```
openspec/       OpenSpec specs and changes
contracts/      openapi.yaml, schemas/, fixtures/
packages/
  scoring-contract/    model interface and shared types
  scoring-runtime/     registry, feature assembly, model runner
  models/<model-id>/   one independently owned package per model
  composition/         recipes and composition logic
  evaluation/          labels, backtests, model leaderboard
  ingestion/           per-source data adapters
  api/                 read-only public API
  web/                 website
  mobile/              mobile app (future)
  clients/             generated API clients (ts, py)
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

### Requirement: Tiers are developable against fixtures before upstream tiers exist

Every tier SHALL be buildable and testable using only `contracts/` definitions and the golden fixtures in `contracts/fixtures/`, without requiring any other tier to be running. Fixtures SHALL be validated against their JSON Schema in CI, and the same fixture files SHALL be used by both the producing and consuming tiers' tests.

#### Scenario: Website development begins before the API is deployed

- **WHEN** a web developer starts work and no API instance exists
- **THEN** they generate a typed client from `contracts/openapi.yaml`, serve `contracts/fixtures/` from a local mock, and build the full interface against it

#### Scenario: A producer emits output violating the shared schema

- **WHEN** an ingestion or scoring package produces output that does not validate against its JSON Schema in `contracts/schemas/`
- **THEN** CI fails before the output can reach a consuming tier

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
