# Collectors

**The one tier permitted to reach outside the process during a scoring run.**

Everywhere else in this repository, external access is a defect. Models are pure by
contract and CI fails a model package that declares an HTTP client. That constraint
is what makes a score reproducible — and it is only affordable because collection
happens here instead.

A collector is the inverse of a model:

| | Model | Collector |
|---|---|---|
| Network, credentials, third-party clients | forbidden | expected |
| Input | one `MatchSnapshot` | the whole `Slate` |
| Output | one `raw_score` per match | values keyed by match, team, or league |
| Failure | should not happen | routine, and recorded as distinct from absence |

## Why the slate arrives whole

A collector decides its own fan-out. An odds source is queried per match; a social
source is read per team subreddit; a league table is one request for twenty matches.
Handing a collector one match at a time would force twenty requests where one would
do, and push batching into every collector as a private cache.

## Why output is not keyed by match

A collector that reads team subreddits keys its output by team, and the platform
joins it onto the home and away sides mechanically. Requiring per-match output would
force every collector to solve attribution — and attribution is a judgement call, not
a mechanical one. One model wants strict match-thread matching; another wants loose
team-mention sentiment. A collector that picks one forecloses the other for every
consumer, which is the opposite of why this tier is shared.

## Absence is not failure

"This match has no thread" is a permanent, correct answer. "The API returned 503"
establishes nothing. Both leave an identical hole in the snapshot, so a collector
that conflates them makes a week-long outage look like a source with nothing to say.
Return an empty entry for the first; return `CollectionResult.unavailable(reason)`
for the second.

## Adding a collector

1. A directory here, with its own `pyproject.toml` declaring its own dependencies. The
   root workspace globs `packages/collectors/*`, so there is no list to add to.
2. Implement `xfun_contract.Collector`: `collector_id`, `namespace`, `entity_kind`,
   `provides`, `refresh_after_seconds`, and `collect(slate)`.
3. Register it in `scripts/pipeline.py`, which is the only place that knows collectors
   exist.

The registry composes full paths from your namespace and leaves — a team-keyed
collector claiming `excitement` provides both `signals.<ns>.home.excitement` and
`signals.<ns>.away.excitement`. **Exactly one producer may claim a path**; a second
claim fails registration rather than silently winning.

A namespace is a subject area, not your identity. Several collectors may contribute
to one, and a signal may change producer without its path moving — which is what
keeps the path stable for the models that declare it.

## What is real here and what is not

`recent-results/` reads a source: goals scored in each team's last five completed
matches, from dated schedule pages. It is the collector the `signals.*` machinery was
built for, and the reason a live run produces scores at all.

`fixture-signals/` is three placeholder collectors that read files and talk to nothing.
They stay, because they exercise all three entity joins — match, team, and league — on a
clone with nothing configured, and because `fixture-team` returns one team on purpose so
the partial-coverage path is real rather than theoretical. See `docs/STUBS.md`.
