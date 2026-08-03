"""Fetching schedule pages, and acquiring a window from them.

This module is the one place in the project that makes an outbound request before a
slate exists. Everything it depends on is unofficial: goal.com publishes no API, no
contract, and no stability promise. Its `robots.txt` permits this -- `User-agent: *`
with `Allow: /` and no disallowed paths -- which is the reason it was chosen over
better data behind a refusal. See design D2.

Because none of that is guaranteed, breakage is treated as an expected outcome
rather than an exception. Failing to reach the source and finding nothing worth
watching both leave an empty slate; the run record is what tells them apart, so
producing that record is as much this module's job as fetching is.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, timedelta

import httpx

from .parse import ScheduleParseError, SourceMatch, parse_schedule

__all__ = [
    "SOURCE_ID",
    "ScheduleSourceError",
    "fetch_window",
    "schedule_url",
    "window_dates",
]

SOURCE_ID = "goal.com"

_URL = "https://www.goal.com/en-us/fixtures/{date}"

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_HEADERS = {
    # Identifies the caller honestly. The alternative -- claiming to be a browser --
    # is what several of the sources rejected in D2 require, and is precisely why
    # they were rejected.
    "User-Agent": "xfun-schedule-acquisition/0.1 (+https://github.com/robusry/xFUN)",
    "Accept": "text/html",
}


class ScheduleSourceError(Exception):
    """The source could not be consulted, or could not be trusted.

    Deliberately NOT raised for a date with no matches. That is a real answer, and
    conflating it with this would make a quiet week indistinguishable from an
    outage -- the exact confusion `schedule_run` exists to prevent.
    """


def schedule_url(day: date) -> str:
    return _URL.format(date=day.isoformat())


def window_dates(start: datetime, days: int) -> tuple[date, ...]:
    """Every date the window touches, inclusive of both ends.

    A window of N days spans N+1 dates whenever it does not start at midnight,
    which it never does in practice -- the window runs from the moment of the run.
    Fetching the extra date is cheaper than missing a match on the final evening.
    """
    first = start.date()
    last = (start + timedelta(days=days)).date()
    span = (last - first).days
    return tuple(first + timedelta(days=offset) for offset in range(span + 1))


def _fetch_one(client: httpx.Client, day: date) -> str:
    url = schedule_url(day)
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        raise ScheduleSourceError(f"could not reach {url}: {exc}") from None

    if response.status_code == 403:
        # Called out separately because it is the failure that means "stop", not
        # "retry". Every source rejected in D2 answers this way, and working around
        # it would mean defeating an access control rather than fixing a bug.
        raise ScheduleSourceError(
            f"{url} refused the request (403). The source may have started "
            f"blocking automated access; do not work around it."
        )
    if response.status_code >= 400:
        raise ScheduleSourceError(f"{url} returned HTTP {response.status_code}")

    return response.text


def fetch_window(
    start: datetime | None = None,
    days: int = 10,
    *,
    client: httpx.Client | None = None,
) -> tuple[SourceMatch, ...]:
    """Every match the source lists across the window, in no particular order.

    Raises `ScheduleSourceError` if any date could not be fetched or parsed. All or
    nothing is deliberate: a partial window looks like a thin week, and the caller
    would have no way to tell that a Saturday was silently missing.

    Filtering to the window itself happens later, in slate assembly. This returns
    whole dates because that is the granularity the source addresses.
    """
    start = start or datetime.now(UTC)
    owned = client is None
    client = client or httpx.Client(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True)

    matches: list[SourceMatch] = []
    try:
        for day in window_dates(start, days):
            html = _fetch_one(client, day)
            try:
                matches.extend(parse_schedule(html))
            except ScheduleParseError as exc:
                raise ScheduleSourceError(f"{schedule_url(day)}: {exc}") from None
    finally:
        if owned:
            client.close()

    return tuple(matches)


def matches_from_pages(pages: Sequence[str]) -> Iterator[SourceMatch]:
    """Parse already-fetched pages. Used by tests and by the capture tooling, so
    that everything downstream of the network can be exercised without it."""
    for html in pages:
        yield from parse_schedule(html)
