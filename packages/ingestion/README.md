# ingestion

⚠️ **PLACEHOLDER.** Reads from disk; talks to nothing.

Two jobs, both narrower than this package used to have:

1. **Slate assembly** — deciding which matches a collection run is about.
2. **Canonical entity writing** — turning match payloads into rows.

`fixture_payloads()` loads `contracts/fixtures/snapshots/*.json`. There is no HTTP
client, no provider, and no credentials — deliberately, so the skeleton runs for
someone who has just cloned the repository with nothing configured.

## What moved out

`SourceAdapter` is gone. It let several sources be plugged in, but each yielded
whole match payloads, so three models wanting one source had no way to share a
fetch. That job now belongs to `packages/collectors/`, where a collector receives
the whole slate, chooses its own fan-out, and keys its output by match, team, or
league for the platform to join on.

What is left here is the part collectors do not do: identity, kickoff, teams,
league, and the canonical odds/form/table blocks.

## The slate rule is a placeholder too

The product scope is matches watchable in the US, but broadcast availability always
answers `unknown`, so "watchable" is not computable yet. Until it is, the slate is a
league allowlist within a time window — and the rule in force is **recorded on the
slate** rather than assumed, so a run stays interpretable after the rule changes.

That matters more than it looks: a team-keyed collector polls a different set of
sources for a different set of teams, so its output is only meaningful alongside the
slate that produced it.

**Replaced by:** `add-live-ingestion` for the provider, `add-broadcast-availability`
for the slate rule. See [docs/STUBS.md](../../docs/STUBS.md).

## Idempotence

A scheduled job will fire twice eventually. Entity writes are upserts on natural
keys, so repeated runs converge rather than duplicate.
