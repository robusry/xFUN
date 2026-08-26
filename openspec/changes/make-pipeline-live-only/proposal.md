## Why

The repository has two pipelines wearing one coat. The default path reads fixtures
from disk and the `--live` path fetches real matches, and the fixture path is what a
person runs, what the README demonstrates, and what CI checks. The consequence is
that the well-tested path is the one nobody wants and the untested path is the
product: nothing in CI ever constructs `LivePages`, the `httpx` client, or
`fetch_page`, so a shape change at the source leaves CI green and is discovered by
whoever next runs `--live` by hand.

The same coat mixes invented data into real output. `build_collector_registry`
registers the three `fixture-signals` collectors unconditionally, so a live run
writes made-up signal values into `collector_corpus` beside real ones, and a database
that has seen both paths serves eight fixture matches alongside several hundred real
ones. `docs/STUBS.md` already records that last one as "harmless, and confusing the
first time"; it is neither harmless nor confusing once the offline path stops being
something a user runs.

This change removes the demo as a concept. There is one pipeline, it always acquires
live, and the fixture machinery stops being a mode a person selects and becomes what
CI injects.

## What Changes

- **BREAKING** `scripts/demo.sh` is removed. The entry point becomes
  `scripts/pipeline.py`, which always acquires from the schedule source.
- **BREAKING** The `--live` flag is removed, along with the fixture-backed branch it
  selected. There is no user-reachable way to run the pipeline against fixtures.
- **BREAKING** The `league-allowlist` slate rule stops being reachable from the
  pipeline. `us-watchable` is the only rule a run selects; `league-allowlist` remains
  as a slate rule the test harness uses, because fixture snapshots carry no
  availability.
- The pipeline's four `live`-conditioned branches — the run clock, the collector page
  source, acquisition versus fixture ingestion, and the slate rule — collapse to their
  live side in the production entry point and become **injected seams** on a
  `run_pipeline(...)` function that the end-to-end test drives. `OFFLINE_STAMP`,
  `OFFLINE_RUN_ID`, and `OFFLINE_AS_OF` move out of `scripts/pipeline.py` and into the
  test that needs them.
- The three `fixture-signals` collectors are no longer registered by the production
  entry point. They are registered by the test harness only.
- **BREAKING** `social-buzz` is no longer registered by the production entry point.
  It is the only model reading `signals.*`, and a model declaring a path no collector
  provides fails registration by design — so it moves to the test harness with the
  collectors that feed it. `over-under-lean` and `odds-spread` stay registered: they
  read canonical data that is simply not fetched yet, and skipping every match with a
  recorded reason is the partial-coverage path working correctly.
- Captured third-party pages move out of `contracts/fixtures/` to a test-only
  location. `contracts/fixtures/` keeps only authored contract examples — the golden
  snapshots, scores, and slates that both sides of a seam agree on and that CI
  validates against the schemas. This makes structural the distinction
  `contracts/README.md` currently draws in prose.
- The fetch path gains its first coverage: a recorded-response test that exercises the
  real client against a captured HTTP exchange, so that "we can still fetch" is
  checked by CI rather than discovered by a user.
- CI keeps running an end-to-end pipeline with no network, through the injected seams
  rather than through a flag.

## Capabilities

### New Capabilities

None. This change removes a mode and relocates test material; it introduces no new
behaviour that is not already specified elsewhere.

### Modified Capabilities

- `schedule-acquisition`: The requirement "The system runs without network access or
  credentials" is replaced. Acquisition is no longer explicitly selected — it is what
  a run does. Reproducibility from a fixed anchor stops being a property of a
  user-facing path and becomes a property of the test harness, and the requirement
  must say so, including why the fixed anchor is still not a placeholder awaiting the
  clock.
- `data-collection`: A collector whose values are invented SHALL NOT be registered by
  the production entry point, so that no run writes fabricated signals into the same
  corpus as collected ones. The existing seam requirements are unchanged; what changes
  is who may register what.
- `repo-structure`: `contracts/fixtures/` is narrowed to authored contract examples.
  Captured third-party responses, which validate against no schema and are not an
  agreement between tiers, live under a test-only path. The requirement "Tiers are
  developable against fixtures before upstream tiers exist" survives and is the reason
  the authored fixtures stay where they are.

## Impact

**Code**

- `scripts/pipeline.py` — the largest edit. Branches collapse; `main()` splits into a
  live entry point and an injectable `run_pipeline(...)`.
- `scripts/demo.sh` — deleted.
- `packages/ingestion/src/xfun_ingestion/fixtures.py` — `fixture_payloads()` loses its
  production caller and is consumed by the test harness.
- `packages/collectors/fixture-signals/` — stays, no longer registered in production.
- `packages/models/social-buzz/` — stays, no longer registered in production.
- `contracts/fixtures/schedule/` (54 files) — moves to a test-only location, with
  `packages/ingestion/tests/test_schedule_parse.py` and
  `packages/collectors/recent-results/tests/test_recent_results.py` following it.
- `packages/api/tests/test_offline_reproducibility.py` — becomes the end-to-end test
  that drives the injected seams, and inherits the frozen anchor constants.

**CI**

- `.github/workflows/ci.yml:59` — the `pipeline.py --quiet` step no longer works as
  written, because there is no offline flag. The end-to-end check moves into pytest,
  where it can inject what it needs. CI stays offline.

**Docs**

- `CLAUDE.md`, `README.md`, `docs/STUBS.md`, `contracts/README.md` all describe a
  fixture-by-default demo and must be rewritten. `docs/STUBS.md` entries resolved:
  "Fixture and live matches share one store" and the "Two paths" half of "Ingestion".
  The "Collectors" and `social-buzz` entries change rather than resolve — those
  components survive as test material.

**Zones**

Zone A (`contracts/`) — the fixture layout narrows, so specs are required. Zone B
(`ingestion/`, `collectors/`, `models/`) — registration behaviour changes. Zone C
(CI, scripts) — carried along, no specs owed.

**Risk**

The property being traded away is real and was deliberate: a fresh clone with no
network currently runs end to end, and after this it will not. Anyone cloning the
repository needs working access to the schedule source to see anything at all, and an
unofficial source with no contract is now the only way in. The team should decide
that trade knowingly rather than inherit it — it is the one part of this proposal
that is a loss rather than a clarification.
