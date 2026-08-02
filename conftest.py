"""Make every workspace package importable under a plain `pytest` run.

With `uv sync` the workspace packages are installed editable and this is
redundant. It exists so that a collaborator who has cloned the repository and run
nothing can still execute the test suite -- which matters when the point of this
repository is that people can read and run it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent

for src in sorted(ROOT.glob("packages/*/src")) + sorted(ROOT.glob("packages/models/*/src")):
    path = str(src.resolve())
    if path not in sys.path:
        sys.path.insert(0, path)
