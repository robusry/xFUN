## 1. Repository skeleton

- [ ] 1.1 Create top-level `contracts/`, `packages/`, `infra/`, `docs/` directories with placeholder READMEs stating each tree's purpose
- [ ] 1.2 Set up Python workspace tooling (single lockfile strategy, per-package dependency declaration) covering `scoring-contract`, `scoring-runtime`, `models/`, `composition`, `evaluation`, `ingestion`
- [ ] 1.3 Set up TypeScript workspace tooling covering `web`, `clients/ts`, and a reserved `mobile` slot
- [ ] 1.4 Write `docs/architecture.md` summarizing the tier diagram, the batch-scoring seam, and the truth-vs-derived split
- [ ] 1.5 Write `docs/zones.md` documenting the Zone A/B/C table and both contribution paths
- [ ] 1.6 Enable branch protection on `main`: reject direct pushes, require a pull request, require passing checks (do this before any other work merges)
- [ ] 1.7 Write `docs/workflow.md` covering the branch-first rule, branch naming prefixes, draft-PR-at-plan-stage, and rebase-then-archive-then-merge
- [ ] 1.8 Add `.gitkeep` to `openspec/specs/` and `openspec/changes/archive/` so both survive a clone
- [ ] 1.9 Write the root `.gitignore` excluding per-tool local settings overrides (e.g. `.claude/settings.local.json`) while tracking generated tool instruction files
- [ ] 1.10 Record the pinned OpenSpec CLI version in the repository and document how contributors install it

## 2. Contracts and fixtures

- [ ] 2.1 Define `contracts/schemas/match-snapshot.json` with the initial feature set (fixture identity, kickoff time, league, teams, odds snapshot, form, table position)
- [ ] 2.2 Define `contracts/schemas/model-score.json` covering `model_id`, `model_version`, `raw_score`, `components`, `snapshot_hash`
- [ ] 2.3 Author golden fixtures under `contracts/fixtures/snapshots/` and `contracts/fixtures/scores/`, including edge cases: missing odds, missing shot data, a match scored by only one model
- [ ] 2.4 Draft initial `contracts/openapi.yaml` covering match listing, per-match scores, model registry, and composition/alias listing
- [ ] 2.5 Add a CI job validating all fixtures against their schemas
- [ ] 2.6 Add a CI job validating `openapi.yaml` parses and lints cleanly

## 3. Scoring contract and runtime

- [ ] 3.1 Implement `packages/scoring-contract/` with `MatchSnapshot` and `ModelScore` types generated from or validated against the JSON Schemas
- [ ] 3.2 Implement the model interface, including the required-features declaration
- [ ] 3.3 Implement the model registry with stable `model_id` and `model_version` registration, and validation that declared features exist in the snapshot schema
- [ ] 3.4 Implement snapshot hashing so identical inputs produce identical hashes
- [ ] 3.5 Implement feature assembly: build each model's declared subset from a full snapshot, and skip-with-reason when required features are unavailable
- [ ] 3.6 Implement the model runner: fan out over registered models in arbitrary order, collect scores and skips, and prove order-independence with a test
- [ ] 3.7 Add a CI purity check for model packages: no database drivers, no HTTP clients, no cross-model imports
- [ ] 3.8 Add a determinism test harness that any model can be run through, asserting identical output for identical fixture input

## 4. Score store

- [ ] 4.1 Write the migration for the raw score table keyed by (`match_id`, `model_id`, `model_version`, `snapshot_hash`) with `raw_score`, `components`, `computed_at`
- [ ] 4.2 Enforce append-only at the database level (reject UPDATE and DELETE on the score table)
- [ ] 4.3 Add snapshot persistence and retrieval so any stored score can be traced back to its exact input
- [ ] 4.4 Implement the latest-score-per-(match, model) serving read while retaining superseded rows
- [ ] 4.5 Add model registry metadata including retirement status, with retired models' rows remaining queryable
- [ ] 4.6 Write tests covering re-scoring on updated snapshots, and confirming retired-model history survives

## 5. Calibration

- [ ] 5.1 Implement percentile-rank calibration to a 0–100 scale, computed per model and model version
- [ ] 5.2 Implement the `window`, `league`, `season`, and `global` cohort resolvers
- [ ] 5.3 Implement minimum cohort size handling with the documented fallback or low-confidence marking
- [ ] 5.4 Ensure every calibration result carries its cohort definition and cohort match count
- [ ] 5.5 Implement the calibration cache keyed by (model identity, cohort, raw-score generation) with invalidation on new raw rows
- [ ] 5.6 Test that the same match calibrates differently under different cohorts and that both results are reproducible
- [ ] 5.7 Benchmark calibration over a realistic season-sized cohort to confirm read-time computation is viable

## 6. Composition

- [ ] 6.1 Define the composition recipe format (models, weights, missing-model policy, `min_models`, version)
- [ ] 6.2 Implement recipe loading and validation, failing on unknown `model_id` and on a missing missing-model policy
- [ ] 6.3 Implement the `require-all`, `renormalize`, and `fallback` missing-model policies
- [ ] 6.4 Implement `min_models` enforcement with a reported reason when no composed score is produced
- [ ] 6.5 Implement alias resolution supporting both composition targets and single-model targets, with `default` always present
- [ ] 6.6 Implement pinned composition targets that are never repointed
- [ ] 6.7 Implement the recompose job over stored raw scores and confirm it executes no models
- [ ] 6.8 Author the initial `default` recipe as configuration, with a single documented owner for changes to it

## 7. Reference model

- [ ] 7.1 Create `packages/models/market-baseline/` as the first model package with independent dependencies
- [ ] 7.2 Implement it as a pure function over declared features derived from odds, emitting a raw score and a components map
- [ ] 7.3 Write its capability spec covering the signal it claims to capture, required features, native output scale, and known coverage gaps
- [ ] 7.4 Run it end to end against fixtures through the runtime, proving the contract works before any real data exists

## 8. Ingestion

- [ ] 8.1 Write migrations for canonical entities: league, team, match, odds snapshot, team form
- [ ] 8.2 Implement the adapter interface for data sources, with idempotent scheduled runs
- [ ] 8.3 Implement one fixture/schedule source adapter for a single league
- [ ] 8.4 Implement one odds source adapter producing conforming odds snapshots
- [ ] 8.5 Implement snapshot assembly: canonical entities to a schema-valid `MatchSnapshot`
- [ ] 8.6 Add CI validation that assembled snapshots conform to `match-snapshot.json`
- [ ] 8.7 Design the broadcast-availability model as a separate module with its own cadence and an explicit unknown state

## 9. Public API

- [ ] 9.1 Decide and record the API implementation language (see design open questions)
- [ ] 9.2 Implement path-versioned read endpoints for match listing and per-match scores
- [ ] 9.3 Implement the score alias and calibration cohort request parameters, with documented defaults reported in every response
- [ ] 9.4 Implement per-model score exposure alongside composed scores
- [ ] 9.5 Implement the registry endpoint listing models (with retirement status), compositions, and aliases
- [ ] 9.6 Implement explanation payloads: contributing models, weights, per-model calibrated scores, and components
- [ ] 9.7 Include broadcast availability with an explicit unknown state
- [ ] 9.8 Add a CI contract-conformance check asserting responses match `openapi.yaml`
- [ ] 9.9 Add a CI check asserting the API package does not depend on any model package
- [ ] 9.10 Generate `clients/ts` and `clients/py` from `openapi.yaml` in CI

## 10. Web

- [ ] 10.1 Scaffold `packages/web/` consuming the generated TypeScript client
- [ ] 10.2 Stand up a fixture-backed mock server so web development runs with no API deployed
- [ ] 10.3 Build a ranked match list for a date range, showing score, explanation, and availability
- [ ] 10.4 Surface the calibration cohort in the interface so a displayed score is never uninterpretable

## 11. Process and CI

- [ ] 11.1 Configure path-filtered CI so package-specific suites run only for touched packages
- [ ] 11.2 Make contract validation and `openspec validate` run on every pull request and block on failure
- [ ] 11.3 Add the PR template asking whether observable behavior changed in a Zone A or Zone B path
- [ ] 11.4 Create the `spec-debt` label and the automation that flags unspecced Zone A/B pull requests and requires it, warning rather than blocking
- [ ] 11.5 Add a required-reviewer rule on `contracts/`
- [ ] 11.6 Document the code-first capture-change procedure in `docs/zones.md` with a worked example
- [ ] 11.7 Schedule the recurring reconciliation pass and name its owner
- [ ] 11.8 Run `openspec doctor` and record its output as the baseline spec-health reading
- [ ] 11.9 Add a CI check that a pull request touching `openspec/changes/<id>/` has a branch name matching `change/<id>` or `capture/<id>`
- [ ] 11.10 Add a merge check that blocks a pull request containing an unarchived OpenSpec change, so `main` specs never lag `main` code
- [ ] 11.11 Extend the PR template with the workflow checklist: plan reviewed while draft, tasks complete, rebased on `main`, archived
- [ ] 11.12 Document the conflict-resolution procedure for a rebase where another change archived the same capability first
- [ ] 11.13 Add a CI check verifying the OpenSpec CLI version in use matches the pinned version
- [ ] 11.14 Add Conventional Commits linting for commit messages and pull request titles, with the permitted type list including `spec`
- [ ] 11.15 Decide and configure the merge strategy (see design open questions) and align commit linting with it

## 12. Follow-up changes to propose

- [ ] 12.1 Propose the evaluation harness change: ground-truth labels, backtests, and the model leaderboard
- [ ] 12.2 Propose the league-scope change resolving audience size versus entertainment density
- [ ] 12.3 Propose the broadcast-availability change covering data sourcing and staleness detection
