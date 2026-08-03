## Context

Ingestion reads eight invented matches from `contracts/fixtures/snapshots/`. The slate rule
is a league allowlist, recorded as a placeholder because the product scope — matches
watchable in the US — was not computable while broadcast availability always answered
`unknown`. The API hardcodes that answer at `main.py:88`.

`add-collector-tier` settled how data reaches a model *after* the set of matches is known:
collectors receive the whole slate, key their output by entity, and the platform joins it
on. It said nothing about where the set of matches comes from, because the fixture source
made that question moot.

It is no longer moot, and the two halves turn out to be structurally different. A collector
cannot produce the schedule: `Collector.collect(slate: Slate) -> CollectionResult` takes a
slate as input, `assemble_slate()` reads the `match` table, and `EntityKind` enumerates
joins onto matches that already exist. Nothing in that interface can bring a match into
being. Acquisition is therefore a distinct step that runs before a slate exists, and this
design is mostly about admitting that honestly rather than forcing it into the collector
shape.

Six candidate sources were surveyed. The results are recorded under D2 because the
constraint that eliminated most of them — broadcast listings are a licensed product, and
almost everyone who has them refuses automated collection — is not obvious, and a future
reader who does not know it will re-run the same search.

## Goals / Non-Goals

**Goals:**

- The slate is real upcoming matches, with a US provider named for each.
- `us-watchable` becomes the recorded selection rule, replacing `league-allowlist`.
- Availability is persisted and served, with `unknown` still reachable and still honest.
- A fresh clone runs `./scripts/demo.sh` with no credentials and no network.
- Source failure is distinguishable from "no matches", the way collector failure already is.

**Non-Goals:**

- Anything a model consumes. Acquisition establishes which matches exist and where they can
  be watched; what a model reads about them is a separate tier's concern, and this design
  takes no position on which. Because no model input becomes real here, no model scores —
  this change makes the schedule real, not the rankings.
- Signal collectors against live sources. Unchanged, still on fixture files.
- Persisting snapshots. `add-score-provenance`.
- A provider selection that is durable. goal.com is the best option available today, not a
  vendor commitment; D2 records what would displace it.
- Personalised availability — a viewer's actual subscriptions. This answers "who carries
  it", not "can *you* watch it".

## Decisions

### D1. The schedule source is a second external-access tier, not a collector

External access is confined to two tiers, distinguished by when they run relative to the
slate. The **schedule source** runs before one exists and produces it. **Collectors** run
after and enrich it. Models and the API may touch neither.

This restates the existing rule rather than eroding it. The point of "collectors are the
only tier allowed to touch the network" was to concentrate impurity where it can be
reviewed, not to claim that exactly one package would ever fetch anything. Two named tiers
with a stated ordering preserves the property; a schedule source smuggled into a collector
would not, because it would have to fabricate a slate to satisfy the interface.

*Rejected:* forcing acquisition into `Collector` by passing an empty slate. The signature
would typecheck and the semantics would be a lie — `collect()` would ignore its only
argument, and every mechanical join in `EntityKind` would be inapplicable to its output.

*Rejected:* a third tier with its own package directory. One component does not earn a
tier. It lives in `packages/ingestion/`, which already owns slate assembly and canonical
entity writing, and is already forbidden to models by `FORBIDDEN_IN_MODELS`.

*Cost accepted:* the one-sentence summary of the architecture gets longer, and
`CLAUDE.md`, `docs/architecture.md`, and `docs/zones.md` all state the old rule and must be
corrected together. A rule that is true in three places and false in a fourth is worse than
either version.

### D2. goal.com is the source, and the alternatives are recorded because they will be re-proposed

Measured over five dates, goal.com returns every league in scope with a stable competition
id and country, so name collisions resolve — the `Premier League` bucket alone spans
England, Kazakhstan, Azerbaijan, Belarus, Bosnia, and Canada, and only the id separates
them. Completeness was checked against an independent source: its Premier League fixtures
for 2026-08-22 matched ESPN exactly, five of five on teams and kickoff times, with richer
provider data.

| competition | fixtures | with provider |
|---|---|---|
| USL Championship | 38 | 26 |
| USL League One | 25 | 16 |
| MLS NEXT Pro | 25 | 0 |
| Major League Soccer | 15 | 2 |
| NWSL | 13 | 10 |
| Liga MX | 5 | 0 |

Its `robots.txt` is `User-agent: * / Allow: /` with no disallowed paths and no rule naming
any AI agent — the only surveyed source that permits this.

*Rejected — livesoccertv.com:* returns 403 to every automated request including its own
terms page. Using it means defeating an access control.

*Rejected — ESPN:* a clean JSON endpoint, but no USL, no MLS NEXT Pro, and empty US
listings for Liga MX. Over a 10-day window only 25% of matches carried a US provider, and
the gap tracked the broadcaster announcement horizon rather than watchability.

*Rejected — FotMob:* the best data found — 173 matches over 7 days, every one with a
channel, 41 distinct US providers including the Spanish-language carriers others miss. Its
`robots.txt` disallows `/api/*` for everyone except four named search crawlers, so the only
route is page state. Best data, worst permission.

*Rejected — league websites:* `ligamx.net` disallows `/` for all user agents; USL disallows
`/` for ClaudeBot and disallows `/event/*` for everyone. MLS and MLS NEXT Pro permit
crawling but expose only undocumented APIs whose paths do not resolve. Two of the three
leagues in scope are unreachable at the source.

*Rejected — open-source TV listings:* the tooling is open, the data is not. `iptv-org/epg`
grabbers scrape commercial sites — its `tvtv.us` grabber sets a fake Chrome User-Agent, and
`tvtv.us` disallows ClaudeBot. Schedules Direct is properly licensed but has no structured
team data for soccer (`NFL, NHL, NBA and MLB` only) and restricts use to open-source
applications.

*Cost accepted:* an undocumented dependency on a third party's page structure, which will
break without notice. D5 and D8 are how that cost is contained rather than ignored.

### D3. Providers resolve from the source first, then a rights table

Per-match provider data from the source wins. Where it is absent, a hand-maintained
`league -> US providers` table answers. Where neither does, availability is `unknown`.

The table is not a workaround. Some US rights genuinely are league-wide: every MLS match
from 2026 is on Apple TV with no blackouts, and every MLS NEXT Pro match is free on
OneFootball. For those leagues a static line is *more* accurate than a per-match lookup,
because the source's provider data carries affiliate tracking (`sponsored: true`, and Fubo
is its single most-listed channel), so it reflects commercial partnerships rather than
rights. It also covers the source's decay across the window — provider coverage thins from
roughly a fifth of matches on day three to almost none by day ten.

**Verifying the seed entries corrected two assumptions this design was written on, which
is the strongest argument for the rule that entries cite the rights holder rather than an
aggregator.** MLS NEXT Pro is not Apple TV: Apple holds streaming rights through 2032, but
the 2026 broadcast arrangement is OneFootball plus the league's own site. And Liga MX is
not league-wide at all — its rights are held per club, with TelevisaUnivision carrying most,
Chivas home matches on Telemundo/Peacock, Monterrey, Tijuana and Santos on FOX, and a
Paramount+ subset in English. Both beliefs came from aggregators and both were wrong.

Liga MX therefore does **not** get an entry, and the consequence is real rather than
cosmetic: the source names no provider for it either, so its matches resolve to `unknown`
and D4's rule keeps them off the slate. Liga MX is absent from the product until either the
source starts answering for it or the table grows club-level entries — which is a change to
what this table means, not a row added to it.

The precedence is deliberately the other way round from what accuracy alone would suggest.
Per-match data wins because split-rights leagues exist — a Premier League matchweek divides
between NBC, USA Network, and Peacock, and no league-level line can express that. The table
answers only where the source is silent, which is where rights are constant.

*Rejected:* the table as the only source of providers. Cannot express split rights, which
covers the leagues with the largest US audiences.

*Rejected:* the source as the only source of providers. It names none for MLS NEXT Pro
across every sampled date, and that competition has a single free carrier for every match,
so the one thing the source cannot tell us is the thing that is easiest to state correctly.

*Cost accepted:* the table is hand-maintained and will go stale when rights move between
seasons, silently and in the direction users notice. It is Zone C configuration, carries a
`verified_on` date per entry, and is small enough to re-check in minutes.

### D4. `us-watchable` is a hard filter over a 10-day window from query time

A match joins the slate only when a provider is known. The window is 10 days from the
moment of the run, not a fixed date range.

The window is what makes the hard filter defensible. Beyond roughly two weeks a missing
provider usually means the broadcaster has not announced yet rather than that nobody
carries the match, so filtering on it further out would silently drop matches for a reason
that has nothing to do with watchability. Inside 10 days that ambiguity is largely spent,
and D3's table absorbs most of what remains.

*Rejected:* admitting matches with unknown providers and marking them. Honest, but it makes
`us-watchable` a label rather than a rule, and the product scope is watchable matches.

*Rejected:* a fixed window in configuration. Invites a value large enough to reintroduce
the announcement-horizon problem the 10 days exist to avoid.

*Cost accepted:* the slate is empty or thin in the off-season. Sampled on 2026-08-02 the
next 10 days held no match from any of the five largest European leagues, all of which were
between seasons. The demo will look sparse at times, which is correct rather than broken,
and `selection` records the rule so a thin slate stays interpretable.

### D5. Read the standardised format where it exists, page state only for what it lacks

The source publishes 696 schema.org `SportsEvent` blocks per date as JSON-LD — a
standardised, documented format carrying team names, UTC kickoff, venue, and event status.
It does not carry the competition or the providers, which live in the page's embedded
state.

Identity and timing come from JSON-LD. Competition and providers come from page state. The
two are not equally durable and the code should not pretend otherwise: the JSON-LD contract
is schema.org's and stable, the page state is a private implementation detail of somebody
else's front end.

*Rejected:* page state for everything, since it has all the fields. It would make the
stable half as fragile as the fragile half for no gain.

*Cost accepted:* two parsers and a join between them, for one source.

### D6. Availability is stored on the match, not carried in the snapshot

`contracts/schemas/match-snapshot.json` is a closed schema with `additionalProperties:
false`, and availability stays out of it. A snapshot is what a model sees, and a model must
not score a match differently because of who broadcasts it — that would make entertainment
value a function of distribution.

Availability is a property of the match, stored beside it and served by the API from the
store. `openapi.yaml` already defines `Availability` with `status` and `providers`, so the
response shape does not change; only its content stops being hardcoded.

*Rejected:* availability as a signal under `signals.*`. That namespace is for model input,
and this is not model input.

*Cost accepted:* a model that legitimately wanted a distribution feature — a
reach-weighted audience model, say — cannot have one without a later change. That is the
right default; the alternative leaks broadcast into scoring by accident.

### D7. Fixtures stay the default path; live is opt-in

`./scripts/demo.sh` continues to run against fixture files with no network and no
credentials. Live acquisition is selected explicitly.

The repository's stated bargain is that a fresh clone runs. That bargain is worth more than
the demo showing real matches by default, and a default that reaches the network makes
every test and every CI run depend on a third party being up.

*Cost accepted:* seeing real data takes a flag, and the flag has to be documented in three
places or nobody will find it.

### D8. Source failure is recorded, not silently an empty slate

An unreachable or unparseable source is a recorded failure, distinct from a window that
genuinely contains no watchable match. Both produce an empty slate; only the run record
separates them.

This is the same distinction `CollectionResult.unavailable()` already draws for collectors,
and it matters more here, because a silent failure at this tier empties the slate rather
than leaving a hole in one snapshot — every downstream tier would report, correctly and
uselessly, that there was nothing to do.

*Cost accepted:* another failure path to record and surface.

### D9. Canonical ids are slugs derived from names, not the source's ids

A league's canonical id is a slug of its country and name; a team's is a slug of its
name; a match's is `<league>-<date>-<home>-<away>`, extending the convention the
existing fixtures already use. All three are constrained to `^[a-z0-9-]+$` by
`match-snapshot.json` and `slate.json`, so slugging is not optional dressing — it is
what the schema requires.

Deriving them deterministically is also what makes re-running acquisition converge.
The same match yields the same id on every run, so entity writes upsert on a natural
key rather than needing a stored correspondence between the source's identifiers and
ours.

*Rejected:* adopting the source's ids directly. They are stable and unique, and
`dmz37633qbsvl7gncq5s51yjw` would work. But D2 is explicit that this source is the
best option available rather than a vendor commitment, and taking its identifiers as
canonical would make replacing it a migration of every stored row instead of a
change to one module.

*Rejected:* a hand-maintained mapping from source ids to canonical ids. Accurate,
and unmaintainable at this breadth — the leagues in scope alone carry several
hundred teams, and every promotion, relegation, and expansion franchise is a new
entry nobody will remember to add.

*Rejected:* storing the source's id alongside the canonical one for traceability. It
would make a rename detectable, but nothing in this change could act on the
detection, and a merge path for duplicated entities is well outside its scope. Left
out until something needs it.

*Cost accepted, and it is the real one:* a team's slug comes from its name alone,
because the source attaches a country to competitions and not to teams. Two clubs in
different countries sharing a name would collide onto one canonical team — River
Plate exists in both Argentina and Uruguay. The leagues in scope make this unlikely
rather than impossible, and the alternative — scoping a team by the country of the
first competition it was seen in — is worse, because it would assign a wrong country
to any team first seen in a continental competition.

*Second cost accepted:* if the source renames a team, its slug changes and a second
canonical entity appears, silently. Nothing detects this today.

*Third cost accepted:* live ids will not match the existing fixture ids. `arsenal`
and `england-premier-league` are not `ars` and `epl`, so the fixture snapshots and a
live run describe the same real clubs under different identifiers. Acceptable
because the fixture data is invented anyway and the two paths are never mixed in one
store, but it means a fixture-seeded database and a live-seeded one are not
interchangeable.

## Risks / Trade-offs

**The source changes its page structure without notice** → D5 confines the fragile half to
competition and providers; JSON-LD carries identity and timing. D8 makes breakage loud.
Golden fixtures captured from real responses let the parser be tested without the network.

**The rights table goes stale when rights move between seasons** → Per-entry `verified_on`
dates, and D3's precedence means it only answers where the source is silent. Small enough
to audit in minutes; wrong entries are the failure users notice fastest.

**Affiliate-driven provider data names a reseller rather than the rights holder** →
Accepted and recorded rather than corrected. "Fubo" is not false — it does carry the match
— but it is not the whole answer either. The table is authoritative where it applies.

**The demo looks empty in the off-season** → Correct behaviour under D4, not a fault.
`selection` records the rule and window so a thin slate is interpretable rather than
mysterious.

**Nothing scores after this change** → Stated in the proposal and expected. Neither
registered model's declared features are satisfied by anything acquisition produces.
Matches are returned with recorded skip reasons, which exercises the partial-coverage path
on real data.

**Depending on a third party with no contract** → Recorded in `docs/STUBS.md` as unofficial,
alongside the six alternatives and why each was rejected, so the decision can be revisited
without repeating the survey.

## Migration Plan

1. Schedule source, parsers, and golden fixtures captured from real responses. No wiring.
2. Availability persistence: migration, store writes and reads.
3. Rights table with `verified_on` dates, and the two-step resolution of D3.
4. `assemble_slate()` gains the `us-watchable` rule and the 10-day window; `league-allowlist`
   stays reachable for the fixture path.
5. API reads availability from the store, replacing the hardcode at `main.py:88`.
6. Opt-in flag through `scripts/pipeline.py` and `scripts/demo.sh`.
7. `CLAUDE.md`, `docs/architecture.md`, `docs/zones.md`, `docs/STUBS.md` corrected together
   for D1 and the three resolved placeholders.

Rollback is removing the flag. The fixture path is untouched throughout, so the demo keeps
working at every step.

## Open Questions

- **Whether the rights table belongs in `packages/ingestion/` or beside the composition
  recipes.** Both are Zone C configuration; the recipes directory has the established
  precedent for values that move without specs.
- **Refresh cadence.** The window moves continuously and providers get announced inside it,
  so a run is stale almost immediately. `refresh_after_seconds` exists on the collector
  interface but is unenforced pending `add-collector-corpora`; whether the schedule source
  needs its own answer sooner is unresolved.
- **Whether `unknown` remains reachable at all** once D4 filters on a known provider. It
  survives in the schema and the API, but under a hard filter no slate match can carry it.
  Either the filter is later softened or the state is only reachable through stale data.
