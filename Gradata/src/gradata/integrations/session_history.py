"""DEPRECATED — moved to :mod:`gradata.services.session_history`.

.. deprecated:: 0.7.0
    Import from ``gradata.services.session_history`` instead. This shim will
    be removed in v0.9.0 per the two-minor-version carry rule.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.session_history is deprecated and will be removed "
    "in v0.9.0. Import from gradata.services.session_history instead.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.services.session_history import *  # noqa: F403
