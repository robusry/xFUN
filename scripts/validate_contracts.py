#!/usr/bin/env python3
"""Validate every fixture against its schema, and check that openapi.yaml parses.

This runs on every pull request. A producer that emits output not conforming to
contracts/schemas/ must fail here, before the output can reach a consuming tier.
That is what makes contracts/ a contract rather than documentation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"

PAIRS = [
    (CONTRACTS / "fixtures" / "snapshots", CONTRACTS / "schemas" / "match-snapshot.json"),
    (CONTRACTS / "fixtures" / "scores", CONTRACTS / "schemas" / "model-score.json"),
    (CONTRACTS / "fixtures" / "slates", CONTRACTS / "schemas" / "slate.json"),
    (CONTRACTS / "fixtures" / "collection-runs", CONTRACTS / "schemas" / "collection-run.json"),
]


def main() -> int:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("jsonschema not installed. Run: uv sync", file=sys.stderr)
        return 2

    try:
        import yaml
    except ImportError:
        print("pyyaml not installed. Run: uv sync", file=sys.stderr)
        return 2

    failures = 0
    checked = 0

    for fixture_dir, schema_path in PAIRS:
        schema = json.loads(schema_path.read_text())
        validator = Draft202012Validator(schema)

        fixtures = sorted(fixture_dir.glob("*.json"))
        if not fixtures:
            print(f"FAIL  {fixture_dir.relative_to(ROOT)} contains no fixtures")
            failures += 1
            continue

        for fixture in fixtures:
            checked += 1
            instance = json.loads(fixture.read_text())
            errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if errors:
                failures += 1
                print(f"FAIL  {fixture.relative_to(ROOT)}")
                for err in errors:
                    location = "/".join(str(p) for p in err.absolute_path) or "(root)"
                    print(f"        {location}: {err.message}")
            else:
                print(f"ok    {fixture.relative_to(ROOT)}")

    openapi = CONTRACTS / "openapi.yaml"
    try:
        spec = yaml.safe_load(openapi.read_text())
        for key in ("openapi", "info", "paths", "components"):
            if key not in spec:
                raise ValueError(f"missing top-level key: {key}")
        print(f"ok    {openapi.relative_to(ROOT)} ({len(spec['paths'])} paths)")
        checked += 1
    except Exception as exc:  # noqa: BLE001 - report any parse problem the same way
        failures += 1
        print(f"FAIL  {openapi.relative_to(ROOT)}: {exc}")

    print(f"\n{checked} checked, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
