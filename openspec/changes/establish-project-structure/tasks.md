> **Scope: walking skeleton.** Every tier exists and is connected end to end, running on
> fixture data. Implementations are deliberately minimal — the deliverable is a structure
> collaborators can read and understand, not working functionality. Anything placeholder
> MUST be marked as such and name the follow-up change that replaces it (see section 13).

## 1. Repository skeleton

- [ ] 1.1 Create top-level `contracts/`, `packages/`, `infra/`, `docs/` with placeholder READMEs stating each tree's purpose
- [ ] 1.2 Set up `uv` workspaces for Python, with each package declaring its own dependencies so a model's dependencies are not imposed on other packages
- [ ] 1.3 Set up `pnpm` workspaces for TypeScript covering `web` and `clients/ts`, with a reserved `mobile` slot
- [x] 1.4 Add `.gitkeep` to `openspec/specs/` and `openspec/changes/archive/` so both survive a clone
- [x] 1.5 Write the root `.gitignore` excluding per-tool local settings overrides while tracking generated tool instruction files
- [ ] 1.6 Record the pinned OpenSpec CLI version and document how contributors install it
- [ ] 1.7 Request branch protection on `main` from the repository owner (needs owner access; do not lock down merge strategy)

## 2. Contracts and fixtures

*Real, not stubbed — these are the bootstrap's actual deliverable.*

- [ ] 2.1 Define `contracts/schemas/match-snapshot.json` with the initial feature set (fixture identity, kickoff time, league, teams, odds snapshot, form, table position)
- [ ] 2.2 Define `contracts/schemas/model-score.json` covering `model_id`, `model_version`, `raw_score`, `components`, `snapshot_hash`
- [ ] 2.3 Author golden fixtures under `contracts/fixtures/`, including edge cases: missing odds, a match scored by only one model, a match with no scores
- [ ] 2.4 Draft `contracts/openapi.yaml` covering match listing, per-match scores, and the registry endpoint
- [ ] 2.5 Add CI validating all fixtures against their schemas and linting `openapi.yaml`

## 3. Scoring contract and runtime

- [ ] 3.1 Implement `packages/scoring-contract/` with `MatchSnapshot` and `ModelScore` types tied to the JSON Schemas
- [ ] 3.2 Implement the model interface including the required-features declaration
- [ ] 3.3 Implement the model registry with `model_id` / `model_version` registration
- [ ] 3.4 Implement snapshot hashing so identical inputs produce identical hashes
- [ ] 3.5 Implement the model runner: fan out over registered models, collect scores, skip models whose required features are unavailable

## 4. Score store

- [ ] 4.1 Write the migration for the raw score table keyed by (`match_id`, `model_id`, `model_version`, `snapshot_hash`)
- [ ] 4.2 Enforce append-only at the database level (reject UPDATE and DELETE)
- [ ] 4.3 Implement the latest-score-per-(match, model) serving read while retaining superseded rows

## 5. Calibration — one cohort only

- [ ] 5.1 Implement percentile-rank calibration to a 0–100 scale, computed per model
- [ ] 5.2 Implement the `window` cohort resolver only; `league`, `season`, and `global` raise "not implemented" and are listed in `docs/STUBS.md`
- [ ] 5.3 Report the cohort definition and cohort match count alongside every calibrated score

## 6. Composition — one policy only

- [ ] 6.1 Define the composition recipe format (models, weights, missing-model policy, `min_models`, version)
- [ ] 6.2 Implement recipe loading and validation, failing on unknown `model_id` and on a missing missing-model policy
- [ ] 6.3 Implement the `renormalize` missing-model policy only; `require-all` and `fallback` raise "not implemented" and are listed in `docs/STUBS.md`
- [ ] 6.4 Implement alias resolution with `default` always present
- [ ] 6.5 Author the initial `default` recipe as configuration

## 7. Placeholder model

*Deliberately trivial. Demonstrates the contract; makes no claim to predict anything.*

- [ ] 7.1 Create `packages/models/placeholder/` as an independent package
- [ ] 7.2 Implement it as a pure function over one or two declared features, emitting a raw score and a components map, with a module docstring stating plainly that it is a placeholder
- [ ] 7.3 Add a determinism test asserting identical output for identical fixture input
- [ ] 7.4 Add a second placeholder model with different required features, so multi-model fan-out and the missing-model path are both exercised

## 8. Ingestion — fixture-backed, no network

- [ ] 8.1 Write migrations for canonical entities: league, team, match, odds snapshot, team form
- [ ] 8.2 Implement the source adapter interface
- [ ] 8.3 Implement a fixture-file adapter that reads from `contracts/fixtures/` — no HTTP, no provider, no credentials
- [ ] 8.4 Implement snapshot assembly from canonical entities to a schema-valid `MatchSnapshot`

## 9. Public API

- [ ] 9.1 Scaffold `packages/api/` as a FastAPI application, validated against `contracts/openapi.yaml` rather than generating it — the contract is the source of truth
- [ ] 9.2 Implement match listing with the score alias and calibration cohort request parameters, defaulting the cohort to `window` and reporting both in the response
- [ ] 9.3 Implement per-match scores exposing each model's calibrated score alongside the composed score, with explanation payloads
- [ ] 9.4 Implement the registry endpoint listing models, compositions, and aliases
- [ ] 9.5 Generate `clients/ts` from `openapi.yaml`
- [ ] 9.6 Add a CI check asserting the API package does not depend on any model package

## 10. Web

- [ ] 10.1 Scaffold `packages/web/` consuming the generated TypeScript client
- [ ] 10.2 Build a single page: matches for a date range ranked by score, showing the composed score, contributing model scores, and the calibration cohort in use

## 11. End-to-end demo

*The most important section for comprehension — a collaborator should see data flow through every tier in one command.*

- [ ] 11.1 Write a single command that seeds fixtures, runs ingestion, runs both placeholder models, writes scores, and serves the API
- [ ] 11.2 Add a README quickstart: clone, one command, see a ranked list in the browser
- [ ] 11.3 Add an end-to-end test asserting a fixture match flows from ingestion through scoring to an API response

## 12. Process and CI

- [ ] 12.1 Configure path-filtered CI so package suites run only for touched packages
- [ ] 12.2 Make contract validation and `openspec validate` run on every pull request and block on failure
- [ ] 12.3 Add the PR template with the workflow checklist and the Zone A/B behavior-change question
- [ ] 12.4 Create the `spec-debt` label and automation flagging unspecced Zone A/B pull requests, warning rather than blocking
- [ ] 12.5 Add Conventional Commits linting for commit messages and pull request titles, with `spec` in the permitted type list
- [ ] 12.6 Add a `CODEOWNERS` entry requiring team review on `contracts/`, naming the team rather than an individual
- [ ] 12.7 Add a CI check verifying the OpenSpec CLI version matches the pinned version
- [ ] 12.8 Establish the recurring reconciliation pass as a shared team activity: cadence and the procedure for clearing `spec-debt` items using `openspec doctor` and `openspec list --specs`

## 13. Documentation

*Comprehension is this change's deliverable, so docs are not an afterthought.*

- [ ] 13.1 Write `docs/architecture.md` with the tier diagram, the batch-scoring seam, and the truth-vs-derived split
- [ ] 13.2 Write `docs/workflow.md` covering branch-first, branch naming, PR-when-complete, rebase-then-archive, and squash-merge as convention
- [ ] 13.3 Write `docs/zones.md` with the Zone A/B/C table, both contribution paths, and a worked capture-change example
- [ ] 13.4 Write `docs/STUBS.md` enumerating every placeholder, what it does today, and which follow-up change replaces it
- [ ] 13.5 Give each package a README stating its role and whether it is real or placeholder

## 14. Follow-up changes to propose

- [ ] 14.1 `add-market-baseline-model` — the first real model, over betting odds
- [ ] 14.2 `add-live-ingestion` — provider selection and real fixture/odds adapters, replacing the fixture-file adapter
- [ ] 14.3 `complete-calibration-cohorts` — the `league`, `season`, and `global` resolvers, cohort caching, minimum cohort size handling, and a season-sized benchmark
- [ ] 14.4 `complete-composition-policies` — `require-all` and `fallback`, `min_models` enforcement, pinned composition targets, and the recompose job
- [ ] 14.5 `add-score-provenance` — snapshot persistence, retired-model metadata, and full reproducibility from a stored row
- [ ] 14.6 `add-evaluation-harness` — ground-truth labels, backtests, and the model leaderboard
- [ ] 14.7 `define-league-scope` — audience size versus entertainment density
- [ ] 14.8 `add-broadcast-availability` — data sourcing, the unknown state, and staleness detection
