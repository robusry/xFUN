## Context

xFUN scores upcoming soccer matches on how entertaining they are likely to be, for viewers in the US, across leagues with meaningful US audiences. The system spans data ingestion, scoring models, a public API, and client applications.

The repository is currently empty apart from a README and OpenSpec scaffolding, so every structural decision here is greenfield. Two properties of the project drive the design more than anything else:

1. **Multiple models, developed independently.** Several models will produce scores for the same match. Whether the product exposes them individually, blends them into composites, or does both is explicitly undecided and expected to change repeatedly.
2. **A mixed-discipline team on GitHub.** Data-science contributors, backend contributors, and frontend contributors work in different languages at different cadences. Some will work spec-first; others will edit code by hand.

The design principle that follows from (1) is the one to judge every decision against: **make changing your mind cheap.** A decision that is easy to make but expensive to reverse is worse than one that is slightly awkward but trivially revertable.

## Goals / Non-Goals

**Goals:**

- Let each tier be built and tested independently, before the tiers around it exist.
- Make adding, replacing, or retiring a scoring model a local operation touching one directory.
- Make changes to how scores are combined and presented cost minutes, not a re-run of the modelling pipeline.
- Keep every score reproducible and explainable after the fact.
- Give hand-editing contributors a low-friction path that still ends with specs reflecting reality.

**Non-Goals:**

- Defining the fun formula itself. This change defines the slot a model fits into, not any model's contents.
- Choosing data providers, leagues in scope, or broadcast data sources.
- The evaluation harness and ground-truth labels. Necessary, but a separate change.
- Building the mobile app. Its package slot exists; its implementation does not.
- Solving multi-tenant auth, billing, or rate-limit tiers for the public API.

## Decisions

### D1. Monorepo, not repo-per-tier

Contract changes are atomic in one repository: `contracts/openapi.yaml` and every consumer update land in one reviewable pull request. Across four repositories the same change becomes a multi-day version-bump sequence. OpenSpec also resolves to the nearest `openspec/` root, so one repository means one spec tree and one `openspec list` covering the whole project.

*Alternatives considered.* Repo-per-tier, rejected for contract-change cost and spec fragmentation. A registered OpenSpec store holding specs centrally, rejected as machine-level setup solving a problem a monorepo does not have.

*Cost accepted.* Polyglot CI is more work to set up; mitigated by path-filtered workflows. `contracts/` keeps a later extraction cheap if a tier ever needs its own deploy or security boundary.

### D2. Batch scoring, not on-demand

Fixtures are known days ahead and odds move on a schedule; there is no request-time input to scoring. Scheduled jobs write scores; the API reads them.

This is the decision that makes "the modelling is independent" literally true. Model runtime and API runtime share nothing. A model can be a cron job, a notebook, or a rewritten-in-another-language service without the API noticing. A broken model degrades score freshness, not availability.

*Alternative considered.* On-demand scoring, rejected: it puts modelling dependencies in the request path, makes past scores irreproducible, and couples the API's uptime to the model's correctness.

### D3. Raw scores are truth; calibration and composition are derived views

Because the calibration cohort is chosen by the caller at request time (D5), a calibrated score cannot be a stored property of a row — the same raw score yields different calibrated values under different cohorts. Composition consumes calibrated scores, so composed scores are likewise derived.

```
  TRUTH (stored, append-only)        DERIVED (computed at read, cacheable)
  ───────────────────────────        ────────────────────────────────────
  raw model scores        ──────▶    calibrate(cohort) ──▶ compose(recipe) ──▶ rank
```

This is simpler than storing both, not more complex: there is exactly one source of truth. Materialized calibration or composition tables are a cache keyed by (cohort, recipe, raw-score generation), discardable at any time.

*Cost accepted.* Read-time computation. The workloads are small — a weekend cohort is on the order of a hundred matches times a handful of models, and percentile ranking over a few hundred rows is trivial. A season-wide cohort is still bounded by matches per league per season. Cache the common paths.

### D4. Models are pure functions and mutually independent

A model takes a `MatchSnapshot` and returns a `ModelScore`. No I/O, no clock, no database. Models never import or read from one another.

Purity buys testability on fixtures, reproducibility forever, and notebook-friendliness for data scientists. Mutual independence keeps the scoring stage a flat parallel fan-out rather than a dependency graph — the moment one model consumes another's output, backfills become ordered and reversal becomes expensive.

*Enforcement.* Dependency checks in CI on model packages: no database drivers, no HTTP clients, no cross-model imports.

### D5. The platform owns calibration; the caller owns the cohort

Models emit raw scores on whatever native scale suits them — a probability, a z-score, an arbitrary index. The platform percentile-ranks each model's raw scores within a cohort to produce a comparable 0–100 value.

Requiring models to self-normalize would be the obvious alternative and is worse: it pushes a cross-cutting statistical concern into every model, makes models inconsistent with each other, and silently produces plausible nonsense when a naive average is taken over incommensurable scales.

The cohort is a request parameter rather than a fixed platform choice because the right cohort is a product question that differs by surface. A weekend-view wants "best of what's on this weekend" (`window`); a season retrospective wants "best of the season" (`season`); a league page wants within-league comparison. Fixing one cohort at storage time would force that product decision permanently.

*Cost accepted.* Calibration must be computed per request-cohort, and every response must report which cohort it used — an unreported cohort makes a calibrated score uninterpretable.

### D6. Composition is configuration data, not code

A composition is a small declarative record: models, weights, missing-model policy, minimum contributing models. Changing the blend is a config diff any team member can read, review, and revert.

If changing weights required editing Python, proposals to change them would stop. Given that this decision is expected to change many times, the cost of one change must be near zero.

*Missing-model policy is a required field, not a default.* Coverage gaps are routine, not exceptional — a model needing shot data will have no score for leagues where shot data is unavailable. Leaving the policy implicit means each recipe author resolves it differently and inconsistently.

### D7. Public score names are repointable aliases

Consumers address `default`, not `composition-v3`. The alias resolves to a composition version or to a single model; repointing it changes what everyone receives with no client change and no contract change. The same indirection makes "expose one model" and "expose a blend" the same code path with different targets.

This is what converts the undecided composition question from a liability into a deferrable decision — and, by exposing per-model scores alongside composites, into a product feature: consumers can build their own blends.

*Cost accepted.* A repointed alias silently changes third-party results. Mitigated by also offering pinned composition targets for consumers that need determinism.

### D8. Append-only score storage

Score rows are never updated or deleted; recomputation inserts. Rows are keyed by (`match_id`, `model_id`, `model_version`, `snapshot_hash`) and carry provenance sufficient to reproduce them. Retired models keep their history.

With several models and volatile composition, "did the new model change last weekend's ranking?" must be answerable by query rather than memory. Append-only also makes a model regression a pointer rollback rather than a recompute. Storage cost at this data volume is negligible.

### D9. One package per model

Each model is its own package with its own dependencies and owner, depending only on `packages/scoring-contract/`. A model needing a heavy ML framework does not impose it on the API or on other models. Adding a model should touch exactly two things: a new directory and a registry entry.

### D10. Zone-based spec obligations

Requiring specs for every change is how spec-driven development dies on a mixed team. Zone A (contracts, scoring interface, scoring runtime, composition mechanism) always requires specs; Zone B (API, ingestion, model behavior) requires them on observable behavior change; Zone C (web, mobile, infra, CI, composition recipe values) does not.

Zone A is deliberately small — roughly the code everyone depends on and everyone will argue about.

The carve-out that matters most: **the composition mechanism is Zone A, the recipe values are Zone C.** Spec the machinery permanently; leave the numbers free to move weekly.

### D11. Drift is flagged and labeled, never blocked

Automation flags Zone A/B pull requests lacking spec changes and requires a `spec-debt` label to proceed. It does not block. A blocking check on a fast-moving team gets disabled within weeks; a label that shows up in a query does not. Validation of artifacts that *do* exist does block, since a malformed spec helps nobody.

Debt that can be counted is debt. Drift that cannot be seen is rot.

### D12. Branch first, PR at plan stage, archive as the final commit

Every change gets a branch created **before any file is touched** — including before `openspec new change` scaffolds its directory. `main` is protected; nothing reaches it except through a pull request. One change means one branch and one pull request.

The pull request opens as a **draft as soon as the planning artifacts exist**, before implementation. This is the decision that makes spec-first review real rather than nominal: reviewers argue with the proposal and specs in the pull request while it is still cheap to change them. Implementation commits then land on the same branch, and the pull request is marked ready once the work is done — so the plan and the code each get reviewed at the moment feedback is worth the most, while `main` still sees a single merge.

*Alternatives considered.* Two pull requests — plan merged separately, then implementation — gives the cleanest separation of concerns but leaves `main` carrying specs for unbuilt behavior and doubles the process overhead. A single pull request opened only when everything is finished is simplest, but the plan is then reviewed after the code exists, which is precisely the failure spec-driven development is meant to prevent.

*Archive is the final commit on the branch*, after rebasing on the current `main`. This is what keeps `main`'s specs in permanent agreement with `main`'s code — there is no window where they disagree, and no second step that can be forgotten under pressure. It also relocates the spec merge-conflict problem to where it is cheapest to solve: the rebase surfaces a conflicting concurrent archive inside the pull request, with both changes' authors and context available, instead of after merge.

*Cost accepted.* Branches live longer than in a merge-early workflow, since they span planning and implementation. Mitigated by keeping changes small and rebasing regularly — and long-lived branches are a direct signal that a change is over-scoped and should have been split.

## Risks / Trade-offs

- **Read-time calibration becomes slow at scale** → Workloads are bounded by matches per cohort; cache materialized results keyed by (cohort, recipe, raw-score generation) and invalidate on new raw rows. Revisit only with measurements.
- **Runtime cohort selection confuses consumers** — the same match legitimately scores 91 and 64 under different cohorts → Every response states its cohort and cohort size; documentation leads with the concept; a sensible default is applied when unspecified.
- **Composition weights get decided by whoever argues hardest** → This is the strongest argument for prioritizing the evaluation harness and a ground-truth label soon after the first model. Until a leaderboard exists, name a single owner who arbitrates entry into `default`.
- **Main spec files conflict when changes are archived concurrently** → Keep capabilities narrow, and rebase before the archive commit (D12) so conflicts surface inside the pull request rather than after merge.
- **Long-lived branches drift from main** — a consequence of spanning planning and implementation on one branch (D12) → Keep changes small; rebase regularly; treat a branch that stays open a long time as evidence the change is over-scoped and should be split.
- **Spec debt accumulates and is never paid** → The recurring reconciliation pass needs a named owner and a real slot, not good intentions. If the backlog grows monotonically for a few cycles, the zone boundaries are wrong and should be narrowed rather than the process abandoned.
- **Polyglot CI complexity slows everyone** → Path-filtered workflows from day one; contract and spec validation are the only universal jobs.
- **Broadcast availability data goes stale silently** → Modeled as a separate concern with its own cadence and an explicit "unknown" state. A confidently wrong provider is worse than an honest gap.
- **`contracts/` rots under shared ownership** → It is the highest-stakes directory and the one nobody owns by default; assign a required reviewer on that path.

## Migration Plan

Greenfield — this is a build order rather than a migration.

1. Branch protection on `main`, repository skeleton, path-filtered CI, contract and spec validation jobs. Branch protection comes first, since every subsequent step depends on the branch-and-PR workflow being enforced rather than merely documented.
2. `contracts/`: `match-snapshot.json`, `fun-score.json`, initial `openapi.yaml`, and hand-authored golden fixtures. Fixtures come first so downstream work can start immediately.
3. `scoring-contract` and `scoring-runtime`: interface, registry, feature assembly, calibration.
4. One reference model against fixtures, proving the contract end to end.
5. Score store and migrations; ingestion for one league and one data source.
6. Composition and alias resolution.
7. API over the store; generated clients.
8. Web against generated clients and fixtures — can begin in parallel from step 2.
9. Process: PR template, `spec-debt` label, drift-flagging automation, reconciliation cadence and owner.

*Rollback.* Nothing to roll back into; the reversible unit is each package, and any tier can be replaced behind its contract.

## Open Questions

- **API implementation language.** Python keeps one runtime with ingestion and scoring and lets the API import contract types directly; TypeScript shares a language with web and mobile. Leaning Python — the API is a thin read layer and the data-side gravity is stronger, with generated clients making the boundary cheap. Not yet decided.
- **Default calibration cohort.** Which cohort applies when a request omits the parameter, and whether the website's default differs from the API's.
- **Minimum cohort size** below which percentile calibration is not meaningful, and whether the fallback widens the cohort or marks the score low-confidence.
- **Is `default` given a stability promise for third parties**, or is pinning the only way to get determinism?
- **Who owns `contracts/`** as required reviewer, and **who arbitrates entry into `default`** before an evaluation leaderboard exists?
- **Reconciliation cadence** — weekly, or per sprint — and its named owner.
- **Merge strategy**, which interacts directly with the Conventional Commits decision. Rebase-merge preserves each conventional commit and keeps the plan → implementation → archive sequence legible in `main`'s history, which is the point of committing planning artifacts separately. Squash-merge collapses a change to one commit, making the pull request title the only message that survives and discarding that sequence. Leaning rebase-merge; not decided.
- **League scope**, which is upstream of ingestion work and unresolved: audience size versus entertainment density. Deferred to its own change.
