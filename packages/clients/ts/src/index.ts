/**
 * Typed client for the xFUN API.
 *
 * The TYPES come from `contracts/openapi.yaml` via `pnpm client:generate`, which
 * writes `src/generated.d.ts`. That file is gitignored: it is a build artifact of
 * the contract, and checking it in would create a second place for the API's shape
 * to live and drift.
 *
 * This module is only the fetch plumbing around those generated types. If a
 * response shape changes in the contract, this file stops typechecking -- which is
 * the point.
 *
 * Run `pnpm install && pnpm client:generate` before typechecking or building.
 */

import type { components, operations } from "./generated";

export type MatchListResponse =
  operations["listMatches"]["responses"]["200"]["content"]["application/json"];
export type MatchScoresResponse =
  operations["getMatchScores"]["responses"]["200"]["content"]["application/json"];
export type RegistryResponse =
  operations["getRegistry"]["responses"]["200"]["content"]["application/json"];

export type RankedMatch = components["schemas"]["RankedMatch"];
export type ComposedScore = components["schemas"]["ComposedScore"];
export type CohortInfo = components["schemas"]["CohortInfo"];
export type AliasInfo = components["schemas"]["AliasInfo"];
export type CalibratedModelScore = components["schemas"]["CalibratedModelScore"];

export type CohortName = "window" | "league" | "season" | "global";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`xFUN API ${status}: ${detail}`);
  }
}

export interface ClientOptions {
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
}

export class XfunClient {
  private readonly baseUrl: string;
  private readonly doFetch: typeof globalThis.fetch;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://localhost:8000").replace(/\/$/, "");
    this.doFetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  private async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(this.baseUrl + path);
    for (const [key, value] of Object.entries(params ?? {})) {
      url.searchParams.set(key, value);
    }

    const response = await this.doFetch(url.toString());
    if (!response.ok) {
      // 501 means a valid-but-unimplemented cohort or policy. Surfacing the
      // server's own detail matters here: it names the change that implements it.
      let detail = response.statusText;
      try {
        const body = (await response.json()) as { detail?: string; title?: string };
        detail = body.detail ?? body.title ?? detail;
      } catch {
        /* non-JSON error body; keep statusText */
      }
      throw new ApiError(response.status, detail);
    }
    return (await response.json()) as T;
  }

  /** Matches in a date range, ranked by composed score. */
  listMatches(args: {
    from: string;
    to: string;
    score?: string;
    cohort?: CohortName;
  }): Promise<MatchListResponse> {
    return this.get<MatchListResponse>("/v1/matches", {
      from: args.from,
      to: args.to,
      score: args.score ?? "default",
      cohort: args.cohort ?? "window",
    });
  }

  /** Every model's calibrated score for one match, plus the composite. */
  getMatchScores(
    matchId: string,
    args: { score?: string; cohort?: CohortName } = {},
  ): Promise<MatchScoresResponse> {
    return this.get<MatchScoresResponse>(`/v1/matches/${encodeURIComponent(matchId)}/scores`, {
      score: args.score ?? "default",
      cohort: args.cohort ?? "window",
    });
  }

  /** Available models, compositions, and aliases. */
  getRegistry(): Promise<RegistryResponse> {
    return this.get<RegistryResponse>("/v1/registry");
  }
}
