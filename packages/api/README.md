# api

**Real, not placeholder** — over placeholder data.

Read-only FastAPI service. Reads precomputed scores; applies calibration and
composition, both of which are arithmetic over stored rows.

    uvicorn xfun_api:app --reload

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
