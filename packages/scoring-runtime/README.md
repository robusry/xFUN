# scoring-runtime

**Real, not placeholder** — except calibration cohorts, which are partly stubbed.

Everything that operates on models without knowing what any of them do: the
registry, feature assembly, the model runner, and calibration.

## Registry

Registration is where declarations meet reality. A model declaring a feature the
snapshot schema does not define is rejected here — a typo in `required_features`
should be a loud registration error, not a model that quietly never scores.

## Runner

Fans registered models out over snapshots. Two properties matter:

- **Order independence.** Models never read each other, so execution order cannot
  change results. A test asserts it.
- **Skips are recorded, not swallowed.** A model whose features are unavailable
  produces no score *and a reason*. Silence would be indistinguishable from a
  model that ran and found nothing.

## Calibration

Percentile-ranks raw scores to 0–100 within a cohort, per `(model_id,
model_version)` — a model is only ever compared against itself.

**The cohort is a request parameter**, which is why calibrated scores are never
stored. `window` answers "best of what's on this weekend"; `season` answers "best
of the season". Both are legitimate and they disagree.

⚠️ Only `window` is implemented. The others raise `CohortNotImplemented` and the
API returns 501. See [docs/STUBS.md](../../docs/STUBS.md).
