## Why

`add-live-schedule` made the matches real and stopped there, deliberately: it established
which matches exist and where a US viewer can watch them, and nothing a *model* reads. The
consequence is visible on every live run today — every match comes back with a recorded skip
reason and no score, because no registered model's declared features are satisfied by
anything in the store.

This change closes that gap with the smallest thing that can close it: one signal a collector
can really fetch, and one model that really consumes it. **Goals scored by each side in its
last five completed matches, summed.** It is a hypothesis about entertainment rather than a
validated formula — there is still no ground-truth label, and there will not be one before
`add-evaluation-harness` — but its inputs are real, its arithmetic is stated, and it produces
a score for a match a person can go and watch.

## What Changes

- **New collector** `recent-results`, keyed by team, providing
  `signals.form.<side>.goals_scored_last_5`. It reads the same source acquisition already
  reads — goal.com's daily fixtures pages — for **past** dates, walking backwards from the
  run until every team on the slate has five completed matches or a **120-day bound** is
  reached, whichever comes first.
- **New model** `recent-goals-total`: the home side's five-match goal total plus the away
  side's. Unnormalised, as the contract requires; typically in the range 5–30.
- Both sides are required. A team with fewer than five completed matches inside the bound
  carries **no value at all** rather than a partial sum, so the match is skipped with a
  recorded reason instead of being scored on a number that means something else.
- `packages/composition/recipes/default.yaml` points at `recent-goals-total` alone, replacing
  the two placeholder market models. Zone C: a config diff, revertible in one line.
- The offline path keeps working with no network. A capture tool writes **reduced past-date
  pages** into `contracts/fixtures/schedule/results/`, and `scripts/pipeline.py` replays them
  through the same collector when `--live` is absent, so `./scripts/demo.sh` on a fresh clone
  scores the fixture matches from real historical goals.

## Capabilities

### New Capabilities

- `recent-goal-form`: what recent goal form is as data — the five most recent **completed**
  matches in any competition, crossing seasons where necessary; what disqualifies a match
  from counting; the bounded lookback and what falls outside it; why fewer than five yields
  absence rather than a partial value; and how the model scores from the pair.

### Modified Capabilities

None. This change adds a source and a model, not a platform mechanism. Everything it relies
on — one collector per source, entity-keyed output joined onto matches, absence distinguished
from failure, skips recorded with a reason — is already specified in `data-collection` and
`scoring-contract`, and this is the first change to exercise those requirements against a
source that can actually be short of data.

## Impact

**Zones.** Zone B for `packages/collectors/recent-results/` and
`packages/models/recent-goals-total/`, both new behaviour and hence both specced. Zone A for
the golden fixtures added under `contracts/`, following the precedent set by the captured
schedule pages. Zone C for `packages/composition/recipes/default.yaml` and for `scripts/`.
No schema change: the `signals` region of `match-snapshot.json` is open by design, which is
exactly the case it was left open for.

**Code.** `packages/ingestion/schedule/` gains two public entry points — fetching one dated
page, and the client that knows this source's headers and its 403 policy — where today those
are private to `fetch_window`. No behaviour of acquisition changes. The new collector depends
on `xfun-ingestion` for those and for canonical id derivation; see design D8 for why sharing
beats duplicating here, and what would have to move if that dependency later grates.

**Cost of a live run.** Measured on 2026-08-04, which is close to the worst case — a
post-World-Cup August, with most European leagues between seasons: a 212-team slate needed
120 dates fetched to give **95%** of teams five completed matches, at ~134 MB and 120
requests. Mid-season the early stop reaches every team in roughly 35–45 dates. The live run
that closed this change out bore that out: 246 of 261 teams covered, and 149 of a 162-match
slate scored. Nothing
persists between runs yet, so every pipeline run pays this again; `add-collector-corpora` is
the change that ends that, and `refresh_after_seconds` is declared here against that day.

**External dependency.** None added. The same unofficial source, the same `robots.txt`
(`User-agent: * / Allow: /`, re-verified for this change), the same absence of any contract
or stability promise, and the same failure discipline: breakage raises rather than returning
an empty answer that would read as "these teams have not played".

**Placeholders resolved in `docs/STUBS.md`.** The **Ingestion** row's standing claim — that
nothing a model reads is real, so no model scores on a live run — stops being true. The
**Collectors** row gains its first collector that talks to a source rather than to a file;
the three fixture collectors stay, because they still exercise all three entity joins on a
clone with nothing configured.

**Not resolved.** Nothing here is validated against whether matches were entertaining, and
the model is honest about what it ignores: goals scored says nothing about how close the
match was, so a 5–0 procession outranks a 2–2 thriller. That is the same objection
`docs/STUBS.md` already records against `over-under-lean`, and it stays open until there is a
label to test against. `recent-goals-total` is therefore **not** marked a placeholder — its
inputs are real and its arithmetic is stated — but it is marked unvalidated, which every
model in this repository is.
