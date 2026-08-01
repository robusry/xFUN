#!/usr/bin/env python3
"""Assert that live API responses match contracts/openapi.yaml.

`contracts/openapi.yaml` is the source of truth: the API is validated against it,
not generated from it. Without this check that claim is aspirational -- the
document and the implementation could drift apart indefinitely and the only
symptom would be a client breaking in production.

OpenAPI 3.1 schemas are JSON Schema 2020-12, so the component schemas can be
validated directly once internal $refs can resolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for src in sorted(ROOT.glob("packages/*/src")) + sorted(ROOT.glob("packages/models/*/src")):
    sys.path.insert(0, str(src))


def main() -> int:
    try:
        import yaml
        from jsonschema import Draft202012Validator
    except ImportError:
        print("Missing dependencies. Run: uv sync", file=sys.stderr)
        return 2

    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print("FastAPI is not installed. Run: uv sync", file=sys.stderr)
        return 2

    from xfun_api import app

    spec = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text())
    components = spec["components"]

    def validator_for(schema_name: str) -> Draft202012Validator:
        # Carrying `components` into the schema root lets #/components/schemas/...
        # references resolve without a network-backed resolver.
        return Draft202012Validator(
            {"$ref": f"#/components/schemas/{schema_name}", "components": components}
        )

    client = TestClient(app)
    window = {"from": "2026-08-01", "to": "2026-08-31"}

    cases = [
        ("GET /v1/matches", "/v1/matches", window, 200, "MatchListResponse"),
        (
            "GET /v1/matches (single-model alias)",
            "/v1/matches",
            {**window, "score": "odds-spread"},
            200,
            "MatchListResponse",
        ),
        (
            "GET /v1/matches/{id}/scores",
            "/v1/matches/epl-2026-08-15-ars-liv/scores",
            {},
            200,
            "MatchScoresResponse",
        ),
        (
            "GET /v1/matches/{id}/scores (partial coverage)",
            "/v1/matches/laliga-2026-08-16-rma-get/scores",
            {},
            200,
            "MatchScoresResponse",
        ),
        ("GET /v1/registry", "/v1/registry", {}, 200, "RegistryResponse"),
        (
            "GET /v1/matches (unimplemented cohort)",
            "/v1/matches",
            {**window, "cohort": "season"},
            501,
            "Problem",
        ),
        (
            "GET /v1/matches/{id}/scores (unknown match)",
            "/v1/matches/nope/scores",
            {},
            404,
            None,  # FastAPI's default 404 body; not contract-described
        ),
    ]

    failures = 0

    for label, path, params, expected_status, schema_name in cases:
        response = client.get(path, params=params)

        if response.status_code != expected_status:
            print(f"FAIL  {label}: expected {expected_status}, got {response.status_code}")
            failures += 1
            continue

        if schema_name is None:
            print(f"ok    {label} -> {response.status_code}")
            continue

        errors = sorted(
            validator_for(schema_name).iter_errors(response.json()),
            key=lambda e: list(e.absolute_path),
        )
        if errors:
            failures += 1
            print(f"FAIL  {label} -> {response.status_code}, does not match {schema_name}")
            for err in errors[:6]:
                location = "/".join(str(p) for p in err.absolute_path) or "(root)"
                print(f"        {location}: {err.message}")
        else:
            print(f"ok    {label} -> {response.status_code} matches {schema_name}")

    # Every path in the contract must exist on the app, and vice versa: a route
    # the contract does not describe is as much a drift as a missing one.
    documented = set(spec["paths"])
    implemented = {
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/v1")
    }
    if documented != implemented:
        failures += 1
        print("FAIL  path sets differ between contract and implementation")
        for path in sorted(documented - implemented):
            print(f"        documented but not implemented: {path}")
        for path in sorted(implemented - documented):
            print(f"        implemented but not documented: {path}")
    else:
        print(f"ok    {len(documented)} paths documented and implemented")

    print(f"\n{len(cases) + 1} checks, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
