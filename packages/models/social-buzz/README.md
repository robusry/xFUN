# social-buzz

⚠️ **PLACEHOLDER MODEL. Predicts nothing.**

Scores a match from two collected signals: how many times it was mentioned, and how
interested the home team's following appears to be.

## Why it exists

The other two models read canonical data — odds — which ingestion writes directly.
This one reads `signals.*`, which only exists because a collector produced it and
the platform joined it onto the match. It is what makes the collector tier reachable
in `scripts/demo.sh` rather than dormant, and it turns the `signals` blocks in the
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
`packages/collectors/fixture-signals/`. Nothing here has been validated against any
measure of whether a match was actually fun to watch — which is the project's
central unanswered question, not this model's to solve.

`raw_score` is deliberately unnormalised, on an arbitrary scale in the hundreds.
Models must not normalise; the platform percentile-ranks within a caller-chosen
cohort.

**Replaced by:** whichever change first builds a validated model over social
signals. Its absence from `packages/composition/recipes/default.yaml` is deliberate
— it contributes nothing to the composed score. See `docs/STUBS.md`.
