"""Data source adapters.

Fixture-backed in the skeleton: nothing here touches the network. Adding a real
provider means a new adapter and nothing else -- the scoring path, the API, and
the web app are unaffected, because everything downstream consumes MatchSnapshots
rather than provider payloads.
"""

from .adapter import SourceAdapter
from .fixture_file import FixtureFileAdapter
from .run import ingest

__all__ = ["FixtureFileAdapter", "SourceAdapter", "ingest"]
