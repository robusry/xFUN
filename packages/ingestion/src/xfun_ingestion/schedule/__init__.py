"""Acquiring the set of upcoming matches, before a slate exists.

This is the one part of ingestion permitted to touch the network, and the reason it
is not a collector. `Collector.collect(slate)` takes a slate as its input; this
produces the matches a slate is assembled from, so there is no way to express it
through that interface without passing a slate it would have to ignore.

External access therefore lives in two tiers, ordered by when they run relative to
the slate: the schedule source before it, collectors after it. Models and the API
may touch neither.

Nothing here maps the source's identifiers onto this project's canonical ones. That
translation is deliberately separate, because the source's ids are stable only
within the source.
"""

from .canonical import (
    CanonicalIdError,
    canonical_payload,
    league_id,
    match_id,
    slugify,
    team_id,
)
from .parse import (
    ScheduleParseError,
    SourceMatch,
    competition_groups,
    parse_schedule,
    sports_events,
)

__all__ = [
    "CanonicalIdError",
    "ScheduleParseError",
    "SourceMatch",
    "canonical_payload",
    "competition_groups",
    "league_id",
    "match_id",
    "parse_schedule",
    "slugify",
    "sports_events",
    "team_id",
]
