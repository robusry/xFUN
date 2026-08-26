# fixture-signals

**PLACEHOLDER, AND TEST-ONLY.** Three collectors that read
`contracts/fixtures/signals/*.json` from disk and talk to nothing. The values are
invented.

> **Nothing that runs registers these.** `tests/harness.py` is their only caller.
> A corpus row does not record whether its value was collected or fabricated, so once
> both are written by the same run nothing downstream — no snapshot, no score, no run
> record — can tell them apart, and the distinction cannot be recovered afterwards.
> That is why they are kept away from the pipeline rather than merely marked.
>
> **Do not delete them as dead code.** They are what exercises all three entity joins,
> and `fixture-team` returns one team on purpose so a match carries
> `signals.reddit.home.*` with no `away` counterpart. Nothing else in this repository
> produces that shape, so removing them silently reduces what the end-to-end check
> covers. See `make-pipeline-live-only` design D6.

They demonstrate all three entity joins end to end:

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
