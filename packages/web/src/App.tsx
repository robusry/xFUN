/**
 * The whole page.
 *
 * One deliberate choice worth noting: the calibration cohort is shown in the
 * interface, not hidden. A score of 91 means "91st percentile among the matches
 * in this window" -- under a season cohort the same match scores differently.
 * Displaying a bare number would make it uninterpretable, and would train people
 * to read it as an absolute rating, which it is not.
 *
 * PLACEHOLDER: the scores come from two placeholder models that predict nothing.
 * See docs/STUBS.md.
 */

import { useEffect, useState } from "react";
import { ApiError, XfunClient, type MatchListResponse } from "@xfun/client";

const client = new XfunClient({
  baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

/** The window the server actually served, as a human-readable line. */
function windowLabel(window: MatchListResponse["window"]): string {
  if (!window.from || !window.to) return "no matches in the store";

  const day = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });

  const from = day(window.from);
  const to = day(window.to);
  return from === to ? from : `${from} to ${to}`;
}

function scoreColor(value: number | null): string {
  if (value === null) return "var(--muted)";
  if (value >= 75) return "var(--hot)";
  if (value >= 50) return "var(--warm)";
  return "var(--cool)";
}

export default function App() {
  const [data, setData] = useState<MatchListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // No dates: the server answers over what it holds and tells us the range it
    // served. Asking for a window computed here would put that policy in the least
    // authoritative tier, and would blank the offline demo, whose fixture matches
    // sit in the past.
    client
      .listMatches()
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : String(e)),
      );
  }, []);

  if (error) {
    return (
      <main>
        <h1>xFUN</h1>
        <p className="error">{error}</p>
        <p className="muted">
          Is the API running? Try <code>./scripts/demo.sh</code>
        </p>
      </main>
    );
  }

  if (!data) return <main><h1>xFUN</h1><p className="muted">Loading…</p></main>;

  if (data.matches.length === 0) {
    // An empty store and an empty date range look identical on the page, so say
    // which it was. The pipeline has to run before there is anything to show.
    return (
      <main>
        <h1>xFUN</h1>
        <p className="muted">No matches scored yet.</p>
        <p className="muted">
          Run <code>uv run python scripts/pipeline.py</code> to acquire and score
          upcoming matches. It needs network access to the schedule source.
        </p>
      </main>
    );
  }

  return (
    <main>
      <header>
        <h1>xFUN</h1>
        <p className="muted">
          Which matches are worth watching, {windowLabel(data.window)}
        </p>
        <p className="banner">
          Placeholder models — these scores predict nothing. See{" "}
          <code>docs/STUBS.md</code>.
        </p>
      </header>

      <p className="cohort">
        Scored as a percentile within the <strong>{data.cohort.definition}</strong>{" "}
        cohort of {data.cohort.match_count} matches
        {data.cohort.low_confidence && " — low confidence, small cohort"}. Blend:{" "}
        <strong>{data.score_alias.alias}</strong> → {data.score_alias.resolves_to}.
      </p>

      <ol className="matches">
        {data.matches.map(({ match, composed }) => (
          <li key={match.match_id}>
            <div className="score" style={{ color: scoreColor(composed.value) }}>
              {composed.value === null ? "—" : composed.value.toFixed(0)}
            </div>
            <div className="detail">
              <div className="teams">
                {match.home_team} <span className="v">v</span> {match.away_team}
              </div>
              <div className="meta">
                {match.league} · {new Date(match.kickoff_utc).toUTCString()}
                {match.availability?.status === "unknown" && (
                  <span className="unknown"> · where to watch: unknown</span>
                )}
              </div>
              <div className="why">
                {composed.reason ??
                  composed.contributors
                    ?.map(
                      (c) =>
                        `${c.model_id} ${c.calibrated_score.toFixed(0)} (weight ${c.weight.toFixed(2)})`,
                    )
                    .join(" · ")}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </main>
  );
}
