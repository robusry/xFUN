## 1. Relocate the captured pages

- [x] 1.1 Move `contracts/fixtures/schedule/*.html` (3 files) and
      `contracts/fixtures/schedule/results/*.html` (49 files) to
      `tests/captures/goal-com/` and `tests/captures/goal-com/results/`, preserving
      filenames. Use `git mv` so the history follows.
- [x] 1.2 Write `tests/captures/README.md`: what these are, that they are captured
      third-party bytes rather than an authored contract, which script regenerates
      each set, and that nothing a user runs reads them.
- [x] 1.3 Update `scripts/capture_schedule_fixture.py` and
      `scripts/capture_results_fixture.py` to write to the new paths, and update
      their module docstrings, which currently describe the output as fixtures for
      the offline demo.
- [x] 1.4 Add a `captures_dir()` helper beside `fixtures_dir()` in
      `packages/scoring-runtime/src/xfun_runtime/paths.py`, and repoint
      `packages/ingestion/tests/test_schedule_parse.py` and
      `packages/collectors/recent-results/tests/test_recent_results.py` at it.
- [x] 1.5 Remove the "Two kinds of fixture" section from `contracts/README.md` and
      replace it with one sentence stating that everything under `contracts/` is
      authored and schema-validated, pointing at `tests/captures/` for the rest.
- [x] 1.6 Confirm `uv run pytest -q` still passes (235 tests) before any behaviour
      changes. This task is a pure move; a failure here is a wiring mistake, not a
      design consequence.

## 2. Split the pipeline into an entry point and an injectable run

- [ ] 2.1 Extract everything below the `live` branches in `scripts/pipeline.py:main`
      into `run_pipeline(...)`, taking a `RunClock`, a page source, a slate producer,
      and a slate rule as parameters. No behaviour change yet — `main()` still
      branches and calls it with either set of arguments.
- [ ] 2.2 Confirm `uv run python scripts/pipeline.py --quiet` and
      `--live` both still behave as before. This is the checkpoint that proves the
      extraction was faithful; everything after it removes things.
- [ ] 2.3 Delete the `--live` flag and the fixture branch from `main()`. The entry
      point constructs `LivePages`, a clock-derived `RunClock`, `acquire_window`, and
      the `us-watchable` rule unconditionally. Keep `--quiet` and `--refresh`.
- [ ] 2.4 Move `OFFLINE_STAMP`, `OFFLINE_RUN_ID`, and `OFFLINE_AS_OF` out of
      `scripts/pipeline.py` into `packages/api/tests/test_offline_reproducibility.py`,
      carrying their docstrings across verbatim. They explain why the anchor is not a
      bug and are the most likely thing in this change to be "fixed" later.
- [ ] 2.5 Delete `RunClock.for_run`'s `live` parameter; the entry point builds the
      live clock directly and the test builds the frozen one directly.
- [ ] 2.6 Remove the `fixture_collectors()` registration from
      `build_collector_registry`, and remove `SOCIAL_BUZZ` from `build_registry`.
      Both move to the test harness in task 3.
- [ ] 2.7 Delete `scripts/demo.sh`.

## 3. Rebuild the offline end-to-end check as a test

- [ ] 3.1 Grow `packages/api/tests/test_offline_reproducibility.py` into the
      end-to-end check: it constructs the frozen clock, `CapturedPages` over
      `tests/captures/goal-com/results/`, `fixture_payloads()` as the slate producer,
      and the `league-allowlist` rule, registers the `fixture-signals` collectors and
      `social-buzz`, and calls `run_pipeline(...)`.
- [ ] 3.2 Keep its existing assertions (identical scores, timestamps, and run ids
      across runs two and three) and add an assertion that the first run produces the
      expected score set, so the test covers correctness and not only stability.
- [ ] 3.3 Replace the `End-to-end pipeline on fixtures` step in
      `.github/workflows/ci.yml:59`. The `pytest` step already covers it; delete the
      step and note in the workflow why the end-to-end check now lives in the suite.
- [ ] 3.4 Confirm the check still fails when it should: temporarily break a scoring
      path and verify this test goes red, then revert. An end-to-end test that passes
      unconditionally is worse than none.

## 4. Cover the fetch path

- [ ] 4.1 Record one real goal.com exchange — request headers and response — into
      `tests/captures/goal-com/http/`, with a short note stating when it was recorded
      and that it will go stale silently.
- [ ] 4.2 Add a test driving the real `LivePages` and the real schedule-source client
      through `httpx.MockTransport` replaying that exchange, asserting the client is
      configured as expected and that bytes reach the parser.
- [ ] 4.3 Add failure-path cases: a transport error and a non-success status each
      translate into a recorded source failure naming the problem, not into an empty
      set of matches.
- [ ] 4.4 State in the test's module docstring what it does not establish — that the
      source is reachable, or still publishes this shape. The spec requires this
      limit to be visible where someone might otherwise over-trust the test.

## 5. Documentation

- [ ] 5.1 Rewrite `README.md`. Network access to the schedule source is now a
      requirement to run anything, and it belongs in the first paragraph rather than
      in a caveat. Remove every reference to `./scripts/demo.sh`.
- [ ] 5.2 Rewrite the affected parts of `CLAUDE.md`: the project-state paragraph, the
      setup-and-verification command list (the `pipeline.py` line goes), the layout
      block, and the "Do not fix these" entries covering `OFFLINE_STAMP` and the
      frozen fixture path — which stay true but now describe a test.
- [ ] 5.3 Update `docs/STUBS.md`: mark "Fixture and live matches share one store"
      resolved, rewrite the "Ingestion" entry now that there is one path, and rewrite
      the "Collectors" and `social-buzz` entries to say those packages are
      verification material rather than placeholders awaiting a real implementation.
      Add the note that a database predating this change holds eight matches nothing
      would now produce, and that deleting `.data/xfun.db` is the fix.
- [ ] 5.4 Add a README line to `packages/collectors/fixture-signals/` and
      `packages/models/social-buzz/` stating that they are registered only by the
      end-to-end test, what coverage they provide, and what would be lost by deleting
      them. Design decision D6 rests entirely on these two lines surviving.
- [ ] 5.5 Update `docs/architecture.md` and `docs/workflow.md` wherever they describe
      a fixture-backed default or the demo script.

## 6. Verification

- [ ] 6.1 Run the full CI sequence from `CLAUDE.md` in order, with the
      `scripts/pipeline.py` step removed, and confirm each passes.
- [ ] 6.2 Confirm no offline mode survived: search the tree for `--live`, `demo.sh`,
      `OFFLINE_`, and `fixture_payloads` and check every remaining hit is either a
      test, a capture tool, or documentation describing history.
- [ ] 6.3 Run the pipeline against the live source on a machine with network access
      and confirm it produces a slate, scores, and served API responses. This is the
      only manual step, and it is unavoidable: nothing in CI can prove the source is
      still answering.
- [ ] 6.4 Run `openspec validate --all --strict`.
