# composition

**Mechanism is real; one of three policies is implemented.**

## Recipes are configuration, not code

`recipes/*.yaml` names models, weights, a missing-model policy, and a minimum
count. Changing the blend is a config diff any team member can read, review, and
revert — deliberately, because how models are combined is expected to change
repeatedly and the cost of one change must be near zero.

Recomposing the entire history runs no models. It is arithmetic over rows that
already exist.

## Zone A vs Zone C runs through this package

```
src/       ZONE A — the mechanism. specs required.
recipes/   ZONE C — the values. a config diff.
```

Adding a policy changes what a composed score means. Changing a weight does not.

## Missing-model policy is required, never defaulted

Coverage gaps are routine: of seven fixture matches, one is scored by a single
model. Leaving the policy implicit would mean each recipe author resolved it
differently.

⚠️ Only `renormalize` is implemented. `require-all` and `fallback` raise
`PolicyNotImplemented`; the API returns 501. See
[docs/STUBS.md](../../docs/STUBS.md).

## Aliases

Consumers address `default`, never `default-v1`. Repointing changes what everyone
receives with no client change — the same indirection as a Docker tag. An alias
can also resolve to a single model, which makes "expose one model" and "expose a
blend" the same code path.
