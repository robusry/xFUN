# xFUN

Predicting which soccer matches will be entertaining to watch, for viewers in the
US, across leagues people actually follow.

## Read this first

**`openspec/config.yaml` holds the full design context. Read it before doing any
design or implementation work.** It is the authoritative record of what has been
decided and why, what must not be "simplified", and what is still open. This file
is a pointer, plus the operational detail config.yaml does not carry.

**`docs/STUBS.md` says what is real and what is placeholder.** Most of this
repository is deliberately minimal. Read it before assuming anything works.

## Project state

**A walking skeleton.** Every tier exists and is connected end to end on fixture
data. It runs — `./scripts/demo.sh` seeds fixtures, scores them, and serves the
API with no database server, no container, and no credentials. But the components
inside the tiers are placeholders by design: the deliverable so far is a structure
the team can read and run, not working functionality.

Both models predict nothing. Ingestion reads files. Three of four calibration
cohorts and two of three composition policies return 501.

`openspec/specs/` is the authoritative record of what the system currently
**does** — seven capabilities, 46 requirements — while `openspec/config.yaml`
holds the reasoning behind them. Archived changes are under
`openspec/changes/archive/`:

- `2026-08-01-establish-project-structure` — the architecture, the workflow, and
  the skeleton itself

**This file does not set priorities.** "Still open" below records what is
undecided, not a queue. Ask what the session is for rather than inferring it.

## The design in one paragraph

Several models, developed independently, each score a match. Their **raw scores
are the only truth** — stored append-only, never updated. Calibration and
composition happen at **read** time, because the caller chooses the calibration
cohort per request, so a calibrated score is not a property of a stored row.
Models are pure functions that declare which snapshot features they need; matches
missing those features are skipped with a recorded reason, which is routine rather
than exceptional. How scores are blended is versioned configuration behind a
repointable alias, so the blending decision stays cheap to change — which is the
point, because it is expected to change repeatedly.

## Do not "fix" these

Full list with rationale is in `openspec/config.yaml`. The ones most likely to
look like bugs:

- **Calibrated and composed scores are not stored.** Deriving them per request is
  the design, not a missing optimisation.
- **Models return unnormalised `raw_score` on arbitrary scales.** Normalising in
  the model is forbidden; the platform percentile-ranks.
- **There is no update or delete path for scores.** Database triggers enforce it.
- **The API imports no model package.** CI fails if one appears.
- **Unimplemented cohorts/policies raise rather than falling back**, and surface
  as 501.
- **Matches with no score are still returned**, with a reason.

## Layout

```
contracts/          the seam: JSON Schemas, openapi.yaml, golden fixtures
packages/
  scoring-contract/   model interface + types. no deps, no I/O.
  scoring-runtime/    registry, feature assembly, runner, calibration
  store/              canonical entities + append-only score store
  models/<id>/        one package per model, deps isolated
  composition/        src/ = mechanism (Zone A), recipes/ = values (Zone C)
  ingestion/          source adapters
  api/                FastAPI, read-only
  web/                Vite + React, one page
  clients/ts/         generated from openapi.yaml
infra/migrations/   plain .sql, applied in filename order
docs/               architecture, workflow, zones, STUBS
scripts/            demo, pipeline, and the CI check scripts
```

## Setup and verification

```bash
uv sync --all-packages    # NOT plain `uv sync` — that installs only the root
pnpm install
pnpm client:generate      # types from contracts/openapi.yaml; gitignored
```

Everything CI runs, in the order it runs:

```bash
uv run python scripts/check_dependencies.py      # tier boundaries
uv run ruff check .
uv run pytest -q                                 # 28 tests
uv run python scripts/pipeline.py                # end-to-end on fixtures
uv run python scripts/check_api_conformance.py   # responses match the contract
uv run python scripts/validate_contracts.py      # fixtures match the schemas
pnpm -r typecheck && pnpm web:build
openspec validate --all --strict
```

Both lockfiles are committed and CI installs with `--locked` / `--frozen-lockfile`.
After changing a Python dependency, run `uv lock` and commit the result.

Three checks exist because the rules they enforce are easy to break by accident
and hard to notice afterwards — model purity, the API not importing a model, and
live responses matching `contracts/openapi.yaml`. Do not weaken them to make a
change pass.

## Code conventions

- Python 3.12, `from __future__ import annotations`, `collections.abc` for ABCs.
- Comments explain **why**, especially where the code looks unnecessarily
  indirect. Most of the surprising code here is deliberate.
- A model depends on `xfun-scoring-contract` and nothing else.
- Anything placeholder says so in its module docstring, its package README, and
  `docs/STUBS.md`. An unmarked stub is worse than a missing feature.

## Workflow

Full detail in `docs/workflow.md`; zones in `docs/zones.md`.

- **Branch before touching any file**, including before `openspec new change`.
  `change/<id>`, `capture/<id>`, or `chore/<slug>`.
- One change = one branch = one PR.
- **The PR opens only when the change is complete** — artifacts, implementation,
  and the archive commit. Push WIP to the branch freely; the absence of a PR is
  what signals "not ready".
- Rebase on `main`, then `openspec archive`, then open the PR.
- Conventional Commits. `spec` is a valid type, for planning and archive commits.
  The PR title matters most — squash-merge makes it the commit subject.
- Not every change needs specs. `docs/zones.md` says which do.

Decisions are made by the team as a group; PR approval is the deciding gate. No
individual owns any part of this project.

## Still open

Not a queue — nothing here is claimed as next.

- **What "fun" means, measured.** There is no ground-truth label, so no formula
  can be evaluated and "which models at what weights" has no answerable form.
  The most consequential open question in the project, and the reason
  `add-evaluation-harness` is the follow-up worth arguing for first.
- Global versus personalised as the headline score.
- League scope: audience size versus entertainment density.
- The default calibration cohort, once more than one exists.
- Whether `default` carries a stability promise for third parties.

## Absent on purpose, not forgotten

`docs/STUBS.md` is authoritative. In short: no real model, no live data provider,
no evaluation harness, no broadcast availability data, no mobile app, and no
automated JavaScript test — CI covers the TS side with typecheck and build only.

Branch protection on `main` is enabled. Adding `contracts`, `ci`, and `pr-hygiene`
as required status checks is still outstanding.
