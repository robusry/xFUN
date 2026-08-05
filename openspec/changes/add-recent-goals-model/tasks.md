## 1. Reading results from the source

- [ ] 1.1 Make the schedule source's page fetching reusable: a public client carrying this source's headers and its 403 policy, and a public fetch of one dated page, without changing what acquisition does
- [ ] 1.2 Read completed matches out of a dated page: home and away names, kickoff, competition, and the goals each side scored, counting only matches the source reports as finished (design D4)
- [ ] 1.3 Test that postponed and cancelled entries carrying a 0-0 score, and in-progress entries carrying a running score, are not counted

## 2. The collector

- [ ] 2.1 Add `packages/collectors/recent-results/`, keyed by team, namespace `form`, providing `goals_scored_last_5`, declaring `refresh_after_seconds` at six hours
- [ ] 2.2 Walk dates backwards from the run, stopping at the first of: every slate team has five completed matches, or the 120-day bound (design D3)
- [ ] 2.3 Key output by canonical team id derived through `xfun_ingestion.schedule.canonical`, so the join to the slate is exact (design D8)
- [ ] 2.4 Provide no value for a team with fewer than five completed matches, and no partial sum (design D5)
- [ ] 2.5 Report failure for the whole run when a page cannot be fetched or parsed, discarding values gathered so far
- [ ] 2.6 Take the page source and `as_of` as injected seams, so every test runs without the network

## 3. The model

- [ ] 3.1 Add `packages/models/recent-goals-total/`, declaring `signals.form.home.goals_scored_last_5` and `signals.form.away.goals_scored_last_5` and depending on `xfun-scoring-contract` alone
- [ ] 3.2 Score the sum of the two sides, unnormalised, with each side's contribution in `components`
- [ ] 3.3 Test determinism on a snapshot, and test that a snapshot missing the away path is skipped with the path named

## 4. Golden fixtures and the offline path

- [ ] 4.1 Add `scripts/capture_results_fixture.py`, reducing a past-date page to matches involving a named set of teams, in the same spirit as `capture_schedule_fixture.py`
- [ ] 4.2 Capture enough dates into `contracts/fixtures/schedule/results/` to give each team in `contracts/fixtures/snapshots/*.json` five completed matches
- [ ] 4.3 Record in `contracts/README.md` that these are captured third-party responses, refreshable wholesale, like the schedule captures
- [ ] 4.4 Register the collector and the model in `scripts/pipeline.py`, reading captured pages by default and the network under `--live`, with `as_of` fixed on the offline path so the demo is reproducible

## 5. Composition and wiring

- [ ] 5.1 Point `packages/composition/recipes/default.yaml` at `recent-goals-total` alone, with a comment recording that the weights question is unanswerable until there is a label (Zone C, design D10)
- [ ] 5.2 Run `uv lock` for the two new packages and commit the result

## 6. Verification

- [ ] 6.1 Everything CI runs, in the order `CLAUDE.md` lists it, including the dependency check proving the model stayed pure and the collector's impurity is allowed
- [ ] 6.2 `./scripts/demo.sh` with no arguments, on the offline path, producing scores for the fixture matches
- [ ] 6.3 `./scripts/demo.sh --live`, producing scores for real upcoming matches, and recording the run's coverage and cost against the numbers in design D3

## 7. Documentation

- [ ] 7.1 `docs/STUBS.md`: the Ingestion row stops claiming no model scores on a live run; the Collectors row gains the first collector that reads a source; `recent-goals-total` is recorded as real but unvalidated, not as a placeholder
- [ ] 7.2 `CLAUDE.md`: update the project-state paragraph, which currently says both models predict nothing and that nothing a model reads is real
- [ ] 7.3 READMEs for the two new packages, saying what they fetch and what they claim
