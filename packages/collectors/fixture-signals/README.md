# fixture-signals

**PLACEHOLDER.** Three collectors that read `contracts/fixtures/signals/*.json` from
disk and talk to nothing.

They exist to demonstrate all three entity joins end to end, on a clone with no
credentials configured:

| Collector | Keys by | Namespace | Joins onto |
|---|---|---|---|
| `fixture-match` | `match` | `match-buzz` | that match, by identity |
| `fixture-team` | `team` | `reddit` | the home and away sides of every match the team plays |
| `fixture-league` | `league` | `league-pulse` | every match in the league |

`fixture-team` returns data for one team only, on purpose — so a match carries
`signals.reddit.home.*` with no `away` counterpart, and a model requiring the away
side skips it with a recorded reason. Partial coverage is the routine case in this
system, not the exceptional one, and the fixtures should look like it.

## Why one package for three collectors

Because they share one placeholder source. Real collectors get a package each, for
the same reason models do: so a dependency one of them needs is not imposed on the
rest. Three packages wrapping the same `json.load` would be ceremony.

## What makes it a placeholder

The values are invented, and there is no HTTP client here. The fixture data exists so
the join, the resolution, and the run record can be exercised — not because anyone
believes Chelsea generate 46 posts.

**Not replaced by anything, and not going away.** `packages/collectors/recent-results/`
is a real collector against this same interface, so the interface no longer needs
proving. These three stay for the job a real collector cannot do: exercising all
three entity joins on a clone with nothing configured and no network. Retiring them
means having a real collector for each of the three keyings. See
[`docs/STUBS.md`](../../../docs/STUBS.md).
