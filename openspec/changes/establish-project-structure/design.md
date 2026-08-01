## Context

xFUN scores upcoming soccer matches on how entertaining they are likely to be, for viewers in the US, across leagues with meaningful US audiences. The system spans data ingestion, scoring models, a public API, and client applications.

The repository is currently empty apart from a README and OpenSpec scaffolding, so every structural decision here is greenfield. Two properties of the project drive the design more than anything else:

1. **Multiple models, developed independently.** Several models will produce scores for the same match. Whether the product exposes them individually, blends them into composites, or does both is explicitly undecided and expected to change repeatedly.
2. **A mixed-discipline team on GitHub.** Data-science contributors, backend contributors, and frontend contributors work in different languages at different cadences. Some will work spec-first; others will edit code by hand.

The design principle that follows from (1) is the one to judge every decision against: **make changing your mind cheap.** A decision that is easy to make but expensive to reverse is worse than one that is slightly awkward but trivially revertable.

## Goals / Non-Goals

**Goals:**

- Give collaborators a structure they can read, run, and understand before any component is worth building.
- Let each tier be built and tested independently, before the tiers around it exist.
- Make adding, replacing, or retiring a scoring model a local operation touching one directory.
- Make changes to how scores are combined and presented cost minutes, not a re-run of the modelling pipeline.
- Keep every score reproducible and explainable after the fact.
- Give hand-editing contributors a low-friction path that still ends with specs reflecting reality.

**Non-Goals:**

- Working functionality. This change delivers a connected skeleton on fixture data; every component is minimal by intent.
- Defining the fun formula itself, or building any real model. The placeholder models demonstrate the contract and predict nothing.
- Choosing data providers, leagues in scope, or broadcast data sources. Ingestion reads from disk.
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

### D12. Branch first, one PR per change, opened when the change is complete

Every change gets a branch created **before any file is touched** — including before `openspec new change` scaffolds its directory. `main` is protected; nothing reaches it except through a pull request. One change means one branch and one pull request.

The pull request opens **only once the change is complete** — artifacts, implementation, and archive commit all present. Plan and implementation are reviewed together in one pass, so the reviewer assesses the specs against the code that implements them rather than in the abstract. Work in progress is still pushed to the remote branch for backup and visibility; the absence of a pull request is what signals "not ready."

*Alternatives considered.* Opening a draft pull request at the planning stage, so the plan is challenged before implementation effort is spent, was the initial choice and was reversed. It buys early plan feedback, but only when the gap between plan approval and completed implementation is short; on a change of any size the draft sits open for weeks, and the team preferred a single review event over two. Two separate pull requests — plan merged first, then implementation — gives the cleanest separation but leaves `main` carrying specs for unbuilt behavior and doubles the process overhead.

*Cost accepted.* A reviewer who rejects a design decision is rejecting it after the code implementing it exists, so some rework is discarded. This puts real weight on keeping changes small: the larger a change, the more expensive a late design objection becomes. It also makes over-scoped changes more painful, which is a useful pressure in the right direction.

*Archive is the final commit on the branch*, after rebasing on the current `main`. This is what keeps `main`'s specs in permanent agreement with `main`'s code — there is no window where they disagree, and no second step that can be forgotten under pressure. It also relocates the spec merge-conflict problem to where it is cheapest to solve: the rebase surfaces a conflicting concurrent archive inside the pull request, with both changes' authors and context available, instead of after merge.

*Cost accepted.* Branches live longer than in a merge-early workflow, since they span planning and implementation. Mitigated by keeping changes small and rebasing regularly — and long-lived branches are a direct signal that a change is over-scoped and should have been split.

### D13. Squash-merge by convention, with repository settings left at defaults

Changes reach `main` as a single squashed commit per pull request. This is documented in `docs/workflow.md` and specified as a convention — the repository's merge settings stay at GitHub's defaults, with all three merge strategies available, and nothing prevents a contributor from merging another way.

Two questions were initially conflated here: what the team should do, and whether tooling should enforce it. Separating them makes the second one easy to defer, and deferring it costs little given nothing is enforced today anyway.

*On the strategy.* An earlier draft of this decision selected rebase-merge, reasoning that committing planning artifacts separately from implementation is only worthwhile if that separation survives the merge. That reasoning was weaker than it appeared, for two reasons. First, **the plan's durable record is `openspec/changes/archive/`, not git history** — the proposal, design, specs, and tasks are archived into the repository as files, making git history a redundant second copy. Second, GitHub's default squash message setting concatenates the branch's commit messages into the squashed commit body, so the sequence is flattened rather than lost. Against that, rebase-only imposes real costs on a team with mixed git fluency: every commit must be curated because every commit lands on `main`, conflicts resolve per-commit during rebase, and force-pushing after a rebase is intimidating to contributors who aren't fluent. Squash also yields one revertable unit per change, which is arguably better revert granularity than a scatter of commits.

*On enforcement.* Locking a strategy down requires repository settings that the team does not control — the repository owner would have to disable two merge options. Requesting that has a cost and buys little while the team is small and the convention is new. Branch protection preventing direct pushes to `main` is worth requesting on its own merits; constraining which merge button is used is not, yet.

*Alternatives considered.* Rebase-merge only, rejected above. Merge commits, rejected for making `main`'s history a graph rather than a sequence. Allowing squash and rebase at the author's discretion, rejected for producing inconsistent history and adding a decision to every pull request.

*Cost accepted.* Nothing prevents a contributor from merging a different way, so `main`'s history may end up mixed. That is recoverable and low-stakes; if it becomes a real annoyance, enforcement is two toggles away.

### D14. Deliver a walking skeleton first

This change builds every tier end to end on fixture data, with deliberately minimal implementations, rather than building any tier to completion. Two placeholder models, one calibration cohort, one composition policy, a fixture-file ingestion adapter with no network access, a two-page API, and one web page — connected, running, and demonstrably passing data from one end to the other.

The goal of this first change is comprehension, not capability: collaborators need to see and understand the structure before the components are worth building. A skeleton makes the seams visible and lets several people start work in parallel against interfaces that already exist and demonstrably work.

*Consequence for stubs.* A collaborator must never be unsure whether something is real. Every placeholder is marked in its own source, its package README, and a central `docs/STUBS.md` that names the follow-up change replacing it. An unmarked stub is worse than a missing feature, because someone will build on it.

*What stays real.* The contracts and fixtures are not stubbed — they are the deliverable. So are the process and CI rules, since they govern how every subsequent change lands.

*Alternatives considered.* Building one tier properly first — say, ingestion and scoring — was rejected because it leaves the seams unproven and gives collaborators nothing to read. Building everything properly in one change was rejected as weeks of work behind a single review.

*Cost accepted.* Each stub becomes a follow-up change, so the change count goes up. That is the intent: eight follow-ups are enumerated in `tasks.md` section 14, each small enough to review properly.

### D15. Toolchain

**Python: `uv` workspaces.** The layout depends on per-package dependency isolation — a model requiring a heavy ML framework must not impose it on the API or on other models (D9). `uv` supports that natively, where Poetry needs manual wiring to achieve it. Speed is a secondary benefit.

**TypeScript: `pnpm` workspaces.** Strict dependency resolution refuses imports of packages not explicitly declared, which enforces the tier boundaries mechanically rather than by convention. npm's looser hoisting would let accidental cross-package imports pass unnoticed.

**API: Python with FastAPI.** Keeps one runtime with ingestion, scoring, calibration, and composition, letting the API import contract types directly instead of re-deriving them in a second language. The generated TypeScript client (task 9.5) makes the language boundary to the web tier cheap.

*One constraint this creates.* FastAPI's idiom is to generate OpenAPI from code, but `repo-structure` makes `contracts/openapi.yaml` the source of truth. The API is therefore validated *against* the committed contract rather than generating it, and CI enforces conformance (task 9.6 and the contract-conformance check). Getting this backwards would quietly invert the contract-first design.

*Alternative considered.* TypeScript for the API, which would share a language with web and future mobile. Rejected because the data-side gravity is stronger — the API is a thin read layer over calibration and composition, both of which live in Python.

### D16. Decisions are made by the team, with pull request approval as the deciding gate

No individual is named as owner or arbiter for any part of this project — not for `contracts/`, not for entry into the `default` composition, not for the reconciliation pass. The team decides as a group, and whether a pull request merges is the final decider.

The mechanism that makes this concrete rather than aspirational is `CODEOWNERS` naming the **team** on high-stakes paths. `contracts/` still cannot be changed without review; the review requirement simply attaches to the team instead of a person. The merge gate supplies the scrutiny an individual owner otherwise would.

*Alternatives considered.* Naming individual owners for `contracts/`, the `default` composition, and the reconciliation pass. Rejected by the team: on a group this size it adds bottlenecks and single points of failure, and pull request approval already functions as a decision procedure.

*Cost accepted, and where to watch it.* Group decisions resolve *who* decides but not *on what basis*. For the reconciliation pass, the exposure is diffusion of responsibility — a shared activity with no assignee can quietly stop happening, so the countable `spec-debt` backlog (D11) is the instrument that makes that visible. For composition weights, the exposure is that a group without shared evidence settles arguments by persistence rather than merit, which is the strongest argument for building the evaluation harness early. Neither cost is a reason to name owners now; both are reasons to watch specific signals.

## Risks / Trade-offs

- **Read-time calibration becomes slow at scale** → Workloads are bounded by matches per cohort; cache materialized results keyed by (cohort, recipe, raw-score generation) and invalidate on new raw rows. Revisit only with measurements.
- **Runtime cohort selection confuses consumers** — the same match legitimately scores 91 and 64 under different cohorts → Every response states its cohort and cohort size; documentation leads with the concept; a sensible default is applied when unspecified.
- **Composition weights get decided by whoever argues hardest** → Decisions are made by the team, with pull request approval as the deciding gate rather than an individual arbiter. That resolves who decides, but not on what basis, which makes the evaluation harness and a ground-truth label the highest-value follow-up: without a leaderboard, a group has no shared evidence to settle a weighting argument with.
- **Main spec files conflict when changes are archived concurrently** → Keep capabilities narrow, and rebase before the archive commit (D12) so conflicts surface inside the pull request rather than after merge.
- **Long-lived branches drift from main** — a consequence of spanning planning and implementation on one branch (D12) → Keep changes small; rebase regularly; treat a branch that stays open a long time as evidence the change is over-scoped and should be split.
- **Spec debt accumulates and is never paid** → The reconciliation pass is a shared team activity with no individual owner, which is the team's explicit choice; the mitigation is therefore a real recurring slot and a visible, countable backlog rather than an assignee. If the backlog grows monotonically for a few cycles, that is the signal to act — either the zone boundaries are too wide and should be narrowed, or the pass needs someone to drive it after all.
- **Polyglot CI complexity slows everyone** → Path-filtered workflows from day one; contract and spec validation are the only universal jobs.
- **Broadcast availability data goes stale silently** → Modeled as a separate concern with its own cadence and an explicit "unknown" state. A confidently wrong provider is worse than an honest gap.
- **`contracts/` rots under shared ownership** → It is the highest-stakes directory and the one nobody owns by default. A `CODEOWNERS` entry naming the team makes review of that path mandatory without assigning it to a person, so the merge gate supplies the scrutiny that an owner otherwise would.

## Migration Plan

Greenfield — this is a build order rather than a migration, and per D14 it produces a walking skeleton rather than any finished tier.

1. Repository skeleton, workspace tooling, path-filtered CI, contract and spec validation jobs. Branch protection is requested from the repository owner in parallel, since it needs access the team does not have.
2. `contracts/`: `match-snapshot.json`, `model-score.json`, initial `openapi.yaml`, and hand-authored golden fixtures. These come first and are not stubbed — everything downstream develops against them.
3. `scoring-contract` and `scoring-runtime`: interface, registry, snapshot hashing, feature assembly, model runner.
4. Two placeholder models, proving multi-model fan-out and the missing-feature skip path.
5. Score store and migrations; fixture-file ingestion adapter with no network access.
6. Calibration with the `window` cohort; composition with the `renormalize` policy and alias resolution.
7. API over the store; generated TypeScript client.
8. Web against the generated client — can begin in parallel from step 2.
9. End-to-end demo: one command from fixtures to a ranked list in the browser.
10. Process and documentation: PR template, `spec-debt` label, commit linting, and the docs that make the structure legible, including `docs/STUBS.md`.

*Rollback.* Nothing to roll back into; the reversible unit is each package, and any tier can be replaced behind its contract.

## Open Questions

- **Default calibration cohort** once more than one cohort exists. The skeleton defaults to `window` because it is the only resolver implemented; whether that remains the default, and whether the website's default differs from the API's, is deferred to `complete-calibration-cohorts`.
- **Minimum cohort size** below which percentile calibration is not meaningful, and whether the fallback widens the cohort or marks the score low-confidence. Deferred to `complete-calibration-cohorts`.
- **Is `default` given a stability promise for third parties**, or is pinning the only way to get determinism?
- **Reconciliation cadence** — weekly, or per sprint. Ownership is settled: the pass is a shared team activity, per D16.
- **League scope**, which is upstream of ingestion work and unresolved: audience size versus entertainment density. Deferred to its own change.
