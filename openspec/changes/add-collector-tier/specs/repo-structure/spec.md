## MODIFIED Requirements

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

## ADDED Requirements

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
