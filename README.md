# xFUN

Predicting which soccer matches will be entertaining to watch, for viewers in the US,
across leagues people actually follow.

> **Status: walking skeleton.** Every tier exists and is connected end to end, running
> on fixture data. The components are deliberately minimal — this repository is
> currently something to *read and understand*, not something that works. See
> [`docs/STUBS.md`](docs/STUBS.md) for what is placeholder and what replaces it.

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
uv run pytest -q                                 # 28 passed
uv run python scripts/check_api_conformance.py   # 8 checks, 0 failed
pnpm -r typecheck
```

## Run it

```bash
./scripts/demo.sh
```

Seeds fixture data, runs both placeholder models, writes scores, and serves the API
at <http://localhost:8000>. No database server, no containers, no credentials — the
database is a SQLite file at `.data/xfun.db`, and deleting it costs nothing.

For the web page, in a second terminal:

```bash
pnpm web:dev            # http://localhost:5173
```

## What it does

```
fixtures ──▶ ingestion ──▶ store ──▶ models ──▶ store ──▶ API ──▶ web
                                       │
                          scores are precomputed in batch;
                          the API never runs a model
```

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
| **A scoring model** | [`packages/scoring-contract/README.md`](packages/scoring-contract/README.md) | `packages/models/over-under-lean/` — copy its shape. A model is a pure function with no I/O. |
| **Data ingestion** | [`packages/ingestion/README.md`](packages/ingestion/README.md) | `fixture_file.py` — the adapter interface, and what a real provider replaces |
| **The API** | [`packages/api/README.md`](packages/api/README.md) | `contracts/openapi.yaml` — the contract is the source of truth; the API is validated against it |
| **The website** | [`packages/web/README.md`](packages/web/README.md) | `packages/web/src/App.tsx` — the whole page is one file |
| **Anything at all** | [`docs/architecture.md`](docs/architecture.md) | the four decisions that explain most of the code |

Everything CI runs, in order — worth running before you open a PR:

```bash
uv run python scripts/check_dependencies.py      # tier boundaries
uv run ruff check .
uv run pytest -q
uv run python scripts/pipeline.py                # end-to-end on fixtures
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
