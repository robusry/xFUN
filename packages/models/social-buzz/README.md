# social-buzz

⚠️ **PLACEHOLDER MODEL. Predicts nothing.**

> **Not registered by anything that runs.** `tests/harness.py` registers it, and only
> there. It is the one model reading `signals.*`, and the only collectors providing
> those paths are `fixture-signals`, which invent their values — so a real run
> registering this model would be scoring matches from fabricated input. The registry
> also fails a model whose declared paths nothing provides, which is why this model and
> those collectors move together or not at all.
>
> **Do not delete it as dead code.** With `fixture-signals` it is what keeps the
> signal-reading path exercised end to end. See `make-pipeline-live-only` design D6.

Scores a match from two collected signals: how many times it was mentioned, and how
interested the home team's following appears to be.

## Why it exists

Every other model reads canonical data that ingestion writes directly — odds for the
two market models, recent results for `recent-goals-total`. This one alone reads
`signals.*`, which exists only because a collector produced it and
the platform joined it onto the match. It is what makes the collector tier reachable
in the end-to-end check rather than dormant, and it turns the `signals` blocks in the
golden snapshot fixtures into something a run actually reproduces.

It also demonstrates the point of the whole tier: **this model has no idea a
collector exists.** It declares two dotted paths. Whether they were fetched by one
collector or three, from Reddit or a CSV, is not its concern and can change without
touching it.

## What makes it a placeholder

The arithmetic is invented. `mentions × home excitement` is not a theory of
entertainment — a heavily-discussed match between two dull teams outranks a quiet
thriller, and the away side's following is ignored entirely because the fixture data
deliberately covers only one side.

More to the point, the underlying signals are themselves invented by
`packages/collectors/fixture-signals/`. No model here is validated against a measure
of whether a match was actually fun to watch, by decision rather than by omission
(see [docs/STUBS.md](../../../docs/STUBS.md)); what singles this one out is that its
inputs are made up as well.

`raw_score` is deliberately unnormalised, on an arbitrary scale in the hundreds.
Models must not normalise; the platform percentile-ranks within a caller-chosen
cohort.

**Replaced by:** whichever change first builds a model over real social
signals. Its absence from `packages/composition/recipes/default.yaml` is deliberate
— it contributes nothing to the composed score. See `docs/STUBS.md`.
