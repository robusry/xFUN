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
| **What** | `over-under-lean` returns the over/under goals line. `odds-spread` returns the normalised entropy of vig-stripped outcome probabilities. |
| **Why it is a placeholder** | Neither has been validated against any measure of whether matches were entertaining. `over-under-lean` ignores competitiveness and will rank a 4–0 procession above a tense 1–1; `odds-spread` ignores goals and will do the reverse. |
| **Why two** | To exercise multi-model fan-out and the partial-coverage path. They require different features on purpose. |
| **Replaced by** | `add-market-baseline-model` |

### Ingestion

| | |
|---|---|
| **What** | `fixture_payloads()` reads `contracts/fixtures/snapshots/*.json` from disk. |
| **Why it is a placeholder** | No HTTP client, no provider, no credentials — deliberately, so a fresh clone runs with nothing configured. No provider has been selected. |
| **Replaced by** | `add-live-ingestion`, which now writes **collectors** rather than source adapters — `SourceAdapter` was removed by `add-collector-tier`. |

### Collectors

| | |
|---|---|
| **What** | `fixture-match`, `fixture-team`, and `fixture-league` in `packages/collectors/fixture-signals/` read `contracts/fixtures/signals/*.json` from disk. The values are invented. |
| **Why they exist** | To exercise all three entity joins end to end on a clone with nothing configured. `fixture-team` returns one team on purpose, so a match carries `signals.reddit.home.*` with no `away` counterpart and the partial-coverage path is real rather than theoretical. |
| **Also missing** | Nothing persists collected signals between runs, so `refresh_after_seconds` is declared but not enforced, and a re-score requires a re-collect. No collector consumes an unkeyed corpus. |
| **Replaced by** | `add-live-ingestion` for real sources; `add-collector-corpora` for persistence, retention, and the corpus escape hatch |

### The slate rule

| | |
|---|---|
| **What** | `assemble_slate()` selects matches by league allowlist within a time window, and records `rule: league-allowlist` on the slate. |
| **Why it is a placeholder** | The product scope is matches watchable in the US, but broadcast availability always answers `unknown`, so `us-watchable` is not computable yet. The rule is recorded rather than assumed so runs stay interpretable once it changes. |
| **Replaced by** | `add-broadcast-availability` |

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
| **What** | The API always returns `{"status": "unknown", "providers": []}`. |
| **Why it is honest** | "Unknown" is a first-class answer. A confidently wrong provider is worse than an admitted gap — telling someone a match is on a service that does not carry it is the failure users notice immediately. |
| **Replaced by** | `add-broadcast-availability` |

### The database

| | |
|---|---|
| **What** | SQLite at `.data/xfun.db`. |
| **Why** | The demo runs with no daemon, no container, and no credentials. |
| **Cost** | The SQL dialect differs from Postgres; triggers and column types will need rewriting. All access goes through one small module to contain that. |
| **Replaced by** | Expected alongside `add-live-ingestion` |

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
