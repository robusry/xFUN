## Context

Every model in the repository predicts nothing, and on a live run none of them even runs:
`add-live-schedule` made matches and broadcasters real and left everything a model reads on
fixture data. `docs/STUBS.md` names the tier that is supposed to close that gap — collectors,
"since model-facing data is what that tier exists to fetch" — but no collector talks to a
source yet. All three read files.

This design takes the narrowest path to a model that works end to end on real data. The
formula is deliberately trivial and was specified by the team: **for each side, the goals it
scored in its last five completed matches, in any competition, going back into previous
seasons if that is what five matches requires; the score is the two totals added together.**

Nothing here claims the formula is good. It cannot be evaluated — there is no ground-truth
label for "entertaining", which `openspec/config.yaml` records as the most consequential open
question in the project. What can be judged is whether the number is really what it says it
is, and most of this design is about that: which matches count, what happens when there are
not five of them, and how a team on this project's slate is matched to a result on somebody
else's page.

The measurements quoted below were taken on 2026-08-04 against a 212-team slate derived from
a five-date window under the live `us-watchable` rule, and over 140 consecutive past dates
covering 6,673 matches. They are recorded because the interesting numbers are seasonal, and a
future reader sampling in March will otherwise conclude the off-season figures were pessimism.

## Goals / Non-Goals

**Goals:**

- One model whose every input is real, which scores real upcoming matches on a live run.
- A signal whose definition is exact enough to be wrong in public: five completed matches,
  not "recent form" loosely construed.
- Absence where the data is short, never a partial value dressed as a complete one.
- The default `./scripts/demo.sh` still runs with no network, and still exercises the model.

**Non-Goals:**

- Validation. No label exists; `add-evaluation-harness` is the change that makes "is this
  model any good" an answerable question, and it is unblocked by this one.
- Goals conceded, xG, shots, or anything else the same pages carry. A leaf nothing declares
  is a claim with no consumer; the team can add one when a model wants it.
- Persistence of collected signals between runs. `add-collector-corpora`, unchanged.
- Liga MX. Its matches still never reach the slate, for the club-level rights reason recorded
  in `docs/STUBS.md`; nothing here changes that and nothing here should be read as trying to.

## Decisions

### D1. The results come from the source already in use, not a second provider

Past-dated goal.com fixtures pages carry the final score and a status in the same page state
acquisition already parses for competition and TV providers. Verified across 140 dates: a
finished match carries `status: "RESULT"` and `score: {teamA, teamB}`.

The decisive argument is **identity, not coverage**. Canonical team ids are slugs derived from
this source's team names (D9 of `add-live-schedule`), and the collector's output is joined to
the slate on exactly those ids. A second provider means cross-source entity resolution — its
"Man Utd" against our `manchester-united`, and the River Plate collision D9 already accepts as
a known cost — where a mismatch does not fail, it silently attributes another club's goals.
One source, one vocabulary, an exact join.

*Rejected:* football-data.org. Its free tier is twelve competitions — Premier League,
Championship, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Brasileirão,
Champions League, European Championship, World Cup. A US-watchable slate is not mostly those:
the measured 212-team slate was dominated by MLS, the English National League and EFL, Leagues
Cup, and CONCACAF competitions, none of which it carries. It also requires an API token, and
this project has never required a credential to run anything.

*Cost accepted:* results are read from the **fragile** half of the page. Design D5 of
`add-live-schedule` put identity and kickoff on the durable schema.org half deliberately, but
`SportsEvent` blocks carry no score, so there is no durable half to prefer here. When the
source is redesigned this breaks, and it breaks loudly — the existing `ScheduleParseError`
path already distinguishes "the page changed shape" from "there was nothing on".

### D2. Fan out over dates, not over teams

One daily page answers for every team at once: ~0.85 MB, one request, every competition the
source lists worldwide. Fanning out per team would be ~400 requests for a ten-day slate, plus
a discovery pass, because a team page is addressed by the **source's** team id, which this
project deliberately does not store.

*Rejected:* the per-team pages at `/en-us/team/{slug}/fixtures-results/{id}`, which look ideal
and are not. Their match list is not the team's fixture list: AFC Fylde's carries seven
completed matches, all of them FA Cup and FA Trophy ties, with every National League match
missing; Altrincham's carries four, same pattern; Barrow's five, same pattern. A last-five
built from those pages would be five cup ties spread over four months, presented as recent
form, for entire leagues at a time. A confidently wrong number is the failure mode this
project rejects everywhere else it appears.

*Cost accepted:* bytes scale with the **lookback**, not with the slate, so a thin slate in a
quiet week still pays for a deep scan. The early stop in D3 is what bounds that in practice.

### D3. The lookback is bounded at 120 days, and the scan stops as soon as it can

The collector walks backwards one date at a time from the run, and stops at the first of: every
team on the slate has five completed matches, or 120 dates have been read.

Measured on 2026-08-04 — close to the worst case, a post-World-Cup August with most European
leagues between seasons — for the 212-team slate:

| days back | teams with five | bytes |
|---|---|---|
| 30 | 29% | 26 MB |
| 45 | 47% | 37 MB |
| 70 | 51% | 57 MB |
| 90 | 77% | 86 MB |
| 105 | 85% | 110 MB |
| **120** | **95%** | **134 MB** |
| 140 | 98% | 164 MB |

The curve is flat between days 45 and 70 and then climbs steeply, because that is where the
scan reaches back past the World Cup break and the European season ends. That shape is the
argument for 120 rather than the 90 that looks natural: stopping at 90 discards a fifth of the
slate for a saving of 48 MB, and the teams it discards are the ones a US viewer is most likely
to be watching in August. Mid-season the early stop reaches every team in roughly 35–45 dates
and the bound never binds.

*Rejected:* no bound at all, scanning until every team has five. Unbounded work against a
third party for a signal that decays: the five most recent matches of a club that last played
in April describe last season's squad.

*Cost accepted:* in the deep off-season some teams get no value and their matches go unscored
— 5% of the measured slate, and the five that remained short after 140 days were minor CONCACAF
clubs. That is the partial-coverage path doing its job on real data, and it is visible in the
run record rather than inferred.

### D4. "Completed" means the source says `RESULT`, not that a score is present

Over the 6,673 sampled matches, 62 `POSTPONED` entries and 33 `CANCELLED` entries carry a
score, and it is `0-0`. Ten `LIVE` entries carry a running score. Filtering on "a score is
present" would count a postponement as a goalless draw, and a match kicking off as whatever it
happened to be at the moment of the fetch.

Neither error announces itself. A team with two postponements in its span would show a total
depressed by two matches' worth of goals, and the number would still look entirely plausible.

*Cost accepted:* a status vocabulary this project does not own is now load-bearing. If the
source introduces a fourth terminal status, matches in it are silently not counted. The scan
therefore counts only what it recognises rather than excluding what it recognises as bad, so a
new status defaults to "not counted" — a short team, and an absent value — rather than to
"counted", which would be a wrong number.

### D5. Fewer than five completed matches produces no value at all

Not four matches' worth of goals, not an average scaled up. Nothing.

The reason is in the contract: `score()` has no way to decline. `packages/scoring-contract/
src/xfun_contract/requirements.py` records that a requirement whose coverage the *model*
decides is anticipated and not yet built. So a model handed three matches must return a
number, and that number — a sum over three — is indistinguishable downstream from a genuinely
low-scoring team's sum over five. It would be percentile-ranked against five-match sums and
land near the bottom of every cohort for a reason that has nothing to do with the team.

Absence routes the match to the skip path instead, where the reason is recorded and the API
returns the match with no score and an explanation. That is the system's designed answer to
exactly this, and this is the first collector that can actually trigger it from data rather
than from a fixture file engineered to.

*Rejected:* providing `goals_scored` alongside a `matches_counted` leaf and letting each model
decide. It moves the decision to a place that cannot act on it, and the first model to forget
to check `matches_counted` produces the same silent distortion with more ceremony.

### D6. The value is per team as of the run, not per match as of kickoff

A team-keyed collector produces one value per team, joined onto both sides of every match that
team plays. "Its last five matches" is therefore measured from the collection run.

The alternative reading — for each match, the five completed before *that* kickoff — is what a
match-keyed collector would compute, and for this slate it returns the same answer: every match
on the slate is in the future, every counted match is complete, so the two definitions differ
only when a team plays twice inside the same window. For the second of those two, the honest
per-kickoff answer would include the first, which has not been played yet.

*Cost accepted:* on a ten-day slate a team playing twice carries the same value for both, and
the later match's value is stale by one fixture. Recomputing per kickoff cannot fix that, since
the missing result does not exist at collection time; only re-running collection after the
first match is played does, which is what a scheduled pipeline already does.

### D7. The path is `signals.form.<side>.goals_scored_last_5`

A namespace is a subject area, never a producer — `form` rather than `goal-com` or
`recent-results`. That is what lets the producer be replaced without every model that declares
the path breaking, which is the whole reason the indirection exists.

*Rejected:* writing this into the canonical `form` block that `match-snapshot.json` already
defines. Two reasons, and the second is the real one. Canonical entities are written by
acquisition, which runs before the slate exists — putting model-facing history there would
push a fetch of five matches per team into the tier that is supposed to establish only which
matches exist. And `team_form` is shaped as `matches` plus `goals_for_avg`, an average over an
unspecified count, which cannot express "the sum over exactly five" without a reader assuming
the multiplication is safe.

*Cost accepted:* a snapshot now carries two things called form — `form.home.*`, still empty on
every path, and `signals.form.home.*`, real. Whichever change first fills the canonical block
should expect to argue about the collision.

### D8. The collector imports the schedule source's page reading and id derivation

`xfun_ingestion.schedule` gains two public entry points — a client carrying this source's
headers and its 403 policy, and a fetch of one dated page — and the collector uses those plus
`canonical.team_id`. Collectors are purity-exempt and nothing forbids the import; the rule that
keeps the tier boundary honest points at who may import a collector, not at what one may
import.

*Rejected:* a second HTTP client and a second copy of `slugify` inside the collector. The slug
rule is not a detail: the join between this collector's output and the slate is by canonical
team id, so if the two derivations ever disagree by one character, the value silently lands on
no team and the match is skipped as though the team had not played. And the 403 handling
carries a policy — "the source may have started blocking automated access; do not work around
it" — which should have one home rather than two that can drift apart.

*Cost accepted:* a collector package now depends on `xfun-ingestion`. If that grates later, the
thing to extract is "how to read a goal.com page and derive an id from a name", which both
tiers would then import. Not done now because one shared consumer does not earn a package.

### D9. The offline path replays captured pages through the same collector

`scripts/capture_results_fixture.py` writes reduced past-date pages — real bytes from the
source, trimmed to matches involving a named set of teams — into
`contracts/fixtures/schedule/results/`. The pipeline injects a file-backed page source and a
fixed `as_of` when `--live` is absent, so the default demo runs the real scan over real
historical results with no network.

*Rejected:* registering the collector and the model only under `--live`. It sounds simpler and
it is a trap: a model declaring a signal path that no registered collector provides is a
registration error, by design, so the model could not be registered at all on the default path.
`./scripts/demo.sh` and the end-to-end pipeline run in CI would never touch either package, and
the only coverage would be unit tests.

*Rejected:* a fixture file of collected values, in the shape of
`contracts/fixtures/signals/*.json`. That is what the three placeholder collectors do, and it
would leave the scan — the only interesting logic here — unexercised outside unit tests.

*Cost accepted:* roughly 35 more fixture files, small ones, and a second capture tool beside
`capture_schedule_fixture.py`. Both tools reduce a third-party response to a subset of its own
bytes; `contracts/README.md` already says what that means and why those files may be refreshed
wholesale.

### D10. `default.yaml` points at `recent-goals-total` alone

The two market models score nothing on a live run and are recorded as predicting nothing on any
run. Blending them with the one model that has real inputs would produce a composed number
whose provenance is mostly placeholder.

*Cost accepted:* the fixture demo stops exercising a multi-model blend. Composition still runs
— alias resolution, the `renormalize` policy, and the minimum-count check are all on the same
path for one model as for three — but the specific case of two models' calibrated scores being
weighted together is now covered only by the composition tests. This is a Zone C value change:
one line restores the blend, and the team decides by review, not by this design.

## Risks / Trade-offs

- **The number is not fun.** Goals scored ignores how close the match was. A 5–0 procession
  between two free-scoring sides outranks a 2–2 thriller between two mean ones. This is the
  same objection `docs/STUBS.md` records against `over-under-lean`, and it is unanswerable
  until there is a label. What is different here is that the inputs are real, so the model can
  be wrong in a way somebody can check by watching.
- **Home and away are added, not weighted.** A side that scores five per game and a side that
  scores none sum to the same total as two sides scoring 2.5 each, and the second match is
  probably the better watch. Left alone deliberately: the team specified the sum, and a
  weighting invented here would be a second unvalidated hypothesis smuggled in under the first.
- **A renamed club becomes a new team.** Already accepted in D9 of `add-live-schedule` for the
  canonical entity; it bites harder here, because a club renamed mid-scan splits its five
  matches across two slugs and both end up short. Rare, and it produces absence rather than a
  wrong number.
- **Cost repeats every run.** 120 requests and ~134 MB in the worst case, with nothing cached
  between runs. Acceptable for a batch pipeline nobody runs in a loop; unacceptable as a
  pattern if a second collector copies it. `refresh_after_seconds` is declared at six hours so
  that the cadence this source deserves is already written down when `add-collector-corpora`
  starts enforcing it.

## Migration Plan

None. Nothing stored changes shape, no migration is added, and the append-only score store
takes rows from a new `model_id` the way it takes rows from any other. A run made before this
change stays queryable and keeps meaning exactly what it meant.

## Open Questions

- Should the same collector provide `goals_conceded_last_5`? It is free — the same pages, the
  same scan — and it is the obvious input to a model that wants to say something about
  competitiveness rather than volume. Not added here because nothing declares it, and a leaf
  with no consumer is a claim nobody checks. The first model that wants it should add it.
- Is five the right number? It is what was specified, and it is conventional. Ten would halve
  the noise and double the staleness. Answerable only once there is something to evaluate
  against, which is `add-evaluation-harness` again.
