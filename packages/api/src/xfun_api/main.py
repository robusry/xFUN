"""The read-only public API.

Three things this module is careful about:

**It never runs a model.** Scores are precomputed in batch and read from the
store. There is no model import anywhere in this package, and CI asserts it. A
broken model degrades score freshness, not availability.

**Calibration and composition happen at read time.** Because the caller chooses
the cohort per request, a calibrated score is not a property of a stored row. Both
are arithmetic over rows that already exist, so this is cheap.

**Every response says which cohort and which alias produced it.** A calibrated
score without its cohort is uninterpretable, and an alias can be repointed, so a
client that does not record what it asked for cannot reproduce what it got.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from xfun_composition import (
    AliasNotFound,
    PolicyNotImplemented,
    compose_match,
)
from xfun_runtime.calibration import CohortNotImplemented, calibrate

from .context import ApiContext, get_context

CohortName = Literal["window", "league", "season", "global"]

app = FastAPI(
    title="xFUN API",
    version="0.1.0",
    description=(
        "Read-only access to entertainment scores for upcoming soccer matches.\n\n"
        "Validated against contracts/openapi.yaml, which is the source of truth."
    ),
)

# The skeleton's web page runs on a different port under Vite.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(CohortNotImplemented)
async def _cohort_not_implemented(_request, exc: CohortNotImplemented) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "title": "Calibration cohort not implemented",
            "status": 501,
            "detail": str(exc),
        },
    )


@app.exception_handler(PolicyNotImplemented)
async def _policy_not_implemented(_request, exc: PolicyNotImplemented) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "title": "Composition policy not implemented",
            "status": 501,
            "detail": str(exc),
        },
    )


Ctx = Annotated[ApiContext, Depends(get_context)]


def _match_payload(snapshot) -> dict[str, Any]:
    return {
        "match_id": snapshot.match_id,
        "league": snapshot.data["league"]["name"],
        "kickoff_utc": snapshot.kickoff_utc,
        "home_team": snapshot.data["home_team"]["name"],
        "away_team": snapshot.data["away_team"]["name"],
        # Broadcast availability is a separate concern with its own cadence, and
        # "unknown" is a first-class answer. A confidently wrong provider is worse
        # than an honest gap. Replaced by the add-broadcast-availability change.
        "availability": {"status": "unknown", "providers": []},
    }


def _resolve_alias(ctx: ApiContext, alias: str):
    try:
        return ctx.aliases.resolve(alias)
    except AliasNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@app.get("/v1/matches", operation_id="listMatches", tags=["matches"])
def list_matches(
    ctx: Ctx,
    date_from: Annotated[str, Query(alias="from")],
    date_to: Annotated[str, Query(alias="to")],
    score: str = "default",
    cohort: CohortName = "window",
) -> dict[str, Any]:
    """Matches in a date range, ranked by composed score."""
    target = _resolve_alias(ctx, score)
    snapshots = ctx.snapshots(date_from=date_from, date_to=date_to)
    match_ids = [s.match_id for s in snapshots]

    calibration = calibrate(ctx.scores(match_ids), cohort=cohort)
    by_match = calibration.by_match()
    recipe = ctx.recipe_for(target)

    ranked = []
    for snapshot in snapshots:
        scores = by_match.get(snapshot.match_id, ())
        composed = ctx.compose(scores, target, recipe)
        ranked.append({"match": _match_payload(snapshot), "composed": composed.to_dict()})

    # Unscored matches sort last rather than being dropped: "no score, and here is
    # why" is more useful than a silently shorter list.
    ranked.sort(key=lambda r: (r["composed"]["value"] is None, -(r["composed"]["value"] or 0)))

    return {
        "cohort": calibration.cohort.to_dict(),
        "score_alias": target.to_dict(),
        "matches": ranked,
    }


@app.get(
    "/v1/matches/{match_id}/scores",
    operation_id="getMatchScores",
    tags=["matches"],
)
def get_match_scores(
    ctx: Ctx,
    match_id: str,
    score: str = "default",
    cohort: CohortName = "window",
) -> dict[str, Any]:
    """Every model's calibrated score for one match, plus the composed score.

    Per-model scores are exposed alongside the composite so a consumer can build
    its own blend rather than depending on ours.
    """
    target = _resolve_alias(ctx, score)

    snapshot = ctx.snapshot(match_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Unknown match {match_id!r}")

    # Calibration needs the whole window as its population, not just this match --
    # a percentile rank against a single value is meaningless.
    calibration = calibrate(ctx.scores(), cohort=cohort)
    scores = calibration.by_match().get(match_id, ())
    composed = ctx.compose(scores, target, ctx.recipe_for(target))

    return {
        "match": _match_payload(snapshot),
        "cohort": calibration.cohort.to_dict(),
        "score_alias": target.to_dict(),
        "composed": composed.to_dict(),
        "model_scores": [
            {
                "model_id": s.model_id,
                "model_version": s.model_version,
                "raw_score": s.raw_score,
                "calibrated_score": s.calibrated_score,
                "components": dict(s.components),
            }
            for s in sorted(scores, key=lambda s: s.model_id)
        ],
    }


@app.get("/v1/registry", operation_id="getRegistry", tags=["registry"])
def get_registry(ctx: Ctx) -> dict[str, Any]:
    """What exists: models, compositions, and aliases.

    Lets a consumer discover the parts and compose its own blend from per-model
    scores, instead of being limited to the aliases we happen to publish.
    """
    return {
        "models": ctx.registered_models(),
        "compositions": [r.to_dict() for r in ctx.recipes.values()],
        "aliases": [a.to_dict() for a in ctx.aliases.all()],
    }
