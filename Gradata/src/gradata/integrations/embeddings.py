"""DEPRECATED — moved to :mod:`gradata.services.embeddings`.

.. deprecated:: 0.7.0
    Import from ``gradata.services.embeddings`` instead. This shim will be
    removed in v0.9.0 per the two-minor-version carry rule.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.embeddings is deprecated and will be removed in "
    "v0.9.0. Import from gradata.services.embeddings instead.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.services.embeddings import *  # noqa: F403
