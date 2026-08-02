"""Slate assembly and canonical entity writing.

Two jobs, both narrower than what this package used to do. It decides WHICH matches
a run is about -- the slate -- and it writes the canonical part of each match into
the store. It no longer defines a pluggable source interface: fetching everything
else is the collector tier's job, because collectors fan out from a slate and key
their output by entity, which is what lets several models share one fetch.

Nothing here touches the network. See `packages/collectors/` for the tier that does.
"""

from .fixtures import fixture_payloads
from .run import IngestResult, ingest
from .slate import assemble_slate

__all__ = ["IngestResult", "assemble_slate", "fixture_payloads", "ingest"]
