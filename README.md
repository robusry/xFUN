# xFUN

Predicting which soccer matches will be entertaining to watch, for viewers in the US,
across leagues people actually follow.

> **Status: walking skeleton.** Every tier exists and is connected end to end, running
> on fixture data. The components are deliberately minimal — this repository is
> currently something to *read and understand*, not something that works. See
> [`docs/STUBS.md`](docs/STUBS.md) for what is placeholder and what replaces it.

## Quickstart

```bash
./scripts/demo.sh
```

Seeds fixture data, runs both placeholder models, writes scores, and serves the API
at <http://localhost:8000>. No database server, no containers, no credentials — the
database is a SQLite file at `.data/xfun.db`.

For the web page:

```bash
pnpm install && pnpm web:dev
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

## Setup

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.12 | |
| [uv](https://docs.astral.sh/uv/) | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node | ≥ 20 | |
| [pnpm](https://pnpm.io/) | 9.x | `corepack enable && corepack prepare pnpm@9.12.0 --activate` |
| OpenSpec | **pinned, see `.openspec-version`** | `npm install -g @fission-ai/openspec@1.6.0` |

```bash
uv sync --all-packages   # Python workspace — all members, not just the root
pnpm install             # TypeScript workspace
```

Both dependency trees are pinned — `uv.lock` and `pnpm-lock.yaml` are committed, and
CI installs with `--locked` / `--frozen-lockfile` so a stale lock fails rather than
silently resolving something different. After changing a dependency, run `uv lock`
and commit the result.

**The OpenSpec version is pinned deliberately.** Artifact templates, workflow schemas,
and validation rules ship with the CLI rather than this repository, so contributors on
different versions generate divergent artifacts. CI verifies the version in use matches
`.openspec-version`.

## Contributing

Read [`docs/workflow.md`](docs/workflow.md) and [`docs/zones.md`](docs/zones.md) before
your first change. In short:

- Create a branch **before** touching any file, including before `openspec new change`
- Not every change needs a spec — `docs/zones.md` says which do
- Open the pull request when the change is **complete**: artifacts, implementation, and
  the archive commit
- Conventional Commits, squash-merge by convention

## Documentation

Everything is in [`docs/`](docs/README.md). Behavioral requirements live in
`openspec/specs/` and are normative; the docs explain and orient.
