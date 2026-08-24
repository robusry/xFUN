## 1. The run's instant

- [x] 1.1 In `scripts/pipeline.py`, resolve the run instant once in `main()`: the clock on `--live`, the existing fixed anchor otherwise. Name it so the two cases are obviously different things, not one thing with a fallback.
- [x] 1.2 Replace every use of `STAMP` with the resolved value — `computed_at` on scores, `started_at`/`completed_at` on the collection run.
- [x] 1.3 Stop passing `run_id="demo"` on the live path; let `run_collectors` derive `run-<stamp>`. Keep a constant id on the fixture path so repeat offline runs stay idempotent (design D3).
- [x] 1.4 Leave `OFFLINE_AS_OF` exactly as it is, and strengthen its docstring to say it is not awaiting replacement by the clock. It is the constant most likely to be "fixed" by the next reader (design D2).
- [x] 1.5 Do not add a clock read below `main()`. `run_collectors` and `run_models` keep taking injected values (design D1).

## 2. API: the window becomes optional and stated

- [x] 2.1 `contracts/openapi.yaml`: `from` and `to` on `listMatches` lose `required: true`. Document that omitting a bound means "unbounded on that side", not "a default window".
- [x] 2.2 `contracts/openapi.yaml`: `MatchListResponse` gains a `window` object with nullable `from`/`to`, and it is required — a response must always say what it served, including that it served nothing.
- [x] 2.3 `packages/api/src/xfun_api/main.py`: `date_from`/`date_to` become optional and pass through to `load_snapshots`, which already accepts `None` for both.
- [x] 2.4 Populate `window` from the matches actually returned, not from the request. When the request bounded the range but the data is narrower, the honest answer is the data's range.
- [x] 2.5 Empty store with no range requested → empty list, `window` with both bounds null. Not an error, not an invented range.
- [x] 2.6 Update `contracts/fixtures/` golden responses for the new field.

## 3. Web

- [x] 3.1 `pnpm client:generate` after the contract change. Do not hand-edit `packages/clients/ts/src/generated.d.ts`.
- [x] 3.2 Delete `FROM`/`TO` from `packages/web/src/App.tsx` and request the match list with no date arguments.
- [x] 3.3 Show the window the response reports, so a viewer can tell what period they are looking at.
- [x] 3.4 Handle the empty-window case with something better than a blank page.

## 4. Tests

- [x] 4.1 Two consecutive fixture runs produce identical stored rows — same `computed_at`, same `run_id`, same scores. This is the test that fails if someone makes the fixture path clock-driven.
- [x] 4.2 A run with an injected live-style stamp stores that stamp rather than the fixed anchor.
- [x] 4.3 Two runs with different stamps produce two distinct `collection_run` rows, neither overwriting the other.
- [x] 4.4 Rescoring with a later `computed_at` resolves the serving read to the later row (score-store delta).
- [x] 4.5 API: no range → all matches, `window` spans them. Both bounds → filtered, `window` reports what was served. One bound → unbounded on the other side.
- [x] 4.6 API: empty store, no range → empty list with a null window rather than an error.
- [x] 4.7 Corpus freshness now expires on its own: a stamp advanced past `refresh_after_seconds` re-collects with no `--refresh`. This is the `add-collector-corpora` risk being retired, and is the point of doing these two changes back to back.

## 5. Documentation

- [x] 5.1 `docs/STUBS.md`: **The web page** — resolve "one hardcoded date window matching the fixtures". Routing, date picker, and filtering stay.
- [x] 5.2 `docs/STUBS.md`: note that the store accumulates fixture and live matches together, which this change deliberately does not address.
- [x] 5.3 `CLAUDE.md`: the fixture path's fixed anchor joins "Do not fix these" — it looks exactly like the bug this change removed elsewhere.
- [x] 5.4 Do not edit the archived `add-collector-corpora` design. Its TTL risk is retired by this change; that belongs in this change's record, not retrospectively in that one.

## 6. Verification

- [x] 6.1 `uv run python scripts/check_dependencies.py`, `ruff check .`, `pytest -q`.
- [x] 6.2 `uv run python scripts/pipeline.py` twice; diff the two runs' stored rows — identical.
- [x] 6.3 `uv run python scripts/check_api_conformance.py` and `validate_contracts.py`.
- [x] 6.4 `pnpm -r typecheck && pnpm web:build`.
- [x] 6.5 `openspec validate --all --strict`.
- [x] 6.6 Live run, then confirm from the store that `computed_at` and `run_id` reflect the actual run time, and that a second live run inside the refresh window still reuses the corpus while a stamp advanced past it does not.
- [x] 6.7 Load the web page against live data and confirm it shows matches beyond the old 31 August cutoff — the five that were invisible are the observable point of this change.
