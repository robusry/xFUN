"""The code that actually fetches, against a recorded exchange.

Everything between "make a request" and "have bytes in hand" -- client construction,
the headers this project sends, timeouts, redirect following, and the translation of
transport and status failures into `ScheduleSourceError`. Until this file existed,
none of it was exercised by anything: the parsers were tested thoroughly against
captured bytes, and the code that goes and gets those bytes was tested not at all,
while being the only path a real run takes.

WHAT THIS DOES NOT ESTABLISH, and must not be read as establishing:

- that goal.com is reachable
- that goal.com still returns this shape, or these headers
- that a live run will succeed

It drives the shipped client against a recording. The recording goes stale silently
the moment the source changes, and nothing here will notice. A source shape change is
caught by the parser failing loudly during a real run, and by nothing earlier. That
limit is deliberate -- a CI check that contacted goal.com would make every build
depend on a third party -- and it is the reason a nightly non-blocking live check was
argued for separately rather than folded in here.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from xfun_ingestion.schedule.source import (
    ScheduleSourceError,
    fetch_page,
    page_client,
    schedule_url,
)
from xfun_runtime.paths import captures_dir

RECORDED = json.loads(
    (captures_dir() / "goal-com" / "http" / "fixtures-page-200.json").read_text()
)

DAY = date(2026, 8, 26)
BODY = "<!doctype html><html><body>a page</body></html>"


def transport_returning(status: int, body: str = BODY, **kwargs):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, text=body, **kwargs)

    return httpx.MockTransport(handler), seen


def transport_raising(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return httpx.MockTransport(handler)


# --- the client that ships ---------------------------------------------------


def test_the_request_carries_the_honest_user_agent():
    """Identifying the caller is a policy, not a detail.

    Several sources surveyed in the archived add-live-schedule design, D2, are
    reachable only by claiming to be a browser, and were rejected for that reason.
    A change that quietly started spoofing one would be a change of policy.
    """
    transport, seen = transport_returning(200)
    with page_client(transport=transport) as client:
        fetch_page(client, DAY)

    sent = seen[0].headers["user-agent"]
    assert sent == RECORDED["request_headers"]["user-agent"]
    assert sent.startswith("xfun-schedule-acquisition/")
    assert "github.com/robusry/xFUN" in sent
    assert "Mozilla" not in sent, "this client must not pretend to be a browser"


def test_the_client_follows_redirects_and_bounds_its_wait():
    transport, _ = transport_returning(200)
    with page_client(transport=transport) as client:
        assert client.follow_redirects is True
        assert client.timeout.connect == 10.0
        assert client.timeout.read == 30.0


def test_the_recorded_exchange_is_the_url_the_code_builds():
    """If the URL shape changes, the recording is describing something else."""
    assert RECORDED["url"] == schedule_url(DAY)
    assert RECORDED["status"] == 200


# --- what comes back ---------------------------------------------------------


def test_a_successful_response_yields_its_text():
    transport, seen = transport_returning(200)
    with page_client(transport=transport) as client:
        assert fetch_page(client, DAY) == BODY

    assert str(seen[0].url) == schedule_url(DAY)


def test_a_redirect_is_followed_to_the_page():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fixtures/2026-08-26"):
            return httpx.Response(302, headers={"location": "https://www.goal.com/moved"})
        return httpx.Response(200, text=BODY)

    with page_client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_page(client, DAY) == BODY


# --- failure is not absence --------------------------------------------------


def test_a_transport_failure_names_the_problem():
    """The distinction the whole collector tier is built on: a failure to reach the
    source is not a source with nothing to say."""
    transport = transport_raising(httpx.ConnectError("no route to host"))
    with page_client(transport=transport) as client, pytest.raises(ScheduleSourceError) as exc:
        fetch_page(client, DAY)

    assert "could not reach" in str(exc.value)
    assert schedule_url(DAY) in str(exc.value)
    assert "no route to host" in str(exc.value)


def test_a_timeout_is_a_source_failure_not_an_empty_page():
    transport = transport_raising(httpx.ReadTimeout("timed out"))
    with page_client(transport=transport) as client, pytest.raises(ScheduleSourceError):
        fetch_page(client, DAY)


def test_a_refusal_says_stop_rather_than_retry():
    """403 carries a policy, not just an error string.

    Every source rejected in D2 answers this way, and a caller that retried past it
    would be defeating an access control on this project's behalf.
    """
    transport, _ = transport_returning(403)
    with page_client(transport=transport) as client, pytest.raises(ScheduleSourceError) as exc:
        fetch_page(client, DAY)

    message = str(exc.value)
    assert "403" in message
    assert "do not work around it" in message


def test_a_server_error_names_its_status():
    transport, _ = transport_returning(503)
    with page_client(transport=transport) as client, pytest.raises(ScheduleSourceError) as exc:
        fetch_page(client, DAY)

    assert "503" in str(exc.value)


def test_a_not_found_is_a_failure_not_a_quiet_week():
    transport, _ = transport_returning(404)
    with page_client(transport=transport) as client, pytest.raises(ScheduleSourceError) as exc:
        fetch_page(client, DAY)

    assert "404" in str(exc.value)
