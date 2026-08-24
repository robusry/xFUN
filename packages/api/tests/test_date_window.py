"""The served date window: optional bounds, and a response that says what it did.

The property worth protecting is that a caller who supplied no dates can still tell
what it got. An unbounded request that silently returned a subset, or a bounded one
that reported the request back rather than the data, would both look correct and be
uninterpretable.
"""

from __future__ import annotations

import pytest

pytest_plugins = ["packages.api.tests.test_end_to_end"]


def _window(client, params: dict[str, str] | None = None):
    # A dict rather than kwargs because `from` is a Python keyword.
    response = client.get("/v1/matches", params=params or {})
    assert response.status_code == 200
    return response.json()


def test_no_range_returns_everything_and_says_so(api_client):
    body = _window(api_client)

    assert body["matches"], "an unbounded request should return the store's matches"
    assert body["window"]["from"] is not None
    assert body["window"]["to"] is not None
    assert body["window"]["from"] <= body["window"]["to"]


def test_the_window_describes_the_data_not_the_request(api_client):
    """A request wider than the data reports the data's range.

    The caller asked about a decade; what it received spans days. Echoing the
    request back would be technically true and useless.
    """
    everything = _window(api_client)
    wide = _window(api_client, {"from": "2020-01-01", "to": "2030-12-31"})

    assert wide["window"] == everything["window"]
    assert len(wide["matches"]) == len(everything["matches"])


def test_a_bounded_request_narrows_both_matches_and_window(api_client):
    everything = _window(api_client)
    narrow = _window(api_client, {"from": "2026-08-15", "to": "2026-08-15"})

    assert len(narrow["matches"]) < len(everything["matches"])
    assert narrow["window"]["from"].startswith("2026-08-15")
    assert narrow["window"]["to"].startswith("2026-08-15")


def test_one_bound_leaves_the_other_side_unbounded(api_client):
    everything = _window(api_client)

    lower_only = _window(api_client, {"from": "2026-08-17"})
    upper_only = _window(api_client, {"to": "2026-08-16"})

    assert lower_only["window"]["to"] == everything["window"]["to"]
    assert upper_only["window"]["from"] == everything["window"]["from"]
    assert len(lower_only["matches"]) + len(upper_only["matches"]) == len(
        everything["matches"]
    ), "the two halves should partition the slate"


def test_an_empty_result_reports_a_null_window_rather_than_an_error(api_client):
    """Not an error and not an invented range.

    Asking about a period with no matches is a legitimate question with the answer
    "none". A 404 would imply the endpoint was wrong; a fabricated window would
    imply data existed.
    """
    body = _window(api_client, {"from": "2019-01-01", "to": "2019-01-02"})

    assert body["matches"] == []
    assert body["window"] == {"from": None, "to": None}
    assert body["cohort"]["definition"] == "window", "the cohort is still stated"


@pytest.mark.parametrize("params", [{}, {"from": "2026-08-01"}, {"to": "2026-08-31"}])
def test_every_response_states_its_window_however_it_was_asked(api_client, params):
    body = _window(api_client, params)
    assert "window" in body, "the window is required on every response, not optional"
    assert set(body["window"]) == {"from", "to"}
