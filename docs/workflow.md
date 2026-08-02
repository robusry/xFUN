# Workflow

## The shape of a change

```
  branch FIRST — before any file is touched, including before
  `openspec new change` scaffolds its directory
        │
        ▼
  change/<change-id>
    commit   proposal.md
    commit   specs/, design.md, tasks.md
    commit   implementation
    commit   implementation
    ──────── rebase on main ────────
    commit   openspec archive
    ──────── open the PR ────────    ← plan and code reviewed together
    squash-merge
```

Push work in progress to the remote branch freely — it is backup and visibility.
**The absence of a pull request is what signals "not ready."**

## Branch naming

| Prefix | For |
|---|---|
| `change/<change-id>` | A spec-first OpenSpec change. Matches the change directory name. |
| `capture/<change-id>` | A code-first capture change documenting already-merged work. |
| `chore/<slug>`, `fix/<slug>` | Zone C work carrying no OpenSpec change. |

## Why the PR opens at the end

Plan and implementation are reviewed together, so a reviewer assesses the specs
against the code implementing them rather than in the abstract. One review event
instead of two.

The cost is real and worth naming: **a design objection arrives after the code
exists**, so late rework gets discarded. That puts weight on keeping changes
small. A branch that stays open a long time is evidence the change is over-scoped
and should have been split.

## Commits

Conventional Commits, checked on the PR title by CI:

```
<type>(<scope>): <subject>
```

| Type | For |
|---|---|
| `spec` | OpenSpec planning artifacts and archive commits |
| `feat` `fix` | New or corrected behavior |
| `refactor` `perf` | Restructuring or speed, no behavior change |
| `test` `docs` | Tests or documentation only |
| `build` `ci` `chore` | Dependencies, CI, everything else |

Scope is a package (`scoring-runtime`, `api`, `web`) or capability
(`score-calibration`). Breaking changes take `!` and a `BREAKING CHANGE:` footer.

The `spec` type is not standard Conventional Commits. It exists so planning
commits are distinguishable and greppable in history.

**The PR title matters most**, because squash-merge makes it the commit subject.

## Merging

**Squash-merge, by team convention.** One commit per change on `main`,
independently revertable.

This is a convention, not an enforced constraint — repository merge settings are
left at GitHub's defaults and all three merge buttons remain available. Nothing
stops a contributor merging another way; the deviation is addressed in review
rather than by tooling. If the convention stops holding, enforcement is two
settings away.

## Rebase, then archive, then open the PR

`openspec archive` folds a change's delta specs into `openspec/specs/`. Run it as
the **final commit**, after rebasing on the current `main`.

Rebasing first is what surfaces a conflicting concurrent archive *inside* your
branch, where both changes' context is available, rather than after merge. CI
refuses to merge a pull request containing an unarchived change, so `main`'s specs
never lag `main`'s code.

### When the rebase conflicts on a main spec

Another change archived deltas to a capability yours also modifies.

1. `git rebase main` reports the conflict in `openspec/specs/<capability>/spec.md`
2. Read both sides. The other change's requirements are already on `main` and are
   not yours to remove.
3. Reconcile so that both changes' requirements survive — this is a merge of
   intent, not a choice between versions.
4. `openspec validate --all --strict`
5. Continue the rebase, then make the archive commit.

Keeping capabilities narrow makes this rare. Archiving close to merge, rather than
batching, keeps it manageable when it happens.

## Setup

See the [README](../README.md). The OpenSpec CLI version is pinned in
`.openspec-version` and verified in CI — templates and validation rules ship with
the CLI, so a version mismatch produces divergent artifacts.

## Branch protection

`main` rejects direct pushes and requires a pull request. **Protection deliberately
does not lock down merge strategy or require linear history**, since squash-merge is
a convention here rather than a constraint.

Still outstanding: adding `contracts`, `ci`, and `pr-hygiene` as required status
checks. Reading protection settings needs repository-owner access, so contributors
without it cannot confirm the current configuration from the API.
