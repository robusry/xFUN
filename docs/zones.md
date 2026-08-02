# Zones: when a change needs specs

Requiring specs for every change is how spec-driven development dies on a mixed
team. So the obligation depends on what you touched.

## The table

| Zone | Paths | Obligation |
|---|---|---|
| **A** | `contracts/`<br>`packages/scoring-contract/`<br>`packages/scoring-runtime/`<br>`packages/composition/src/` | **Always.** A change with spec deltas, every time. |
| **B** | `packages/api/`<br>`packages/ingestion/`<br>`packages/models/<id>/` behavior<br>`packages/collectors/<id>/` behavior<br>`packages/evaluation/` | **On observable behavior change.** New endpoint, changed response, new data source, changed model output → yes. Refactor, perf, bugfix-to-match-spec → no. |
| **C** | `packages/web/`, `packages/mobile/`<br>`infra/`, CI, dependency bumps<br>`packages/composition/recipes/*.yaml` | **None.** Hand-edit freely. If a change exists anyway, archive with `--skip-specs`. |

Zone A is deliberately small — roughly the code everyone depends on and everyone
will argue about.

## The carve-out that matters most

```
  packages/composition/src/       ZONE A  ← the mechanism
  packages/composition/recipes/   ZONE C  ← the values
```

The collector tier splits the same way, for the same reason:

```
  scoring-runtime/collectors.py   ZONE A  ← resolution, the joins, the registry
  scoring-runtime/join.py         ZONE A  ← adding a fourth entity kind is a
                                            new join, and a spec change
  packages/collectors/<id>/       ZONE B  ← one source; specs on behaviour change
```

Adding a collector for a new source is Zone B — it changes what data exists, not
what the platform does with it. Changing how entity-keyed output is joined onto
matches is Zone A, because every model's declared paths depend on it.

Adding a new missing-model policy changes what a composed score *means*: Zone A,
specs required. Changing `over-under-lean: 0.5` to `0.6` does not: Zone C, a
config diff.

Composition weights are expected to change repeatedly. Requiring an OpenSpec
change for each tweak would stop anyone proposing them, which is worse than the
churn. **Spec the machinery permanently; leave the numbers free to move weekly.**

## Two ways in, one destination

```
  SPEC-FIRST (Zone A, larger Zone B work)

    branch ──▶ openspec new change ──▶ proposal ──▶ specs ──▶ design ──▶ tasks
                                                                          │
                                                                    implement
                                                                          │
                                                        rebase + archive ─┤
                                                                          │
                                                              open the PR ▼
                                                                       main
  CODE-FIRST (hand edits, hotfixes, exploration)                          ▲
                                                                          │
    code merges ──▶ `spec-debt` label ──▶ capture change ─────────────────┘
                                          (describes what IS now)
```

**A capture change is a legitimate contribution, not a confession.** If
back-filling feels like punishment, nobody does it and the specs rot instead.

### Writing a capture change

Say PR #47 added a response field to `/v1/matches` under time pressure, with the
`spec-debt` label.

```bash
git switch -c capture/add-kickoff-local-time
openspec new change capture-add-kickoff-local-time
```

**proposal.md** — thin. It is describing what happened, not proposing it:

> ## Why
> PR #47 added a `kickoff_local` field to match responses so the web page could
> show local kickoff times without a second round trip. It merged with the
> `spec-debt` label; this captures the behavior into specs.
>
> ## What Changes
> - `/v1/matches` and `/v1/matches/{id}/scores` return `kickoff_local`
>
> ## Capabilities
> ### Modified Capabilities
> - `public-api`: match payloads carry a local-time field

**specs/public-api/spec.md** — the delta, in the present tense, describing what is
already true:

> ## MODIFIED Requirements
>
> ### Requirement: Match payloads identify the fixture and when it starts
> ...full updated requirement text, with the new field...
>
> #### Scenario: A client renders a kickoff time
> - **WHEN** a match payload is returned
> - **THEN** it carries both `kickoff_utc` and `kickoff_local`

Then `openspec validate --strict`, archive, open a PR, and remove the `spec-debt`
label from #47.

Ten minutes, not an hour — the design questions were settled by the code that
already exists.

## How drift is caught

The `spec-drift` job flags a pull request touching Zone A/B paths with no
`openspec/` changes. It **does not block**: applying the `spec-debt` label lets it
through with a warning.

That is deliberate. A blocking check on a fast-moving team gets disabled within
weeks; a label that shows up in a query does not. What *does* block is
`openspec validate` — a malformed spec helps nobody.

**Drift you can count is debt. Drift you cannot see is rot.**

## Clearing spec debt

**No cadence, no ritual, no owner.** This is an informal project; debt gets cleared
when someone has the time, not on a schedule.

To see what is outstanding:

```bash
gh pr list --label spec-debt          # what has drifted
openspec list --specs                 # what exists
openspec doctor                       # relationship health
```

To clear an item: write and archive a capture change (worked example above), or
explicitly record that it needs no specs, then remove the label.

Because there is no scheduled pass, **the countable backlog is the only control
left** — which is precisely why the `spec-debt` label is not optional. A backlog
that grows steadily over months is the signal to act: either the zones are too
wide, or the project has outgrown doing this opportunistically.
