"""Gradata Exceptions — structured error hierarchy rooted at ``BrainError``."""


class BrainError(Exception):
    """Base exception for all Gradata errors."""


class BrainNotFoundError(BrainError, FileNotFoundError):
    """Brain directory does not exist or is not a valid brain."""


class EventPersistenceError(BrainError):
    """Failed to persist an event to both JSONL and SQLite.

    This is critical — learning data was lost. Check file permissions
    and disk space, then retry the operation.
    """


class TaxonomyError(BrainError):
    """Invalid or corrupt taxonomy.json configuration."""


class EmbeddingError(BrainError):
    """Embedding operation failed (missing deps or backend error)."""


class ExportError(BrainError):
    """Brain export/packaging failed."""


class ValidationError(BrainError):
    """Brain validation failed (corrupt data, missing files, etc.)."""
