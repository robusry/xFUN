# xFUN

Predicting which soccer matches will be entertaining to watch, for viewers in the US,
across leagues people actually follow.

> **Status: walking skeleton with one working model.** Every tier exists and is
> connected end to end, and most components inside them are deliberately minimal.
> The pipeline acquires real upcoming matches and their US broadcasters and scores
> them from goals really scored — everything else is placeholder. Nothing here is
> *validated*, and by decision it will not be: see `openspec/config.yaml`. Read
> [`docs/STUBS.md`](docs/STUBS.md) for what is real and what is not.

> **Running this needs network access to goal.com.** There is no offline or
> fixture-backed mode: a run acquires from the schedule source or it produces nothing.
> That is deliberate — the thing you run and the thing CI checks are the same code,
> rather than two systems that drift apart. The test suite is fully offline and needs
> no network at all. goal.com is an unofficial source with no API and no stability
> promise, so when it changes shape a run fails loudly; see
> [`docs/STUBS.md`](docs/STUBS.md).

## Setup

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.12 | |
| [uv](https://docs.astral.sh/uv/) | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node | ≥ 20 | |
| [pnpm](https://pnpm.io/) | 9.x | `corepack enable && corepack prepare pnpm@9.12.0 --activate` |
| OpenSpec | **pinned, see `.openspec-version`** | `npm install -g @fission-ai/openspec@1.6.0` |

```bash
uv sync --all-packages     # NOT plain `uv sync` — that installs only the root
pnpm install
pnpm client:generate       # REQUIRED — generates TS types from contracts/openapi.yaml
```

`pnpm client:generate` is not optional. The generated types are gitignored, because
committing them would create a second place for the API's shape to live. Skipping it
is quietly nasty: `pnpm web:dev` still serves fine with every type silently `any`, and
you find out at `pnpm web:build` or in CI.

Check the setup took:

```bash
uv run pytest -q                                 # 252 passed, no network needed
uv run python scripts/check_api_conformance.py   # 8 checks, 0 failed
pnpm -r typecheck
```

## Run it

**Needs network access to goal.com.**

```bash
uv run python scripts/pipeline.py
```

Acquires upcoming matches and their US broadcasters, collects the goals each side
scored in its last five completed matches, runs every registered model, and writes
scores. No database server, no containers, no credentials — the database is a SQLite
file at `.data/xfun.db`, and deleting it costs nothing.

Two of the three registered models are placeholders that skip every match, because
nothing fetches odds or league tables yet; they report a reason rather than
disappearing. `recent-goals-total` is the one that scores. Matches where a side has
fewer than five completed matches also come back with a recorded skip reason and no
score — that is the partial-coverage path working, not a failure.

If the source cannot be read, the run says so and stops. It does not fall back to
anything, because a score from yesterday's matches is a different claim from a score
from today's, and no stored row could tell you which it was.

Then serve it, in a second terminal:

```bash
uv run uvicorn xfun_api:app --port 8000     # http://localhost:8000/docs
```

The API is read-only and never writes. Against an empty database it returns 500 on
the first request rather than an empty list, because the schema is created by the
pipeline's migrations — so run the pipeline first.

For the web page, in a third terminal:

```bash
pnpm web:dev            # http://localhost:5173
```

Keep both ports as they are unless you change both: the page defaults to
`http://localhost:8000` (override with `VITE_API_URL`) and the API allows
cross-origin requests from `http://localhost:5173` alone. Changing one gives you a
CORS error in the browser and an empty page, with nothing wrong in either log.

## What it does

```
schedule source ──▶ ingestion ──▶ store ──▶ slate ──▶ collectors
   (goal.com)                                              │
                                                           │ signals, keyed by
                                                           │ match / team / league
                                                           ▼
                              web ◀── API ◀── store ◀── models
                                       │
                          scores are precomputed in batch;
                          the API never runs a model
```

Two tiers may touch the network and no others: the schedule source, which runs before
the slate because it produces it, and collectors, which run after and enrich it.

Several independently developed models each score a match. Their raw scores are the
system's only truth — calibration and composition are derived at read time, because
the caller chooses the calibration cohort per request.

Read [`docs/architecture.md`](docs/architecture.md) for why.

## Pinned dependencies

Both dependency trees are pinned — `uv.lock` and `pnpm-lock.yaml` are committed, and
CI installs with `--locked` / `--frozen-lockfile` so a stale lock fails rather than
silently resolving something different. After changing a Python dependency, run
`uv lock` and commit the result.

**The OpenSpec version is pinned too.** Artifact templates, workflow schemas, and
validation rules ship with the CLI rather than this repository, so contributors on
different versions generate divergent artifacts. CI verifies the version in use
matches `.openspec-version`.

## Where to start

Almost nothing here is finished, and that is on purpose. Start by reading
[`docs/STUBS.md`](docs/STUBS.md) — it says what is real, what is placeholder, and
which change replaces each placeholder. Building on an unmarked stub is the main way
to waste a week.

| If you are working on | Read | Then look at |
|---|---|---|
| **A scoring model** | [`packages/scoring-contract/README.md`](packages/scoring-contract/README.md) | `packages/models/recent-goals-total/` — copy its shape. A model is a pure function with no I/O. |
| **A data source** | [`packages/collectors/README.md`](packages/collectors/README.md) | `packages/collectors/recent-results/` — a real collector; one of the two tiers allowed on the network |
| **Data ingestion** | [`packages/ingestion/README.md`](packages/ingestion/README.md) | `schedule/` acquires the slate; `fixtures.py` is test-only input |
| **The API** | [`packages/api/README.md`](packages/api/README.md) | `contracts/openapi.yaml` — the contract is the source of truth; the API is validated against it |
| **The website** | [`packages/web/README.md`](packages/web/README.md) | `packages/web/src/App.tsx` — the whole page is one file |
| **Anything at all** | [`docs/architecture.md`](docs/architecture.md) | the four decisions that explain most of the code |

Everything CI runs, in order — worth running before you open a PR:

```bash
uv run python scripts/check_dependencies.py      # tier boundaries
uv run ruff check .
uv run pytest -q                                 # includes the offline end-to-end run
uv run python scripts/check_api_conformance.py   # responses match the contract
uv run python scripts/validate_contracts.py      # fixtures match the schemas
pnpm -r typecheck && pnpm web:build
openspec validate --all --strict
```

Three of those enforce rules that are easy to break by accident and hard to notice
afterwards — models staying pure, the API never importing a model, and live responses
matching the contract. If one fails, it has found something; don't weaken it to pass.

## Contributing

Read [`docs/workflow.md`](docs/workflow.md) and [`docs/zones.md`](docs/zones.md) before
your first change. In short:

- Create a branch **before** touching any file, including before `openspec new change`
- Not every change needs a spec — `docs/zones.md` says which do, and most changes
  outside `contracts/` and the scoring core do not
- Open the pull request when the change is **complete**: artifacts, implementation, and
  the archive commit. Push work in progress to the branch freely; the absence of a PR
  is what signals "not ready"
- Conventional Commits, squash-merge by convention

You do not have to use OpenSpec to contribute. Hand-edited work is expected, and
`docs/zones.md` explains how it gets captured into specs afterwards.

## Documentation

| | |
|---|---|
| [`docs/`](docs/README.md) | architecture, workflow, zones, stubs |
| `openspec/specs/` | behavioural requirements — normative; the docs only explain |
| `openspec/config.yaml` | the design brief: why things are the way they are, and what is still open |
| [`CLAUDE.md`](CLAUDE.md) | orientation for AI coding agents; useful to humans too |
