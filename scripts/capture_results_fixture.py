#!/usr/bin/env python3
"""Capture past goal.com pages into golden fixtures of completed matches.

A development tool, not part of the pipeline and not run by CI. Its output is what
lets `./scripts/demo.sh` run the real `recent-results` scan over real historical
results with no network, which is the bargain every default path in this repository
makes: a fresh clone works with nothing configured.

Walks backwards from a date, keeping only matches involving a named set of teams, and
stops as soon as each of them has five completed matches -- the same stopping rule the
collector uses, so the capture is exactly as deep as the fixture needs and no deeper.

The capture is REDUCED, not raw. A live page is 0.5-3 MB, almost all of it markup and
competitions this fixture does not care about. What survives is the competition-grouped
page state, trimmed to matches involving the named teams. Still the source's own bytes;
a subset, not a paraphrase.

Unlike `capture_schedule_fixture.py` this keeps NO schema.org blocks. They carry
identity and kickoff but no score, so the results scan never reads them, and a fixture
carrying data nothing reads invites a reader to believe it matters.

Matches are kept whatever their state -- postponed, cancelled, and in-progress entries
included -- because filtering them here would hide them from the fixture, and not
counting them is precisely what the collector has to get right.

Usage:
    python scripts/capture_results_fixture.py --as-of 2026-08-14
    python scripts/capture_results_fixture.py --as-of 2026-08-14 --teams Arsenal Liverpool

Uses stdlib urllib on purpose: this tool must not be the reason the repository grows an
HTTP dependency, and it runs on a developer's machine rather than in the pipeline.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "contracts" / "fixtures" / "schedule" / "results"
SNAPSHOT_DIR = ROOT / "contracts" / "fixtures" / "snapshots"

sys.path.insert(0, str(ROOT / "packages" / "ingestion" / "src"))
from xfun_ingestion.schedule.canonical import CanonicalIdError, team_id

SOURCE_URL = "https://www.goal.com/en-us/fixtures/{date}"

COMPLETED = "RESULT"
MATCHES_WANTED = 5
BOUND_DAYS = 120

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


def fixture_team_names() -> list[str]:
    """The teams the golden snapshots are about, by name.

    By name rather than by id on purpose: the snapshots' ids are short codes (`ars`),
    and the collector matches on the name derivation, so this captures what the
    collector will actually look for.
    """
    names: set[str] = set()
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        payload = json.loads(path.read_text())
        for side in ("home_team", "away_team"):
            names.add(payload[side]["name"])
    return sorted(names)


def fetch(day: date) -> str:
    url = SOURCE_URL.format(date=day.isoformat())
    request = urllib.request.Request(
        url,
        headers={
            # The same honest identification the schedule source uses. Claiming to be
            # a browser is what several rejected sources require, and why they were
            # rejected.
            "User-Agent": "xfun-schedule-acquisition/0.1 (+https://github.com/robusry/xFUN)",
            "Accept": "text/html",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def competition_groups(html: str) -> list[dict[str, Any]]:
    match = NEXT_DATA_RE.search(html)
    if match is None:
        raise SystemExit("no __NEXT_DATA__ in page; the source changed shape")
    data = json.loads(match.group(1))
    try:
        return data["props"]["pageProps"]["content"]["liveScores"]
    except KeyError as exc:
        raise SystemExit(f"page state no longer holds liveScores: {exc}") from None


def key_of(name: str | None) -> str | None:
    if not name:
        return None
    try:
        return team_id(name)
    except CanonicalIdError:
        return None


def reduce_page(groups: list[dict[str, Any]], wanted: set[str]) -> list[dict[str, Any]]:
    """The same groups, holding only matches involving a wanted team."""
    kept: list[dict[str, Any]] = []
    for group in groups:
        matches = [
            match
            for match in (group.get("matches") or [])
            if isinstance(match, dict)
            and {
                key_of((match.get("teamA") or {}).get("name")),
                key_of((match.get("teamB") or {}).get("name")),
            }
            & wanted
        ]
        if matches:
            kept.append({**group, "matches": matches})
    return kept


def write_capture(day: date, groups: list[dict[str, Any]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{day.isoformat()}.html"
    state = {"props": {"pageProps": {"content": {"liveScores": groups}}}}
    out.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html><head>",
                f"<!-- Captured from {SOURCE_URL.format(date=day.isoformat())}",
                "     Reduced by scripts/capture_results_fixture.py.",
                "     A third-party response, not an authored contract example. See",
                "     contracts/README.md and docs/STUBS.md. -->",
                "</head><body>",
                '<script id="__NEXT_DATA__" type="application/json">'
                + json.dumps(state, ensure_ascii=False)
                + "</script>",
                "</body></html>",
            ]
        ),
        encoding="utf-8",
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        required=True,
        help="the date to walk back from, YYYY-MM-DD. Fix it to the demo's stamp so "
        "the offline path stays reproducible.",
    )
    parser.add_argument(
        "--teams",
        nargs="*",
        default=None,
        help="team names to keep. Defaults to every team in the golden snapshots.",
    )
    parser.add_argument("--bound-days", type=int, default=BOUND_DAYS)
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    names = args.teams if args.teams is not None else fixture_team_names()
    wanted = {key for name in names if (key := key_of(name))}
    print(f"capturing for {len(wanted)} teams, back from {as_of}\n")

    counts: dict[str, int] = dict.fromkeys(wanted, 0)
    written = 0
    total_bytes = 0

    for offset in range(args.bound_days + 1):
        day = as_of - timedelta(days=offset)
        html = fetch(day)
        kept = reduce_page(competition_groups(html), wanted)

        if kept:
            out = write_capture(day, kept)
            written += 1
            total_bytes += out.stat().st_size
            finished = 0
            for group in kept:
                for match in group["matches"]:
                    if match.get("status") != COMPLETED:
                        continue
                    finished += 1
                    for side in ("teamA", "teamB"):
                        key = key_of((match.get(side) or {}).get("name"))
                        if key in counts:
                            counts[key] += 1
            print(
                f"  {day}  {sum(len(g['matches']) for g in kept):>2} matches "
                f"({finished} completed)  {out.stat().st_size // 1024} KB"
            )

        if all(n >= MATCHES_WANTED for n in counts.values()):
            print(f"\nevery team has {MATCHES_WANTED}; stopping at {day}")
            break

        # Deliberately unhurried. This walks a hundred-odd pages of somebody else's
        # site, and it is a tool a person runs by hand rather than a pipeline step.
        time.sleep(1.0)
    else:
        short = sorted(t for t, n in counts.items() if n < MATCHES_WANTED)
        print(f"\nreached the {args.bound_days}-day bound with {len(short)} teams short:")
        print("  " + ", ".join(f"{t} ({counts[t]})" for t in short))

    print(f"\nwrote {written} captures, {total_bytes // 1024} KB total")
    print(f"  {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
