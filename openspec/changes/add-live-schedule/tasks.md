## 1. Golden fixtures for the source

- [x] 1.1 Capture real goal.com responses for two dates into `contracts/fixtures/schedule/`, one dense and one sparse, keeping the JSON-LD blocks and the competition-grouped page state
- [x] 1.2 Add a malformed capture — page state present but the expected structure missing — so the parse-failure path of `schedule-acquisition` is testable without the network
- [x] 1.3 Record in `contracts/README.md` that these fixtures are captured third-party responses, not authored contract examples, and may be refreshed wholesale

## 2. Parsing the source

- [x] 2.1 Parse schema.org `SportsEvent` JSON-LD for match identity, UTC kickoff, and team names
- [x] 2.2 Parse the competition-grouped page state for `competition.id`, `competition.name`, `competition.area.name`, and `tvChannels`
- [x] 2.3 Join the two by match, keeping identity sourced from JSON-LD and competition/providers from page state per design D5
- [x] 2.4 Test both parsers against the golden fixtures, including a competition-name collision (the `Premier League` bucket spans six countries and only the id separates them)

## 3. Canonical identity

- [x] 3.1 Resolve the open question in design: decide how source team and competition ids map to canonical ids, and record the decision in the design before writing the mapping
- [x] 3.2 Implement the mapping and write canonical league, team, and match entities from a parsed response
- [x] 3.3 Test that re-running acquisition over an overlapping window converges rather than duplicating

## 4. The rights table

- [ ] 4.1 Add the `league -> US providers` table as Zone C configuration, with a `verified_on` date required per entry
- [ ] 4.2 Seed the leagues the source leaves empty — MLS, MLS NEXT Pro, Liga MX — each verified against the league's own published rights announcement, not against an aggregator
- [ ] 4.3 Fail table loading when an entry omits `verified_on`, per the `schedule-acquisition` spec
- [ ] 4.4 Implement two-step provider resolution: per-match data first, table second, `unknown` third

## 5. Availability persistence

- [ ] 5.1 Add `infra/migrations/004_availability.sql` for per-match availability status and providers
- [ ] 5.2 Write availability during acquisition and read it in `xfun_store`
- [ ] 5.3 Replace the hardcoded `{"status": "unknown", "providers": []}` at `packages/api/src/xfun_api/main.py:88` with a store read
- [ ] 5.4 Confirm `scripts/check_api_conformance.py` still passes — `openapi.yaml` already defines `Availability`, so the shape must not change

## 6. The slate rule

- [ ] 6.1 Add `us-watchable` to `assemble_slate()`: kickoff within 10 days of run time, and at least one known provider
- [ ] 6.2 Keep `league-allowlist` reachable for the fixture path, which has no provider data
- [ ] 6.3 Record the rule and window bounds on `Selection`, and validate the slate against `contracts/schemas/slate.json` (`us-watchable` is already in the enum)
- [ ] 6.4 Test the boundary cases from the spec: known provider inside the window, no provider inside it, known provider beyond it, and a window with nothing watchable

## 7. Failure as a first-class outcome

- [ ] 7.1 Record schedule-source failure with a reason, distinctly from a window containing no watchable match
- [ ] 7.2 Ensure a failed acquisition does not present stale canonical matches as freshly acquired
- [ ] 7.3 Test unreachable, unauthorised, and unparseable sources against the malformed fixture from 1.2

## 8. Wiring and the opt-in flag

- [ ] 8.1 Add live acquisition behind an explicit flag in `scripts/pipeline.py`, defaulting to fixtures
- [ ] 8.2 Surface the flag in `scripts/demo.sh` without making it the default path
- [ ] 8.3 Add the HTTP client dependency to `packages/ingestion/pyproject.toml`, run `uv lock`, and commit the lockfile
- [ ] 8.4 Confirm `scripts/check_dependencies.py` still passes, and extend it so models and the API may not import the schedule source — the rule the `data-collection` delta adds

## 9. Correcting the architecture rule in every place it is stated

- [ ] 9.1 `CLAUDE.md`: collectors are no longer "the ONLY tier that may touch the network" — restate as the two tiers of design D1
- [ ] 9.2 `docs/architecture.md` and `docs/zones.md`: same correction, so the rule is not true in three places and false in a fourth
- [ ] 9.3 `docs/STUBS.md`: mark **Ingestion**, **The slate rule**, and **Broadcast availability** as partly resolved — not deleted, since acquisition establishes matches and availability but nothing a model reads
- [ ] 9.4 `docs/STUBS.md`: add goal.com as an unofficial third-party source with no API contract, naming the six rejected alternatives from design D2 so the survey is not repeated
- [ ] 9.5 PLACEHOLDER: the rights table is hand-maintained and will go stale when rights move between seasons. Record it in `docs/STUBS.md`; no follow-up change is proposed, because no surveyed source can replace it

## 10. Verification

- [ ] 10.1 Run everything CI runs, in order, per `CLAUDE.md`
- [ ] 10.2 Run the pipeline live against the real source and confirm the slate holds real matches with real providers
- [ ] 10.3 Confirm the fixture path still runs on a clone with no network and no credentials
- [ ] 10.4 Confirm every match is returned with a recorded skip reason and no composed score, since no model's declared features are satisfied — the expected outcome, not a regression

## 11. Follow-ups this change deliberately defers

- [ ] 11.1 Record that model input remains entirely on fixture data, so no model scores, and that supplying it is expected to fall to the collector tier rather than to acquisition
- [ ] 11.2 Record that `add-broadcast-availability` is fully discharged by this change, and update any reference that still names it as pending
- [ ] 11.3 Record the unresolved question of whether `unknown` availability stays reachable once `us-watchable` filters on a known provider
