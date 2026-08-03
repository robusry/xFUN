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

from .acquire import acquire_window, store_matches
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
from .rights import (
    Availability,
    LeagueRights,
    RightsTableError,
    default_rights_path,
    load_rights,
    resolve_providers,
)
from .source import (
    SOURCE_ID,
    ScheduleSourceError,
    fetch_window,
    schedule_url,
    window_dates,
)

__all__ = [
    "SOURCE_ID",
    "Availability",
    "CanonicalIdError",
    "LeagueRights",
    "RightsTableError",
    "ScheduleParseError",
    "ScheduleSourceError",
    "SourceMatch",
    "acquire_window",
    "canonical_payload",
    "competition_groups",
    "default_rights_path",
    "fetch_window",
    "league_id",
    "load_rights",
    "match_id",
    "parse_schedule",
    "resolve_providers",
    "schedule_url",
    "slugify",
    "sports_events",
    "store_matches",
    "team_id",
    "window_dates",
]
