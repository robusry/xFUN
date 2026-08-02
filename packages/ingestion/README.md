# ingestion

⚠️ **PLACEHOLDER.** Reads from disk; talks to nothing.

`FixtureFileAdapter` loads `contracts/fixtures/snapshots/*.json`. There is no HTTP
client, no provider, and no credentials — deliberately, so the skeleton runs for
someone who has just cloned the repository with nothing configured.

The adapter interface and snapshot assembly are real. Adding a live provider means
a new adapter and nothing else: everything downstream consumes `MatchSnapshot`s,
not provider payloads.

**Replaced by:** `add-live-ingestion`. See [docs/STUBS.md](../../docs/STUBS.md).

## Idempotence

Adapters must be idempotent — a scheduled job will fire twice eventually. Entity
writes are upserts on natural keys, so repeated runs converge rather than
duplicate.
