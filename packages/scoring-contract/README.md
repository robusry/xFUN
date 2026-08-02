# scoring-contract

**Real, not placeholder.** This is the interface every model implements.

Types and one hash function. No dependencies, no I/O — every model depends on this
package, so anything added here is imposed on all of them.

```python
from xfun_contract import MatchSnapshot, Model, ScoreResult

class MyModel:
    model_id = "my-model"
    model_version = "0.1.0"
    required_features = ("odds.total_line",)
    description = "What signal this claims to capture."

    def score(self, snapshot: MatchSnapshot) -> ScoreResult:
        line = snapshot.feature("odds.total_line")
        return ScoreResult(raw_score=line, components={"total_line": line})
```

## What the constraints buy

| Constraint | Why |
|---|---|
| Pure — no network, database, filesystem, or clock | Testable on fixtures, reproducible years later, runnable in a notebook |
| Declares `required_features` | Coverage gaps skip a model for a match instead of blocking the pipeline |
| Never imports another model | Keeps scoring a flat fan-out; a graph would make backfills ordered and composition expensive to reverse |
| Returns `ScoreResult`, not `ModelScore` | The runtime attaches identity and provenance, so a model cannot get its own metadata wrong |

## raw_score is deliberately unconstrained

A probability, a z-score, an arbitrary index — whatever suits the model. **Models
must not normalise.** The platform percentile-ranks raw scores within a
caller-chosen cohort to produce comparable 0–100 values.

Two models' raw scores are not comparable to each other. Averaging them directly
would produce plausible nonsense, which is why calibration is the platform's job
and not each model's.

## Zone A

Changes here always require an OpenSpec change with spec deltas. See
`openspec/specs/scoring-contract/` for the normative requirements.
