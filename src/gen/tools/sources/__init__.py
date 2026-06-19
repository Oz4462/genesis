"""gen.tools.sources — free-API discovery connectors behind the ``SearchBackend`` seam.

Each connector turns a free, openly-licensed scholarly/patent API into a stream of ``SourceCandidate``s —
DISCOVERY only, like every backend: it never asserts a fact, the candidate stays unfetched until ``scholar``
retrieves it, and every candidate carries a real, stable id/URL as provenance. Transport is the injected
``HttpGet`` so each connector is offline-fixture-testable and live-probeable through the same seam.

Connectors:
  - ``openalex.OpenAlexBackend``  — OpenAlex works (data CC0), prior-art / literature.
  - ``patents.PatentsViewBackend`` — PatentsView patents (US gov, public domain), the §7/§13 patent gap.
"""

from .openalex import OpenAlexBackend
from .patents import PatentsViewBackend

__all__ = ["OpenAlexBackend", "PatentsViewBackend"]
