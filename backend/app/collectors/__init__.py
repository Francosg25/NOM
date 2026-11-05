"""Bounded, evidence-preserving official-source collectors.

`complete` describes exhaustion of this configured query's queue, not completeness
of Mexican regulation coverage. See docs/SOURCES.md before enabling a source.
"""

from .core import (
    Batch,
    CollectionError,
    Document,
    FetchResult,
    SafeFetcher,
    collect,
    extract_document,
    normalize_url,
    validate_url,
)

__all__ = [
    "Batch",
    "CollectionError",
    "Document",
    "FetchResult",
    "SafeFetcher",
    "collect",
    "extract_document",
    "normalize_url",
    "validate_url",
]
