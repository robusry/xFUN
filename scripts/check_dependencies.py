#!/usr/bin/env python3
"""Enforce the tier boundaries that everything else depends on.

These rules are the difference between an architecture and a diagram. Each one is
easy to break by accident and hard to notice afterwards, so CI checks them rather
than trusting discipline:

1. **Models are pure.** No database drivers, no HTTP clients, no filesystem at
   scoring time. A model that reaches outside its snapshot stops being
   reproducible, and every historical score it produced becomes unverifiable.

2. **Models are independent.** No model imports another, or reads another's
   output. One such import turns scoring into an ordered graph and makes
   composition expensive to reverse.

3. **The API never executes a model.** No model package appears anywhere in the
   API's dependency tree. This is what lets the API keep serving when a model is
   broken, and what keeps modelling work from becoming an availability risk.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"

FORBIDDEN_IN_MODELS = {
    "sqlite3", "psycopg", "psycopg2", "sqlalchemy", "asyncpg", "pymongo",
    "requests", "httpx", "aiohttp", "urllib", "urllib3", "socket", "http",
    "xfun_store", "xfun_ingestion", "xfun_api",
}

MODEL_DIST_PREFIX = "xfun-model-"
MODEL_MODULE_PREFIX = "xfun_model_"


def _dependencies(pyproject: Path) -> list[str]:
    data = tomllib.loads(pyproject.read_text())
    raw = data.get("project", {}).get("dependencies", [])
    return [re.split(r"[<>=!\[; ]", d, maxsplit=1)[0].strip() for d in raw]


def _imported_modules(package_dir: Path) -> set[str]:
    modules: set[str] = set()
    for source in package_dir.rglob("*.py"):
        tree = ast.parse(source.read_text(), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    return modules


def main() -> int:
    failures: list[str] = []
    model_dirs = sorted((PACKAGES / "models").glob("*/"))

    # --- 1 and 2: model purity and independence ---------------------------
    for model_dir in model_dirs:
        name = model_dir.name
        src = model_dir / "src"

        for dependency in _dependencies(model_dir / "pyproject.toml"):
            if dependency != "xfun-scoring-contract":
                failures.append(
                    f"models/{name}: declares dependency {dependency!r}. A model may "
                    f"depend only on xfun-scoring-contract."
                )

        for module in sorted(_imported_modules(src)):
            if module in FORBIDDEN_IN_MODELS:
                failures.append(
                    f"models/{name}: imports {module!r}. Models are pure: no I/O, no "
                    f"database, no network."
                )
            if module.startswith(MODEL_MODULE_PREFIX) and module != f"{MODEL_MODULE_PREFIX}{name.replace('-', '_')}":
                failures.append(
                    f"models/{name}: imports another model ({module!r}). Models are "
                    f"mutually independent."
                )

    # --- 3: the API must not be able to run a model ------------------------
    api_dir = PACKAGES / "api"
    for dependency in _dependencies(api_dir / "pyproject.toml"):
        if dependency.startswith(MODEL_DIST_PREFIX):
            failures.append(
                f"api: declares dependency {dependency!r}. The API reads precomputed "
                f"scores and must never execute a model."
            )
    for module in sorted(_imported_modules(api_dir / "src")):
        if module.startswith(MODEL_MODULE_PREFIX):
            failures.append(
                f"api: imports {module!r}. The API must never execute a model."
            )

    checked = f"{len(model_dirs)} model packages, api"
    if failures:
        print(f"Tier boundary violations ({checked}):\n")
        for failure in failures:
            print(f"  FAIL  {failure}")
        print(f"\n{len(failures)} violation(s)")
        return 1

    print(f"ok    tier boundaries hold ({checked})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
