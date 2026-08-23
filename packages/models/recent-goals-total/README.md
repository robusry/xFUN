# recent-goals-total

**Real inputs. Unvalidated hypothesis.** Not a placeholder — and not evidence either.

Scores a match as the goals the home side scored in its last five completed matches,
plus the goals the away side scored in its last five.

```
raw_score = signals.form.home.goals_scored_last_5
          + signals.form.away.goals_scored_last_5
```

## What is real about it

Every input is a goal somebody really scored in a match that was really played,
collected by `packages/collectors/recent-results/` from dated schedule pages. This is
the first model in the repository of which that is true, and the reason a live run now
produces scores instead of a page of skip reasons.

## What is not

Nothing here has been tested against whether the matches were entertaining, because
there is no ground-truth label for that — the project's central open question, recorded
in `openspec/config.yaml`. Until `add-evaluation-harness` exists, this model is an
argument that goals are fun to watch, not a finding.

It is also plainly wrong in ways worth stating before somebody discovers them:

- It ignores **how close** the match will be. A 5–0 procession between two free-scoring
  sides outranks a tense 1–1. `odds-spread` makes exactly the opposite mistake.
- It ignores **defence**. Scoring three and conceding four looks like scoring three and
  keeping a clean sheet.
- It ignores **who the goals were against**. Five past a relegated side count as five
  past the champions.
- It **adds** the two sides rather than weighting them, so 25 + 0 scores the same as
  12 + 13. The second is almost certainly the better watch. The sum is what the team
  specified; a weighting invented here would be a second untested hypothesis smuggled
  in under the first.

## Coverage

Both sides are required, so a match is scored only when both teams have five completed
matches inside the collector's 120-day bound. Between seasons many do not, and those
matches come back with a recorded skip reason and no score. That is the partial-coverage
path working, not a fault — see design D5 of `add-recent-goals-model` for why a partial
sum would be worse than nothing.

`raw_score` is the goal total itself and is deliberately unnormalised. Models must not
normalise; the platform percentile-ranks per (model_id, model_version) inside a
caller-chosen cohort.
