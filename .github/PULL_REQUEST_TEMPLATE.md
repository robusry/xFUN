<!--
Open a pull request only when the change is COMPLETE: planning artifacts,
implementation, and the archive commit. Plan and code are reviewed together.

Title must follow Conventional Commits — squash-merge makes it the commit subject.
  <type>(<scope>): <subject>
  types: spec feat fix refactor perf test docs build ci chore
-->

## What and why

<!-- One or two sentences. Link the OpenSpec change if there is one. -->

## Does this change observable behavior in Zone A or Zone B?

<!-- Zone A: contracts/, scoring-contract, scoring-runtime, composition mechanism
     Zone B: api/, ingestion/, models/ behavior, evaluation/
     Zone C: web, mobile, infra, CI, deps, refactors, composition recipe values
     See docs/zones.md. -->

- [ ] No — Zone C only, or no behavior change
- [ ] Yes — spec deltas are included in this pull request
- [ ] Yes — but not specced yet; I have applied the `spec-debt` label

## Checklist

- [ ] Branch was created before any file was touched
- [ ] Tasks complete
- [ ] Rebased on `main`
- [ ] `openspec validate --all --strict` passes
- [ ] Change archived (`openspec archive`) as the final commit
- [ ] Squash-merge (team convention)

## Review notes

<!-- Anything a reviewer should look at first, or decisions worth arguing with. -->
