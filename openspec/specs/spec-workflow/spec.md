# spec-workflow Specification

## Purpose
TBD - created by archiving change establish-project-structure. Update Purpose after archive.
## Requirements
### Requirement: Spec obligations are defined by zone

The repository SHALL define three zones determining when an OpenSpec change is required:

| Zone | Paths | Obligation |
|---|---|---|
| A | `contracts/`, `packages/scoring-contract/`, `packages/scoring-runtime/`, composition mechanism in `packages/composition/` | A change with spec deltas is always required |
| B | `packages/api/`, `packages/ingestion/`, `packages/models/<id>/` behavior, `packages/evaluation/` | A change is required when externally observable behavior changes |
| C | `packages/web/`, `packages/mobile/`, `infra/`, CI, dependency updates, refactors, composition recipe values | No change required; if one exists it may be archived with `--skip-specs` |

Composition recipe *values* — the specific models, weights, and policies chosen — SHALL be Zone C configuration. The composition *mechanism* — recipe semantics, missing-model policies, alias resolution — SHALL be Zone A.

#### Scenario: Composition weights are retuned

- **WHEN** a contributor changes the weights in a composition recipe
- **THEN** no OpenSpec change is required, and the change is reviewed as a configuration diff

#### Scenario: A new missing-model policy is introduced

- **WHEN** a contributor adds a new missing-model policy type to the composition mechanism
- **THEN** an OpenSpec change with spec deltas to `score-composition` is required

#### Scenario: A styling change is made to the website

- **WHEN** a contributor adjusts layout or styling in `packages/web/`
- **THEN** no OpenSpec change is required

### Requirement: Two contribution paths lead to the same spec state

The project SHALL support both a spec-first path and a code-first path.

- **Spec-first**: a change is created, its proposal, specs, design, and tasks are written, implementation follows, and the change is archived.
- **Code-first**: code is written and merged by hand, then captured afterwards by a change whose artifacts describe the behavior that now exists, which is then archived.

A code-first capture SHALL be a legitimate, expected contribution, not an exception requiring justification.

#### Scenario: A hotfix is merged under time pressure

- **WHEN** a contributor merges a fix in a Zone A or Zone B path without prior specs
- **THEN** the pull request is marked as spec debt, and a capture change is created afterward that documents the behavior now in place and is archived

#### Scenario: A capture change is written

- **WHEN** a capture change is created for already-merged code
- **THEN** its proposal references the merged pull request, its spec deltas describe the current behavior, and it is validated and archived by the same rules as a spec-first change

### Requirement: Spec drift is visible and countable

Spec drift SHALL never be silent. A pull request modifying Zone A or Zone B paths without accompanying `openspec/` changes SHALL be flagged automatically and SHALL require an explicit `spec-debt` label to proceed. The set of outstanding spec debt SHALL be queryable at any time.

#### Scenario: Zone A code changes without spec changes

- **WHEN** a pull request modifies `contracts/` but no files under `openspec/`
- **THEN** automation flags the pull request and requires the `spec-debt` label before merge

#### Scenario: Someone asks how much spec debt exists

- **WHEN** a team member queries for outstanding spec debt
- **THEN** the labeled pull requests are enumerable, giving a countable backlog rather than an unknown amount of drift

#### Scenario: Malformed artifacts are committed

- **WHEN** a pull request contains OpenSpec artifacts that fail `openspec validate`
- **THEN** CI blocks the merge

### Requirement: Automated flagging warns rather than blocks

Automation that detects missing specs SHALL NOT block merges outright; it SHALL require acknowledgement via the `spec-debt` label. Validation of artifacts that do exist SHALL block.

#### Scenario: A contributor needs to merge urgently

- **WHEN** a contributor applies the `spec-debt` label to an unspecced Zone B change
- **THEN** the merge proceeds and the debt is recorded for later capture

### Requirement: Spec debt is enumerable at any time and cleared opportunistically

Outstanding spec debt SHALL be enumerable at any time by querying pull requests carrying the `spec-debt` label, and repository spec health SHALL be inspectable via `openspec doctor` and `openspec list --specs`.

The team SHALL clear that debt opportunistically rather than on a fixed schedule: no reconciliation cadence, ritual, or assigned owner is required. Clearing an item means writing and archiving a capture change, or explicitly recording that the item needs no specs. Capture changes reach `main` through the same pull request review as any other change.

The countable backlog is the control, not a calendar. A backlog that grows steadily over time is the signal that the zone boundaries are too wide, or that the team needs a deliberate pass after all.

#### Scenario: Someone asks how much spec debt exists

- **WHEN** a team member queries for outstanding spec debt
- **THEN** the labelled pull requests are enumerable, giving a countable backlog rather than an unknown amount of drift

#### Scenario: A spec-debt item is cleared

- **WHEN** a contributor picks up an outstanding spec-debt item
- **THEN** it is either captured into specs and its label removed, or explicitly recorded as not requiring specs

#### Scenario: No reconciliation has happened recently

- **WHEN** no spec-debt item has been cleared for some time
- **THEN** nothing is blocked and no process has been violated, because clearing debt is opportunistic; the growing backlog is the signal to act

### Requirement: Capabilities are kept narrow to limit archive conflicts

Specs SHALL be organized by capability rather than by package, and capabilities SHALL be scoped narrowly enough that concurrent changes rarely touch the same spec file. Changes SHOULD be archived close to the time their implementation merges rather than batched.

#### Scenario: Two changes are archived against one capability

- **WHEN** two changes modifying the same capability are archived in sequence
- **THEN** the second is reconciled against the updated main spec before archiving, and conflicts are resolved rather than overwritten

#### Scenario: A new scoring model is added

- **WHEN** a new model is introduced
- **THEN** it receives its own capability spec describing the signal it claims to capture, its required features, its native output scale, and its known coverage gaps

### Requirement: OpenSpec standards are version-controlled, not per-machine

The OpenSpec configuration, specs, changes, and archive SHALL be tracked in the repository so that every contributor works from identical standards. The generated AI tool instruction files SHALL also be tracked, so that contributors using different AI tools follow the same workflow rather than each machine's local configuration.

The following SHALL be tracked:

| Path | Why |
|---|---|
| `openspec/config.yaml` | Shared project context and per-artifact rules |
| `openspec/specs/` | The specifications themselves |
| `openspec/changes/` including each change's `.openspec.yaml` | Active changes and their schema binding |
| `openspec/changes/archive/` | Completed change history |
| Generated tool instruction files (e.g. `.claude/skills/`, `.claude/commands/`, and equivalents for other tools) | Identical agent behavior across contributors |

The following SHALL NOT be tracked:

| Path | Why |
|---|---|
| Per-tool local settings overrides (e.g. `.claude/settings.local.json`) | Machine-specific by convention |
| Personal worksets | Stored in global user configuration, never in the repository |

#### Scenario: A contributor clones the repository

- **WHEN** a new contributor clones the repository and runs `openspec list`
- **THEN** they see the same specs, changes, and configuration as every other contributor, with no local initialization step required

#### Scenario: A contributor uses a different AI tool

- **WHEN** a contributor initializes OpenSpec instruction files for an additional AI tool
- **THEN** those generated instruction files are committed, so that contributor's agent follows the same workflow as everyone else's

#### Scenario: A machine-local settings file is created

- **WHEN** a tool writes a local settings override such as `.claude/settings.local.json`
- **THEN** it is excluded by `.gitignore` and never committed

### Requirement: Structural directories survive cloning

Directories that are structurally required but may be empty — at minimum `openspec/specs/` and `openspec/changes/archive/` — SHALL contain a tracked placeholder file so they exist in every clone.

#### Scenario: The specs directory is empty before the first archive

- **WHEN** the repository is cloned before any change has been archived
- **THEN** `openspec/specs/` and `openspec/changes/archive/` exist, because Git does not track empty directories

### Requirement: The OpenSpec CLI version is pinned and its generated files kept current

Artifact templates, workflow schemas, and validation rules ship with the OpenSpec CLI rather than the repository, so version drift between contributors produces divergent artifacts. The required OpenSpec CLI version SHALL be recorded in the repository, and CI SHALL verify that the version in use matches it. When the pinned version changes, `openspec update` SHALL be run and its regenerated instruction files committed in the same change.

#### Scenario: A contributor runs a different CLI version

- **WHEN** a contributor generates artifacts using an OpenSpec CLI version other than the pinned one
- **THEN** CI reports the version mismatch

#### Scenario: The pinned version is upgraded

- **WHEN** the pinned OpenSpec CLI version is raised
- **THEN** `openspec update` is run and the regenerated tool instruction files are committed as part of that same change, so tracked instructions never lag the pinned CLI

### Requirement: All work happens on a branch created before any file is modified

No work SHALL be committed directly to `main`. A branch SHALL be created **before** any file is created or modified, including before the OpenSpec change directory is scaffolded. `main` SHALL be protected so that direct pushes are rejected and merges arrive only through pull requests.

Branch names SHALL follow these prefixes:

| Prefix | Used for |
|---|---|
| `change/<change-id>` | A spec-first OpenSpec change; the branch name matches the change directory name |
| `capture/<change-id>` | A code-first capture change documenting already-merged work |
| `chore/<slug>`, `fix/<slug>` | Zone C work carrying no OpenSpec change |

#### Scenario: A contributor begins a new proposal

- **WHEN** a contributor decides to propose a change
- **THEN** they create the branch first, and only then run `openspec new change` and write artifacts, so that no scaffolding or artifact file is ever created while on `main`

#### Scenario: A direct push to main is attempted

- **WHEN** any contributor or automation attempts to push a commit directly to `main`
- **THEN** the push is rejected by branch protection

#### Scenario: Work is already in progress on main

- **WHEN** a contributor discovers they have begun work while still on `main` and has not yet committed
- **THEN** they create the branch from that working state before committing, so no commit ever lands on `main` directly

### Requirement: One change maps to one branch and one pull request

Each OpenSpec change SHALL correspond to exactly one branch and exactly one pull request. Planning artifacts, implementation, and the archive step for a change SHALL all land on that single branch and merge to `main` in a single merge.

#### Scenario: A change is implemented

- **WHEN** a change moves from proposal through implementation to archive
- **THEN** all of that work exists on one branch and reaches `main` through one pull request and one merge

#### Scenario: Implementation grows beyond the original change

- **WHEN** work in progress turns out to require behavior outside the change's stated scope
- **THEN** the additional work becomes its own change on its own branch rather than expanding the current one

### Requirement: The pull request is opened once the change is complete

A pull request SHALL be opened only when the change's planning artifacts, implementation, and archive commit are all complete. Reviewers SHALL review the plan and the implementation together in that single pull request, so that specs and the code implementing them are assessed against each other.

```
branch: change/<change-id>
  commit   proposal.md
  commit   specs/, design.md, tasks.md
  commit   implementation
  commit   implementation
  ──────── rebase on main ────────
  commit   openspec archive
  ──────── open PR ────────   ← plan and code reviewed together
  merge
```

Work in progress SHALL be pushed to the remote branch for backup and visibility, but the absence of a pull request SHALL indicate that the change is not yet ready for review.

#### Scenario: Planning artifacts are complete but implementation has not started

- **WHEN** a change's proposal, specs, design, and tasks are written and `openspec validate` passes
- **THEN** no pull request is opened yet, and work continues on the branch

#### Scenario: A change is ready for review

- **WHEN** a change's tasks are complete and its archive commit is present
- **THEN** a pull request is opened containing the planning artifacts, the implementation, and the archive, and the reviewer assesses the plan and the code together

#### Scenario: A reviewer objects to the design

- **WHEN** a reviewer challenges a design decision in the pull request
- **THEN** the planning artifacts and the affected implementation are both revised on the same branch before merge, since the change is reviewed as a single unit

#### Scenario: Work in progress is pushed

- **WHEN** a contributor pushes incomplete work to the remote branch
- **THEN** the push is expected and no pull request is opened, because a pull request signals readiness for review

### Requirement: A change is rebased on main and archived as the final commit before merge

Before merging, the branch SHALL be rebased on the current `main`, and `openspec archive` SHALL be run as the final commit on the branch. Spec conflicts arising from concurrently archived changes SHALL be resolved on the branch, within the pull request, rather than after merge.

#### Scenario: Another change archived the same capability first

- **WHEN** a branch is rebased on `main` and another change has already archived deltas to a capability this change also modifies
- **THEN** the conflict surfaces during the rebase and is resolved on the branch before the archive commit is made

#### Scenario: A change requires no spec updates

- **WHEN** a Zone C change is archived
- **THEN** `openspec archive --skip-specs` is used and the main specs are left unchanged

#### Scenario: A merge is proposed without archiving

- **WHEN** a pull request containing an OpenSpec change is opened but the change has not been archived
- **THEN** the merge is blocked until the archive commit is present, so that `main` specs never lag `main` code

### Requirement: Pull requests merge by squash-merge, as a documented convention

Contributors SHALL merge pull requests using squash-merge, so that each change reaches `main` as a single commit that is independently revertable.

This is a documented team convention rather than an enforced constraint. The repository's merge settings SHALL be left at their defaults and SHALL NOT be locked down to a single strategy. The convention SHALL be documented in `docs/workflow.md`. Whether to enforce it through repository configuration SHALL be revisited only if the convention fails to hold in practice.

#### Scenario: A change is merged

- **WHEN** a pull request containing planning, implementation, and archive commits is squash-merged
- **THEN** `main` receives one commit for that change, and the individual branch commit messages are retained in that commit's body

#### Scenario: A contributor uses a different merge strategy

- **WHEN** a contributor merges using a merge commit or a rebase-merge
- **THEN** the merge is not blocked, because the convention is documented rather than enforced, and the deviation is addressed in review rather than by tooling

#### Scenario: The squashed commit subject is derived

- **WHEN** a pull request is squash-merged
- **THEN** the resulting commit subject conforms to Conventional Commits, because both pull request titles and individual commit messages are required to conform

### Requirement: Commit messages follow Conventional Commits

Commit messages SHALL follow the Conventional Commits format `<type>(<scope>): <subject>`. Pull request titles SHALL follow the same format, since the title becomes the commit subject under a squashing merge strategy. Both SHALL be validated automatically.

Permitted types:

| Type | Used for |
|---|---|
| `spec` | OpenSpec planning artifacts and archive commits |
| `feat` | New behavior |
| `fix` | Corrected behavior |
| `refactor` | Restructuring with no behavior change |
| `perf` | Performance work with no behavior change |
| `test` | Tests only |
| `docs` | Documentation only |
| `build` | Dependencies, packaging, workspace tooling |
| `ci` | Continuous integration configuration |
| `chore` | Everything else |

The scope SHALL be a package name (e.g. `scoring-runtime`, `api`, `web`) or a capability name (e.g. `score-calibration`) where one applies. Breaking changes SHALL be marked with `!` after the type or scope, and SHALL include a `BREAKING CHANGE:` footer describing the migration.

#### Scenario: Planning artifacts are committed

- **WHEN** a contributor commits a change's proposal, specs, design, and tasks
- **THEN** the commit uses the `spec` type, making planning commits distinguishable from implementation commits in history

#### Scenario: A commit message does not conform

- **WHEN** a commit message or pull request title does not match the Conventional Commits format or uses a type outside the permitted list
- **THEN** automated validation fails and reports the expected format

#### Scenario: A contract change breaks consumers

- **WHEN** a change alters an interface in `contracts/` in a way that breaks existing consumers
- **THEN** the commit is marked with `!` and carries a `BREAKING CHANGE:` footer describing the migration

