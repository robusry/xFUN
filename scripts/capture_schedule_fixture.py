#!/usr/bin/env python3
"""Capture a goal.com schedule page into a golden fixture.

A development tool, not part of the pipeline and not run by CI. It exists so the
fixtures in `contracts/fixtures/schedule/` can be refreshed reproducibly instead of
hand-pasted, because they are captured third-party responses whose upstream will
change without notice.

The capture is REDUCED, not raw. A live page is roughly 3 MB, almost all of it
markup, advertising, and competitions nobody in this product cares about. What is
kept is the two things the parsers read -- the schema.org JSON-LD blocks and the
competition-grouped page state -- with the state trimmed to a chosen set of
competitions. The result is still the source's own bytes for those competitions; it
is a subset, not a paraphrase.

Trimming is deliberate rather than incidental. A fixture that keeps every one of 125
competitions would be slower to read than the code it tests, and would have to be
regenerated wholesale every time an unrelated league changed. Naming the
competitions makes the fixture's coverage a stated choice that a reviewer can check
against the scenarios in the spec.

Usage:
    python scripts/capture_schedule_fixture.py 2026-08-08 --name dense
    python scripts/capture_schedule_fixture.py 2026-08-12 --name sparse --all-competitions

Uses stdlib urllib on purpose: this tool must not be the reason the repository grows
an HTTP dependency, and it runs on a developer's machine rather than in the pipeline.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "contracts" / "fixtures" / "schedule"

SOURCE_URL = "https://www.goal.com/en-us/fixtures/{date}"

# Competitions the fixture keeps, chosen to exercise the scenarios in
# specs/schedule-acquisition/spec.md rather than to be representative:
#
#   USL Championship      per-match providers present -- the ordinary case
#   MLS NEXT Pro          no providers -- resolution must fall to the rights table
#   Liga MX               no providers -- same, and absent from other sources entirely
#   Premier League (ENG)  providers present AND split rights, so per-match must win
#   Premier League (KAZ)  same display name, different competition -- the collision
#                         that makes name-based matching wrong
KEPT_COMPETITIONS = {
    "c1d9p6b2e9zr5tqlzx3ktjplg": "USL Championship",
    "5qmjkpvi92vrzdcb2knassjkk": "MLS NEXT Pro",
    "2hsidwomhjsaaytdy9u5niyi4": "Liga MX",
    "2kwbbcootiqqgmrzs6o5inle5": "Premier League (England)",
    "9ikchyu9fb8bvx0s673jofj6s": "Premier League (Kazakhstan)",
}

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)
LD_JSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)


def fetch(date: str, local: Path | None) -> str:
    if local:
        return local.read_text(encoding="utf-8", errors="replace")
    url = SOURCE_URL.format(date=date)
    request = urllib.request.Request(url, headers={"Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def competition_groups(html: str) -> list[dict[str, Any]]:
    """The page state, as competition groups each holding their matches."""
    match = NEXT_DATA_RE.search(html)
    if match is None:
        raise SystemExit("no __NEXT_DATA__ in page; the source changed shape")
    data = json.loads(match.group(1))
    try:
        return data["props"]["pageProps"]["content"]["liveScores"]
    except KeyError as exc:
        raise SystemExit(f"page state no longer holds liveScores: {exc}") from None


def sports_events(html: str) -> list[dict[str, Any]]:
    """The schema.org blocks, which carry identity and timing but no competition."""
    events = []
    for block in LD_JSON_RE.findall(html):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("@type") == "SportsEvent":
            events.append(parsed)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", help="fixture date, YYYY-MM-DD")
    parser.add_argument("--name", required=True, help="fixture basename, e.g. dense")
    parser.add_argument(
        "--all-competitions",
        action="store_true",
        help="keep every competition rather than the chosen set",
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="read a saved page instead of fetching, for offline capture",
    )
    args = parser.parse_args()

    html = fetch(args.date, args.from_file)
    groups = competition_groups(html)
    events = sports_events(html)

    if args.all_competitions:
        kept = groups
    else:
        kept = [
            g
            for g in groups
            if (g.get("competition") or {}).get("id") in KEPT_COMPETITIONS
        ]

    # Keep only the JSON-LD blocks for matches we kept. The two halves are joined on
    # team names and kickoff, so a JSON-LD block with no surviving match is noise.
    kept_keys = {
        (
            (m.get("teamA") or {}).get("name"),
            (m.get("teamB") or {}).get("name"),
            m.get("startDate"),
        )
        for g in kept
        for m in (g.get("matches") or [])
    }
    kept_events = [
        e
        for e in events
        if (
            (e.get("homeTeam") or {}).get("name"),
            (e.get("awayTeam") or {}).get("name"),
            e.get("startDate"),
        )
        in kept_keys
    ]

    match_count = sum(len(g.get("matches") or []) for g in kept)
    with_providers = sum(
        1 for g in kept for m in (g.get("matches") or []) if m.get("tvChannels")
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.date}-{args.name}.html"

    # Rebuilt as a minimal document rather than the original markup. The parsers read
    # script tags, so this is a faithful input for them, and it makes the fixture
    # reviewable as a diff instead of an opaque blob.
    parts = [
        "<!doctype html>",
        "<html><head>",
        f"<!-- Captured from {SOURCE_URL.format(date=args.date)}",
        "     Reduced by scripts/capture_schedule_fixture.py.",
        "     A third-party response, not an authored contract example. See",
        "     contracts/README.md and docs/STUBS.md. -->",
        "</head><body>",
    ]
    for event in kept_events:
        parts.append(
            '<script type="application/ld+json">'
            + json.dumps(event, ensure_ascii=False)
            + "</script>"
        )
    state = {"props": {"pageProps": {"content": {"liveScores": kept}}}}
    parts.append(
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(state, ensure_ascii=False)
        + "</script>"
    )
    parts.append("</body></html>")
    out.write_text("\n".join(parts), encoding="utf-8")

    print(f"wrote {out.relative_to(ROOT)}")
    print(f"  competitions   {len(kept)}")
    print(f"  matches        {match_count}")
    print(f"  with providers {with_providers}")
    print(f"  json-ld blocks {len(kept_events)}")
    print(f"  size           {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
