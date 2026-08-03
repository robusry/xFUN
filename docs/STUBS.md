# What is real and what is not

This repository is a **walking skeleton**: every tier exists and is connected end
to end, running on fixture data, with deliberately minimal components.

**An unmarked stub is worse than a missing feature**, because someone will build on
it. This page is the authoritative list. If something is not here, it is real.

---

## Real — not stubbed

These are the bootstrap's actual deliverable and are expected to survive.

| What | Where |
|---|---|
| The JSON Schemas and the OpenAPI document | `contracts/` |
| Golden fixtures, including the coverage edge cases | `contracts/fixtures/` |
| The model interface: purity, feature declaration, identity | `packages/scoring-contract/` |
| Registry, feature assembly, snapshot hashing, the model runner | `packages/scoring-runtime/` |
| Append-only score storage, enforced by database trigger | `infra/migrations/002_score_store.sql` |
| Tier-boundary enforcement | `scripts/check_dependencies.py` |
| Zones, branch/PR workflow, commit conventions, CI | `.github/`, `docs/` |

---

## Placeholder

### The models

| | |
|---|---|
| **What** | `over-under-lean` returns the over/under goals line. `odds-spread` returns the normalised entropy of vig-stripped outcome probabilities. `social-buzz` multiplies invented mention counts by an invented interest level. |
| **Why it is a placeholder** | None has been validated against any measure of whether matches were entertaining. `over-under-lean` ignores competitiveness and will rank a 4–0 procession above a tense 1–1; `odds-spread` ignores goals and will do the reverse; `social-buzz` measures attention, which is not the same thing as quality, from data that was made up. |
| **Why three** | To exercise multi-model fan-out and the partial-coverage path — they require different features on purpose. `social-buzz` additionally reads `signals.*` rather than canonical data, which is what makes the collector tier reachable from `scripts/demo.sh` instead of dormant. |
| **Not in the default recipe** | `social-buzz` is deliberately absent from `packages/composition/recipes/default.yaml`; it contributes nothing to the composed score. |
| **Replaced by** | `add-market-baseline-model` for the two market models; whichever change first builds a validated social model for `social-buzz` |

### Ingestion

| | |
|---|---|
| **What** | Two paths. `--live` acquires real upcoming matches and their US broadcasters from goal.com. The default reads `contracts/fixtures/snapshots/*.json` from disk. |
| **Why the fixture path stays** | A fresh clone must run with nothing configured and no network, and the default must not depend on a third party being up. |
| **What is still placeholder** | Everything a model reads. Acquisition establishes which matches exist and where to watch them; it fetches no odds, no form, and no league table, so **no model scores anything on a live run** — every match is returned with a recorded skip reason. That is the partial-coverage path working on real data, not a regression. |
| **Replaced by** | Whichever change gives models real input. Expected to be the collector tier, since model-facing data is what that tier exists to fetch. |

### Collectors

| | |
|---|---|
| **What** | `fixture-match`, `fixture-team`, and `fixture-league` in `packages/collectors/fixture-signals/` read `contracts/fixtures/signals/*.json` from disk. The values are invented. |
| **Why they exist** | To exercise all three entity joins end to end on a clone with nothing configured. `fixture-team` returns one team on purpose, so a match carries `signals.reddit.home.*` with no `away` counterpart and the partial-coverage path is real rather than theoretical. |
| **Also missing** | Nothing persists collected signals between runs, so `refresh_after_seconds` is declared but not enforced, and a re-score requires a re-collect. No collector consumes an unkeyed corpus. |
| **Replaced by** | Whichever change gives models real input — the collector tier is where model-facing data belongs; `add-collector-corpora` for persistence, retention, and the corpus escape hatch. Note that the **schedule source is not a collector** and does not replace these: it runs before the slate exists and produces what the slate is made of. |

### The slate rule

| | |
|---|---|
| **What** | `us-watchable` on the live path: kickoff within ten days of the run, and a known US broadcaster. `league-allowlist` remains for the fixture path, which carries no availability. |
| **Why the window is ten days** | Beyond roughly two weeks a missing broadcaster usually means the match has not been assigned one yet rather than that nobody carries it. A wider window would silently drop matches for a reason unrelated to watchability. Not configurable, for that reason. |
| **What it costs** | The slate goes thin between seasons, which is correct rather than broken. `selection` records the rule and window so a thin slate stays interpretable. |
| **No longer a placeholder** | Resolved by `add-live-schedule`. |

### Calibration cohorts

| | |
|---|---|
| **What** | Only `window` is implemented. `league`, `season`, and `global` raise `CohortNotImplemented`; the API returns **501**. |
| **Also missing** | Cohort caching and invalidation, minimum-cohort-size fallback (currently only flags `low_confidence`), and the season-sized benchmark that would confirm read-time calibration scales. |
| **Why it fails loudly** | A silent fallback to a different cohort would return a plausible number computed against the wrong population. |
| **Replaced by** | `complete-calibration-cohorts` |

### Composition policies

| | |
|---|---|
| **What** | Only `renormalize` is implemented. `require-all` and `fallback` raise `PolicyNotImplemented`; the API returns **501**. |
| **Also missing** | Pinned composition targets beyond the automatic `<id>-v<version>` alias, and a standalone recompose job. |
| **Replaced by** | `complete-composition-policies` |

### Score provenance

| | |
|---|---|
| **What** | Scores store a `snapshot_hash`, but the snapshots themselves are not persisted, so a stored score cannot be re-derived from its exact input without re-running ingestion. |
| **Also missing** | Retirement metadata is stored but nothing exercises it; no model has been retired. |
| **Replaced by** | `add-score-provenance` |

### Broadcast availability

| | |
|---|---|
| **What** | Served from the store. Providers come from goal.com per match, or from a hand-maintained league rights table where the source is silent. |
| **Why "unknown" survives** | It is still a first-class answer. A confidently wrong provider is worse than an admitted gap — telling someone a match is on a service that does not carry it is the failure users notice immediately. |
| **No longer a placeholder** | Resolved by `add-live-schedule`. |

### The schedule source

| | |
|---|---|
| **What** | goal.com, read from its schema.org JSON-LD and its embedded page state. |
| **Why it is not a vendor** | It publishes no API, no contract, and no stability promise. It will change shape without notice, and when it does the parser breaks loudly rather than returning an empty window. |
| **Why it anyway** | Six sources were surveyed and it is the only one that both covers the leagues in scope and permits automated access: its `robots.txt` is `User-agent: * / Allow: /` with no disallowed paths. livesoccertv 403s every automated request; FotMob disallows `/api/*`; Liga MX's and USL's own sites disallow `/`; tvtv.us and USL disallow ClaudeBot specifically; Schedules Direct is properly licensed but has no structured soccer teams and restricts use to open-source applications. The full survey is in the archived `add-live-schedule` design, D2 — read it before proposing a replacement, because most of the obvious candidates have already been tried. |
| **What would displace it** | A licensed feed with US listings and structured team data. None was found at any price a hobby project would pay. |

### The broadcast rights table

| | |
|---|---|
| **What** | `packages/ingestion/rights/us-broadcast-rights.yaml`, hand-maintained, consulted only where the schedule source names no provider. |
| **Why it exists** | Some US rights genuinely are league-wide — every MLS match is on Apple TV, every MLS NEXT Pro match is free on OneFootball — and no aggregator surveyed knew the second one. Where rights are constant, a verified line is more accurate than the source, whose provider data carries affiliate tracking. |
| **Why it will go stale** | US rights move between seasons and nothing here detects it. Every entry carries `verified_on` and a link to the rights holder's own announcement, and loading fails without them, but neither makes an entry current. |
| **What it deliberately cannot express** | Rights held per club or per match. Liga MX is the standing example: TelevisaUnivision carries most clubs, Chivas home matches are Telemundo/Peacock, Monterrey/Tijuana/Santos are FOX. It gets no entry, so **Liga MX matches never reach the slate**. |
| **Replaced by** | Nothing proposed. No surveyed source can replace it. A per-match manual entry path is the expected next step. |

### The database

| | |
|---|---|
| **What** | SQLite at `.data/xfun.db`. |
| **Why** | The demo runs with no daemon, no container, and no credentials. |
| **Cost** | The SQL dialect differs from Postgres; triggers and column types will need rewriting. All access goes through one small module to contain that. |
| **Replaced by** | Not yet proposed. A live run now writes a few hundred matches per window rather than eight, which makes this more pressing than it was, but nothing here has outgrown SQLite yet. |

### The web page

| | |
|---|---|
| **What** | One page, one hardcoded date window matching the fixtures, no routing, no date picker, no filtering. |
| **Replaced by** | Not yet proposed. |

---

## Not started

No package exists for these; the architecture leaves room for them.

| | Change |
|---|---|
| Evaluation harness — ground-truth labels, backtests, the model leaderboard | `add-evaluation-harness` |
| League scope — audience size versus entertainment density | `define-league-scope` |
| Mobile app — the workspace slot is reserved and commented out | not yet proposed |

**The evaluation harness is the most consequential item on this page.** With
several models and configurable weights, "which models, at what weights" has no
answerable form without a ground-truth label and a leaderboard. Until one exists,
the team is choosing weights on argument rather than evidence.
