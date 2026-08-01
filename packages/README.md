# packages/

Every tier of the system. Each package declares its own dependencies, so a
dependency needed by one is never imposed on the others.

```
scoring-contract/    the model interface + shared types.       Python
scoring-runtime/     registry, feature assembly, calibration.  Python
store/               canonical entities + append-only scores.  Python
models/<model-id>/   one independently owned package per model. Python
composition/         recipes and composition logic.            Python
evaluation/          labels, backtests, leaderboard.           Python  (not yet built)
ingestion/           per-source data adapters.                 Python
api/                 read-only public API (FastAPI).           Python
web/                 the website.                              TypeScript
mobile/              future mobile app.                        TypeScript (slot only)
clients/             generated API clients (ts, py).           generated
```

## The dependency rules

These are enforced in CI, not left to good intentions:

- **Models depend only on `scoring-contract/`.** Never on each other, never on the
  database, never on the network. A model is a pure function.
- **The API depends on no model package.** It reads precomputed scores from the
  store; it never executes a model during a request.
- **Nothing imports across a tier boundary except through `contracts/`.**

## Adding a model

Should touch exactly two things: a new directory here and a registry entry. If it
touches the API, the web app, or another model, a boundary has leaked.

## Real vs placeholder

This repository is currently a walking skeleton — several packages are deliberately
minimal. Each package README says which it is, and `docs/STUBS.md` lists every
placeholder alongside the change that replaces it.
