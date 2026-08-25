# odds-spread

⚠️ **PLACEHOLDER MODEL. Predicts nothing.**

Returns the normalised Shannon entropy of the vig-stripped implied
probabilities of home, draw, and away.

## Why it is a placeholder

High entropy means the market cannot separate the sides, which is a reasonable
proxy for a competitive match. But it ignores goals entirely, so it will rank a
tense 0-0 above a 4-3 thriller.

It has never been validated against any measure of whether matches were actually
enjoyable to watch, and no model here is expected to be — see
[docs/STUBS.md](../../../docs/STUBS.md). What sinks this one is not the missing
validation but the reasoning above, which the team can judge without a label.

**Replaced by:** `add-market-baseline-model`, which folds goal expectancy and
competitiveness into one model.

## Required features

```
odds.home_price
odds.draw_price
odds.away_price
```

Five of the seven fixture matches provide these. One fixture has a total line
but no moneyline **on purpose**, so it is scored by `over-under-lean` and
skipped here — exercising partial coverage and the `renormalize` policy.
