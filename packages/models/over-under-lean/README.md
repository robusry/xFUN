# over-under-lean

⚠️ **PLACEHOLDER MODEL. Predicts nothing.**

Returns the market's over/under goals line as the score. That is the entire model.

## Why it is a placeholder

The over/under line genuinely is the market's expected goal total, and goals
correlate with entertainment. But it ignores competitiveness entirely, so it
will happily rank a 4-0 procession above a tense 1-1.

It has never been validated against any measure of whether matches were actually
enjoyable to watch — there is no ground-truth label in this repository yet.

**Replaced by:** `add-market-baseline-model`, which folds goal expectancy and
competitiveness into one validated model. See [docs/STUBS.md](../../../docs/STUBS.md).

## Required features

```
odds.total_line
```

Six of the seven fixture matches provide this. The one that does not has no
odds at all and is skipped.
