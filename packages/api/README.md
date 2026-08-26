# api

**Real, not placeholder.**

Read-only FastAPI service. Reads precomputed scores; applies calibration and
composition, both of which are arithmetic over stored rows.

```bash
uv run uvicorn xfun_api:app --port 8000        # http://localhost:8000/docs
uv run uvicorn xfun_api:app --port 8000 --reload   # while editing this package
```

`uv run` matters unless the virtualenv is already active — a bare `uvicorn` will
either be missing or be the wrong one.

It reads whatever is in `.data/xfun.db` and never writes. Against an empty database
every endpoint returns 500 on the first request — the schema is created by the
pipeline's migrations, so there is no `model_registry` table to read yet. Run
`uv run python scripts/pipeline.py` first to acquire and score something; that needs
network access to the schedule source.

Port 8000 is not arbitrary: the web page defaults to `http://localhost:8000`, and
this service allows cross-origin requests from `http://localhost:5173` alone. Moving
either without the other breaks the page in the browser and nowhere else. See
`packages/web/README.md`.

## It never runs a model

No model package appears in this package's dependencies or imports, and
`scripts/check_dependencies.py` fails CI if one ever does. Everything the API
knows about models comes from the `model_registry` table.

That is what lets the API keep serving when every model is broken — and what keeps
modelling work from becoming an availability risk.

## The contract is the source of truth

`contracts/openapi.yaml` defines this API; the implementation is validated
*against* it. FastAPI's idiom is the reverse — generating OpenAPI from code — and
getting it backwards would quietly invert the contract-first design.

## Every response states its cohort and alias

A calibrated score without its cohort is uninterpretable, and an alias can be
repointed. A client that does not record what it asked for cannot reproduce what
it got.

## 501, not a wrong answer

Unimplemented calibration cohorts and composition policies return 501 with a
detail naming the change that implements them. Silently falling back to a
different cohort would return a plausible number computed against the wrong
population.
