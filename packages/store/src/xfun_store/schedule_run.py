"""Recording what happened when the schedule was acquired.

The whole point is one distinction. An empty slate can mean the source answered and
nothing in the window is watchable, or it can mean the source could not be reached.
Downstream they are identical -- no matches, no scores, nothing to serve -- and only
this record separates them.

That distinction is not hypothetical here. The leagues in scope go between seasons,
so a genuinely empty fortnight is a normal answer, which is exactly what makes a
broken source easy to mistake for one.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field

__all__ = ["ScheduleRun", "latest_schedule_run", "write_schedule_run"]


@dataclass(frozen=True)
class ScheduleRun:
    """One attempt at acquiring the schedule.

    `matches_seen` counts what the source returned, before the watchable filter.
    `matches_watchable` counts what survived it. Keeping both separates "the source
    answered fully but named no providers" from "the source returned nothing",
    which otherwise look the same from the empty slate they both produce.
    """

    source_id: str
    status: str
    window_start_utc: str
    window_end_utc: str
    reason: str | None = None
    matches_seen: int = 0
    matches_watchable: int = 0
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @classmethod
    def ok(
        cls,
        source_id: str,
        window_start_utc: str,
        window_end_utc: str,
        *,
        matches_seen: int,
        matches_watchable: int,
    ) -> ScheduleRun:
        return cls(
            source_id=source_id,
            status="ok",
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            matches_seen=matches_seen,
            matches_watchable=matches_watchable,
        )

    @classmethod
    def failure(
        cls,
        source_id: str,
        window_start_utc: str,
        window_end_utc: str,
        reason: str,
    ) -> ScheduleRun:
        """A failed run names a reason. Without one this record would say only that
        something went wrong, which is what the table exists to improve on."""
        if not reason:
            raise ValueError("a failed schedule run must record why")
        return cls(
            source_id=source_id,
            status="failed",
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            reason=reason,
        )

    def summary(self) -> str:
        if self.failed:
            return f"{self.source_id}: FAILED — {self.reason}"
        return (
            f"{self.source_id}: {self.matches_watchable} watchable "
            f"of {self.matches_seen} seen"
        )


def write_schedule_run(conn: sqlite3.Connection, run: ScheduleRun) -> str:
    conn.execute(
        "INSERT INTO schedule_run (run_id, source_id, status, reason, "
        "window_start_utc, window_end_utc, matches_seen, matches_watchable, ran_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (
            run.run_id,
            run.source_id,
            run.status,
            run.reason,
            run.window_start_utc,
            run.window_end_utc,
            run.matches_seen,
            run.matches_watchable,
        ),
    )
    return run.run_id


def latest_schedule_run(conn: sqlite3.Connection) -> ScheduleRun | None:
    """The most recent attempt, successful or not.

    Reading the most recent attempt rather than the most recent SUCCESS is
    deliberate. A caller asking "is what I am looking at current" needs to know that
    the last run failed, not be handed the last one that happened to work.
    """
    row = conn.execute(
        "SELECT run_id, source_id, status, reason, window_start_utc, window_end_utc, "
        "matches_seen, matches_watchable FROM schedule_run "
        "ORDER BY ran_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return ScheduleRun(
        run_id=row["run_id"],
        source_id=row["source_id"],
        status=row["status"],
        reason=row["reason"],
        window_start_utc=row["window_start_utc"],
        window_end_utc=row["window_end_utc"],
        matches_seen=row["matches_seen"],
        matches_watchable=row["matches_watchable"],
    )
