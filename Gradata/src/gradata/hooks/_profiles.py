"""Hook profile tiers — controls which hooks activate."""

from __future__ import annotations

from enum import IntEnum


class Profile(IntEnum):
    MINIMAL = 0  # Core learning loop only
    STANDARD = 1  # + safety + quality
    STRICT = 2  # + duplicate guard, implicit feedback, full maintenance
