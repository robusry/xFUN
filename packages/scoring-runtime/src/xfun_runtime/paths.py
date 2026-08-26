"""Locating the repository's shared directories.

Walks up from this file to find the repository root. Crude, but honest for a
skeleton: it has no configuration to get out of sync, and it fails loudly rather
than silently reading the wrong contracts.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "captures_dir",
    "contracts_dir",
    "data_dir",
    "fixtures_dir",
    "repo_root",
    "schemas_dir",
]

_MARKERS = ("contracts", "openspec", "pyproject.toml")


def repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if all((candidate / m).exists() for m in _MARKERS):
            return candidate
    raise RuntimeError(
        "Could not locate the repository root. Expected an ancestor directory "
        f"containing all of: {', '.join(_MARKERS)}"
    )


def contracts_dir() -> Path:
    return repo_root() / "contracts"


def schemas_dir() -> Path:
    return contracts_dir() / "schemas"


def fixtures_dir() -> Path:
    return contracts_dir() / "fixtures"


def captures_dir() -> Path:
    """Captured third-party responses, read only by tests.

    Deliberately NOT under `contracts/`. Everything in that directory is authored
    by this project and validated against a schema; these are somebody else's bytes,
    validated against nothing, and the distinction has to be visible from a file's
    location rather than from a paragraph someone has to find first.
    """
    return repo_root() / "tests" / "captures"


def data_dir() -> Path:
    """Where the SQLite database lives. Created on demand, gitignored."""
    d = repo_root() / ".data"
    d.mkdir(exist_ok=True)
    return d
