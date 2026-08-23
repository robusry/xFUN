# recent-results

**The first collector here that reads a source rather than a file.**

Provides one leaf, keyed by team:

```
signals.form.home.goals_scored_last_5
signals.form.away.goals_scored_last_5
```

Goals a team scored in its **five most recent completed matches**, in any competition,
crossing into previous seasons when five require it.

## How it fetches

goal.com's dated fixture pages — the same pages the schedule source reads for upcoming
matches, read backwards from the day of the run. One page answers for every team in the
world at once, which is why this fans out over **dates** rather than over the slate's
teams: a ten-day slate carries roughly 400 teams and one request per team would be 400
requests, against roughly 40 for a mid-season scan by date.

The scan stops at the first of:

- every team on the slate has five completed matches, or
- **120 days** before the run.

The bound is measured, not chosen for roundness. See design D3 of
`add-recent-goals-model` for the coverage curve behind it; the short version is that
95% of an August slate is reachable at 120 days and only 51% at 70, because that is
where the scan reaches back past the previous European season.

## Three ways this could report a wrong number, and does not

- **A postponed match carries a 0–0 score on this source.** Counting "any match with a
  score" would treat a postponement as a goalless draw. Only matches the source reports
  as `RESULT` count, matched positively — so a status nobody here has seen leaves a team
  short rather than entering a total.
- **Fewer than five matches yields no value at all**, not a partial sum. A model cannot
  decline to score, so a sum over three would be ranked against sums over five and land
  at the bottom of the cohort for a reason unrelated to the team.
- **A fetch failure discards the whole run.** Values already gathered are correct, but
  reporting them would record every other team as "asked, and had nothing" — a claim a
  collector that just failed cannot make.

## How a team on the slate is recognised

By reducing the **name** on both sides with the same derivation that mints canonical
ids, then emitting under the slate's own team id. Not by the slate's id directly: the
golden fixture slate calls Arsenal `ars`, and matching on that would find nothing.

Two consequences worth knowing before you debug a missing value:

- A club the source names differently is invisible. The golden snapshots call Inter
  `Internazionale` and the source calls them `Inter`, so that fixture match comes back
  unscored. That is deliberate — see the tests, which assert it stays a gap rather than
  becoming a value found by a looser match.
- Two slate teams whose names reduce to one key are both dropped. Both River Plates are
  `river-plate`, and attributing one club's goals to the other is worse than a gap.

## Running it without a network

`collect` takes an injected `PageSource` and an `as_of` date. `CapturedPages` reads
reduced golden captures from `contracts/fixtures/schedule/results/`, which is what
`./scripts/demo.sh` uses when `--live` is absent, and what every test here uses.
`LivePages` is the network one.

## Cost

Roughly 0.85 MB and one request per date. A mid-season run is ~40 requests; an
off-season one walks the full bound at ~120 requests and ~134 MB. Nothing persists
between runs yet, so every run pays it again — `refresh_after_seconds` is declared at
six hours against the day `add-collector-corpora` starts enforcing it.
