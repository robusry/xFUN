## Why

xFUN predicts which soccer matches will be entertaining to watch, for a US audience, across leagues people actually follow. The work spans four tiers — data ingestion, scoring models, a public API, and client apps (web now, mobile later) — built by a team collaborating on GitHub, with some contributors working spec-first and others editing code by hand.

Two decisions need to be settled before any of that code exists, because both are expensive to retrofit:

1. **Tier boundaries.** Without agreed contracts between ingestion, scoring, API, and clients, the tiers cannot be built in parallel and every team blocks on the one upstream of it.
2. **Multi-model scoring.** There will be several independently developed models producing scores for the same match. How those scores are combined and exposed is explicitly undecided and expected to change repeatedly as the product evolves. The architecture must make reversing those decisions cheap, not merely possible.

This change establishes the project's structure, the contracts between tiers, the multi-model scoring architecture, and the workflow that keeps specs in step with a codebase edited by both spec-driven and hand-editing contributors.

## What Changes

- **Monorepo layout** with a language-neutral `contracts/` directory as the single seam between tiers, plus shared golden fixtures so every tier can be developed against the others before they exist.
- **Batch scoring, not on-demand.** Models write scores to a store on a schedule; the API reads. Model runtime is fully decoupled from API runtime.
- **A multi-model scoring platform** rather than a single formula: a stable model interface, a registry, per-model packages with independent dependencies and ownership, and a rule that models never reference one another.
- **Append-only score storage.** Raw model scores are immutable truth, keyed by model identity and version, and are never deleted or updated in place. Retired models keep their historical rows queryable.
- **Runtime-configurable calibration.** Raw model scores are on incomparable native scales. Callers choose the calibration cohort at request time, so calibrated scores are a derived view rather than stored data.
- **Composition as versioned configuration**, not code — a recipe naming models, weights, and an explicit missing-data policy — with stable public aliases (e.g. `default`) that can be repointed without any client change.
- **Individual model scores exposed alongside composites**, so consumers can compose their own blends and so the composition decision stays deferrable indefinitely.
- **A spec workflow with explicit zones**, defining where specs are required, where they are required only on behavior change, and where hand edits are free — plus a named path for capturing hand-edited work back into specs after the fact.
- **Version-controlled OpenSpec standards**: config, specs, changes, archive, and the generated AI tool instruction files are tracked so every contributor works from identical standards, with the OpenSpec CLI version pinned and verified in CI.
- **A branch-and-pull-request workflow**: `main` is protected, a branch is created before any file is touched, one change maps to one branch and one pull request, the pull request opens as a draft at the planning stage so the plan is reviewed before implementation, and the change is rebased and archived as the final commit before merge.

## Capabilities

### New Capabilities

- `repo-structure`: Monorepo layout, tier boundaries, the `contracts/` seam, shared fixtures, and the dependency rules that keep tiers independently buildable.
- `scoring-contract`: The interface every scoring model implements — `MatchSnapshot` in, `ModelScore` out — including feature declaration, purity constraints, and model identity/versioning.
- `score-store`: Append-only persistence semantics for raw model scores: identity keys, immutability, reproducibility metadata, and retention of retired models.
- `score-calibration`: Conversion of incomparable raw model scores onto a common scale, with the cohort selectable by the caller at request time.
- `score-composition`: Versioned composition recipes, missing-model policies, and the alias indirection that decouples public score names from the math behind them.
- `public-api`: The read-only score API surface — versioning, alias resolution, per-model and composed score access, and explainability payloads.
- `spec-workflow`: Zone-based spec requirements, the spec-first and code-first contribution paths, and the mechanisms that make spec drift visible and recoverable.

### Modified Capabilities

None. This is the project's first change; `openspec/specs/` is empty.

## Impact

- **Repository**: introduces `contracts/`, `packages/`, `infra/`, and `docs/` trees. No existing code is affected — the repository currently contains only a README and OpenSpec scaffolding.
- **Tooling**: path-filtered CI for a polyglot (Python + TypeScript) monorepo; contract validation; client generation from OpenAPI.
- **Process**: PR template, a `spec-debt` label, and a recurring reconciliation pass become part of how the team works.
- **Deferred to later changes**: individual model implementations, specific data source adapters, broadcast-availability data, the evaluation harness and ground-truth labels, and league scope. This change defines the slots those fit into, not their contents.
