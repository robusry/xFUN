## 1. Storage

- [x] 1.1 Add `infra/migrations/005_collector_corpus.sql` creating `collector_corpus` keyed by `(collector_id, entity_id, collected_at)`, carrying `entity_kind`, `values` (JSON of leaf → value), and `run_id` as provenance. Comment why it is separate from `collection_run` (design D1) and why it is append-only (D2).
- [x] 1.2 Add an append-only trigger mirroring `002_score_store.sql`, so immutability is enforced by the database rather than by callers.
- [x] 1.3 Index `(collector_id, entity_id, collected_at DESC)` so the latest-per-entity read and the coverage check are both indexed.
- [x] 1.4 Correct the "NOT stored here" comment at `infra/migrations/003_collection_run.sql:15-19` — it becomes wrong with this change and would otherwise mislead the next reader.

## 2. Store API

- [x] 2.1 `write_corpus(conn, run_id, collector_id, entity_kind, values, collected_at)` in `packages/store/src/xfun_store/collection.py`, inserting one row per entity.
- [x] 2.2 `read_corpus(conn, collector_id, entity_ids)` returning the latest values per entity plus the entities with no row at all, so absence is distinguishable from a stored empty value (spec: "An entity the collector has never covered").
- [x] 2.3 `corpus_freshness(conn, collector_id)` returning the most recent `collected_at` for the collector, or `None` if it has never collected.
- [x] 2.4 Export the three from `xfun_store.__init__`.
- [x] 2.5 Unit tests: supersede-without-erase, absent-entity versus stored-empty, freshness of a never-collected collector.

## 3. Runtime invocation decision

- [x] 3.1 Add a `CorpusReader` protocol to `packages/scoring-runtime/src/xfun_runtime/collectors.py` — the runtime must not import `xfun_store` directly, matching how `write_collection_run` takes the run structurally rather than importing the runtime type.
- [x] 3.2 Add `reused` to `CollectorOutcome` and to the `CHECK (outcome IN (...))` constraint in `003_collection_run.sql`, with `entities_with_data` carrying the count served from the corpus (design D5).
- [x] 3.3 In `run_collectors`, before invoking a needed collector, evaluate freshness AND coverage (design D3). Compare against the injected `started_at`, never the clock (design D4) — this is the constraint most likely to be "fixed" into a bug.
- [x] 3.4 Treat `refresh_after_seconds is None` as "always invoke".
- [x] 3.5 On successful collection, write the corpus; on failure, write nothing and do not substitute persisted values (design D6).
- [x] 3.6 Merge reused values into the run's signals so the join and snapshot assembly downstream cannot tell reuse from collection.
- [x] 3.7 Add a `force: bool = False` parameter that bypasses the freshness check.

## 4. Runtime tests

- [x] 4.1 Fresh and complete corpus → collector not invoked, outcome `reused`, signals still present downstream.
- [x] 4.2 Fresh corpus missing one slate entity → collector invoked. This is the scenario the design calls out as the reason coverage is checked at all.
- [x] 4.3 Corpus older than the declared window → collector invoked.
- [x] 4.4 `refresh_after_seconds is None` → invoked every run.
- [x] 4.5 Collector fails with a corpus present → failure recorded, corpus unchanged, models skip with the skip attributable to failure rather than absence.
- [x] 4.6 `force=True` with a fresh corpus → invoked, and previously persisted values remain queryable.
- [x] 4.7 Same inputs and same `started_at` produce the same invocation decision twice — the reproducibility property D4 exists to protect.

## 5. Contract and pipeline

- [x] 5.1 Rewrite the `refresh_after_seconds` docstring in `packages/scoring-contract/src/xfun_contract/collection.py:110-118` — remove "DECLARED BUT NOT YET ENFORCED" and the forward reference to this change, and state what it now controls.
- [x] 5.2 Add `--refresh` to `scripts/pipeline.py`, threading `force` into `run_collectors` (design D7).
- [x] 5.3 Print the `reused` outcome in the pipeline's per-collector summary, including how many entities were served from the corpus, so an operator can see no network call happened.
- [x] 5.4 Verify the offline path still produces byte-identical ranked output on a second run — with a frozen `STAMP` the second run reuses everything, which is correct for the fixture demo (design D4, Risks).

## 6. Documentation

- [x] 6.1 `docs/STUBS.md`: resolve the persistence half of the "Also missing" row under **Collectors**. The unkeyed-corpus escape hatch keeps its entry and stays pointed at a future change.
- [x] 6.2 `packages/collectors/README.md` and `packages/store/README.md`: document that a collector's declared refresh window now decides whether it runs.
- [x] 6.3 `CLAUDE.md`: add the corpus to the "Do not fix these" list — specifically that freshness is measured against an injected timestamp rather than the clock, which reads like a bug and is not.
- [x] 6.4 Note in the archived design that TTL expiry does not fire unattended until the dates change lands, so a later reader does not diagnose it as broken.

## 7. Verification

- [x] 7.1 `uv run python scripts/check_dependencies.py` — confirm the runtime still does not import the store.
- [x] 7.2 `uv run ruff check .` and `uv run pytest -q`.
- [x] 7.3 `uv run python scripts/pipeline.py` twice; confirm the second run reports `reused` and makes no fetch.
- [x] 7.4 `uv run python scripts/pipeline.py --refresh`; confirm collectors are invoked despite a fresh corpus.
- [x] 7.5 `uv run python scripts/check_api_conformance.py` and `scripts/validate_contracts.py` — no response shape should have moved.
- [x] 7.6 `openspec validate --all --strict`.
- [ ] 7.7 Run the live path once (`--live`, then `--live --refresh`) and record what actually happened against what this design predicted, as `add-recent-goals-model` did.
