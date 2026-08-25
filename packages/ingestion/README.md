# ingestion

**Not a placeholder.** Three jobs, all narrower than this package used to have:

1. **Schedule acquisition** — which matches exist, and who carries them in the US.
2. **Slate assembly** — deciding which matches a collection run is about.
3. **Canonical entity writing** — turning match payloads into rows.

Two paths in. `schedule/` acquires real upcoming matches and their US broadcasters
from goal.com — this is one of exactly two tiers permitted to touch the network, and
it runs *before* the slate because it produces what the slate is made of.
`fixture_payloads()` loads `contracts/fixtures/snapshots/*.json` instead, and stays
the default so a fresh clone runs with no network, no daemon and no credentials.

The provider is real but it is not a vendor: goal.com publishes no API and no
stability promise, so the parser is written to break loudly rather than to return an
empty window. `rights/us-broadcast-rights.yaml` is consulted only where the source
names no provider, and availability may still answer `unknown` — a confidently wrong
broadcaster is the failure a viewer notices immediately. See
[docs/STUBS.md](../../docs/STUBS.md) for what that source can and cannot be trusted
for.

## What moved out

`SourceAdapter` is gone. It let several sources be plugged in, but each yielded
whole match payloads, so three models wanting one source had no way to share a
fetch. That job now belongs to `packages/collectors/`, where a collector receives
the whole slate, chooses its own fan-out, and keys its output by match, team, or
league for the platform to join on.

What is left here is the part collectors do not do: identity, kickoff, teams,
league, and the canonical odds/form/table blocks.

## The slate rule

Two rules, because the two paths know different things. The live path uses
**`us-watchable`**: kickoff within ten days, and a known US broadcaster. The fixture
path carries no availability, so it keeps **`league-allowlist`** within a time window.

Either way the rule in force is **recorded on the slate** rather than assumed, so a
run stays interpretable after the rule changes. That matters more than it looks: a
team-keyed collector polls a different set of sources for a different set of teams,
so its output is only meaningful alongside the slate that produced it.

The ten-day window is not configurable on purpose. Beyond roughly two weeks a missing
broadcaster usually means the match has not been assigned one yet rather than that
nobody carries it, so a wider window would silently drop matches for a reason
unrelated to watchability. The slate going thin between seasons is correct, not
broken.

## Idempotence

A scheduled job will fire twice eventually. Entity writes are upserts on natural
keys, so repeated runs converge rather than duplicate.
