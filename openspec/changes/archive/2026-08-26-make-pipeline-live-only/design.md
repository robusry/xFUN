## Context

`scripts/pipeline.py` branches on a single `live` boolean in four places: the run
clock (`RunClock.for_run`), the collector page source (`LivePages` vs
`CapturedPages`), acquisition versus fixture ingestion, and the slate rule
(`us-watchable` vs `league-allowlist`). One flag drives all four, which is why the
fixture path reads as a coherent second mode rather than as scaffolding.

That second mode is currently load-bearing in three unrelated ways. It is the demo a
person runs, it is CI's end-to-end check (`.github/workflows/ci.yml:59`), and it is
the reason a fresh clone works with no network. This change keeps the second, removes
the first, and knowingly gives up the third.

Two facts constrain the shape. CI must stay offline — an end-to-end check that
contacts goal.com goes red when a third party has a bad afternoon, and the project
already depends on that source more than it would like. And the collector registry
rejects a model declaring a signal path no collector provides, so `social-buzz` and
the `fixture-signals` collectors cannot be separated: they move together or not at
all.

## Goals / Non-Goals

**Goals:**

- One pipeline, one entry point, no mode selection. Running it acquires live.
- CI runs the same pipeline end to end, offline, by injecting seams rather than by
  setting a flag.
- No invented value is ever written to the same corpus as a collected one.
- `contracts/fixtures/` holds only what its README says it holds: authored examples
  that both sides of a seam agree on.
- The fetch path is exercised by CI for the first time.

**Non-Goals:**

- Making the fixture path work better. It stops being a path.
- Separating fixture rows already sitting in someone's local `.data/xfun.db`. New
  runs stop adding them; existing rows are the developer's to delete.
- Odds and league-table acquisition. `over-under-lean` and `odds-spread` continue to
  skip every match with a recorded reason, which is correct and unchanged.
- Any change to how scores are calibrated, composed, or served.

## Decisions

### D1: One entry point with injected seams, not a hidden offline flag

`main()` splits. A `run_pipeline(...)` function takes the four varying things as
parameters — a `RunClock`, a page source, a slate producer, and a slate rule — and
contains everything that is currently below the branches. The CLI entry point
constructs the live versions of all four and calls it. The end-to-end test constructs
the offline versions and calls the same function.

**Alternatives rejected.** A hidden `--offline` flag, or an `XFUN_OFFLINE` environment
variable, keeps one code path and is a smaller diff — but it leaves the mode
reachable, and a mode that is reachable is a mode someone will run and then report a
bug about. The team's stated intent is that the demo concept goes away, not that it
gets a quieter name. A separate `scripts/e2e_offline.py` duplicating the pipeline was
rejected outright: two pipelines that must stay in step is the failure this change
exists to end.

**Cost accepted.** The end-to-end test now knows how the pipeline is wired, so wiring
can drift between test and production without either failing. Mitigated by keeping
`run_pipeline(...)` the whole body: everything below the seams is shared, and the test
substitutes only the four arguments. Not eliminated — a fifth seam added carelessly
in future would reintroduce the gap.

### D2: The offline end-to-end check moves into pytest

`.github/workflows/ci.yml:59` currently shells out to `pipeline.py --quiet`. With no
flag to pass, the check becomes a test — the existing
`packages/api/tests/test_offline_reproducibility.py` grows into it, since it already
asserts the properties that matter (identical scores, timestamps, and run ids across
repeated runs) and already knows about the frozen anchor.

`OFFLINE_STAMP`, `OFFLINE_RUN_ID`, and `OFFLINE_AS_OF` move out of
`scripts/pipeline.py` and into that test. They keep their long explanatory docstrings
verbatim. They are not becoming less important — they are moving to where their one
remaining caller lives.

**Alternatives rejected.** Keeping a CI-only shell entry point (`scripts/ci_e2e.py`)
was tempting because it preserves "run the whole thing by hand and read the output."
Rejected because it is D1's hidden flag with extra steps.

**Cost accepted.** A developer loses the ability to run the full pipeline offline and
watch it print. `pytest -q -k reproducibility` runs the same code but prints nothing
useful. If that turns out to hurt, the answer is a `--verbose` on the test, not a
restored mode.

### D3: Captured pages move to `tests/captures/`, at the repository root

The 52 captured goal.com pages move out of `contracts/fixtures/schedule/` to
`tests/captures/goal-com/`, carrying a README stating what they are, which script
regenerates them, and that they are parser input rather than a contract.

Root level rather than inside a package because three separate test suites read them
— `packages/ingestion/tests/test_schedule_parse.py`,
`packages/collectors/recent-results/tests/test_recent_results.py`, and the end-to-end
test in `packages/api/tests/`. Burying them under any one package makes the other two
reach across a package boundary for test data, which is worse than a shared root
directory.

**Alternatives rejected.** `contracts/fixtures/captured/` keeps the diff small and
was the obvious minimum, but it leaves third-party bytes inside the directory whose
defining property is that everything in it is validated against a schema and agreed
between tiers. That is the mixing this change is meant to end. Duplicating the pages
per package was rejected for the obvious reason.

**Cost accepted.** A top-level `tests/` directory that contains no tests, only data,
is mildly surprising and needs its README to stay honest. `contracts/README.md` loses
its "two kinds of fixture" section, which was good writing doing the job a directory
boundary should have been doing.

### D4: All 49 result captures are kept

They were sized by `capture_results_fixture.py` to satisfy the same stopping rule the
collector uses — five completed matches for each of the sixteen teams in the eight
authored snapshots, walking back from 2026-08-14. The end-to-end test still runs that
scan, so it still needs them.

**Alternatives rejected.** Shrinking the authored slate to two matches would cut the
captures to a handful and save ~250 KB. Rejected: the end-to-end test's value is that
it exercises the full fan-out, the partial-coverage path, and the reuse path
together, and a two-match slate exercises none of them properly. Deleting the
captures and having the recent-results tests rely only on their synthetic pages was
also rejected — the last test in that file exists specifically to run the real code
over the source's own bytes, and synthetic pages cannot replace that.

**Cost accepted.** The 300 KB stays. This change answers the objection by *purpose*
rather than by deletion: the files are now unambiguously CI input, in a directory
that says so, unreachable from anything a user runs.

### D5: The fetch path is covered by a recorded exchange, not by a live call

A new test constructs the real `LivePages` and the real schedule-source client
against an `httpx.MockTransport` replaying a recorded response. That exercises client
construction, headers, timeout configuration, redirect following, status handling,
and the mapping of transport errors onto `ScheduleSourceError` — everything between
"make a request" and "have bytes", which today nothing touches.

**Alternatives rejected.** A live smoke test hitting goal.com in CI would catch the
failure that actually matters — the source changing shape — but makes every CI run
depend on a third party, which is precisely the dependency the project is uneasy
about. A scheduled (nightly, non-blocking) live check is a reasonable future addition
and is deliberately not in this change; it is a different decision with a different
failure mode. Doing nothing was rejected: after this change the fetch path is the only
path, and shipping the only path untested is not defensible.

**Cost accepted.** A recorded exchange goes stale silently. This test proves the
client works against bytes shaped like goal.com's, not that goal.com still sends
them. It narrows the gap; it does not close it, and the spec should not claim
otherwise.

### D6: `social-buzz` and `fixture-signals` survive as test material

Neither is registered by the production entry point. Both are registered by the
end-to-end test, together, because the registry fails a model whose declared signal
paths nothing provides.

**Alternatives rejected.** Deleting all four packages is the cleaner-looking move and
was rejected because it removes real coverage: they are what exercises all three
entity joins (match, team, league), and `fixture-team` returns one team on purpose so
that the partial-coverage path has a case where a match carries
`signals.reddit.home.*` with no `away` counterpart. Nothing else in the repository
produces that shape.

**Cost accepted.** Four packages will exist that nothing in production registers, and
someone will eventually propose deleting them as dead code. `docs/STUBS.md` and each
package README must say plainly that they are test material and why, or this decision
does not survive contact with a future contributor.

### D7: A source failure stops the run, with nothing to fall back to

Unchanged from today's `--live` behaviour: acquisition failure prints the reason,
records it, and returns non-zero rather than proceeding into an empty slate. What
changes is that there is no longer a fixture path to retreat to.

**Alternatives rejected.** Falling back to the last successful slate was rejected for
the reason already recorded in `openspec/config.yaml` about stale corpora: a run over
yesterday's matches is a different claim from a run over today's, and no row records
which it was. That needs `add-score-provenance` first.

**Cost accepted.** A goal.com outage means the pipeline produces nothing, for
everyone, with no local workaround. This is the sharpest edge of the change.

## Risks / Trade-offs

**A fresh clone no longer runs.** → No mitigation is offered, because this is the
change, not a side effect. `README.md` must state the network requirement in its first
paragraph rather than let someone discover it by running the thing. The team is
trading a property it deliberately built for a system that is honest about being one
system. That trade should be argued at PR review, and if it is rejected, D1 is where
the argument lands.

**A single unofficial source is now the only way in.** → Partly mitigated by D5, which
at least makes client breakage visible. Not mitigated for source shape changes; the
parser still fails loudly rather than returning an empty window, which remains the
correct behaviour and is now the only warning anyone gets.

**Test wiring drifts from production wiring.** → Mitigated by D1's shared
`run_pipeline(...)` body. A reviewer should treat any new parameter on that function
as needing a reason.

**Existing local databases keep their fixture rows.** → Not mitigated in code. The
pipeline stops writing them; `docs/STUBS.md` should say that a database predating
this change holds eight matches that no current code path would produce, and that
deleting `.data/xfun.db` is the fix.

**Someone deletes the "unused" test packages.** → Mitigated only by documentation
(D6), which is a weak mitigation and is stated as one.

## Migration Plan

No data migration. The schema is untouched and the store is append-only.

For a developer: delete `.data/xfun.db` after pulling, or accept eight stale fixture
matches in local API responses forever.

Rollback is a revert. Nothing outside the repository changes state, and no stored row
written before or after this change is shaped differently.

## Open Questions

- **Is the loss of the offline clone acceptable to the team?** Recorded as decided by
  the requester, unresolved by the team. It is the one item here that a reviewer might
  reasonably block on, and D1 is where a reversal would be implemented.
- **`tests/captures/` versus a package-local home.** D3 argues for the root; it is a
  layout preference and cheap to change before implementation, expensive after.
- **Should a nightly non-blocking live check exist?** Deliberately excluded from this
  change (D5). It is the only thing that would catch a source shape change before a
  user does, and it deserves its own proposal rather than being smuggled in here.
- **Does `contracts/fixtures/snapshots/` still belong in `contracts/`?** It is
  genuinely an authored contract example, read by many tests and by
  `validate_contracts.py`, so this change leaves it alone — but it is also the input
  to an end-to-end test, which is the kind of double duty this change is otherwise
  ending.
