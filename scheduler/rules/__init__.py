"""Rule registry package.

Importing this package imports the hard and soft modules so their register
decorators run and fill the registries. Anything that needs the rules imports
the registries from here, which guarantees they are populated first.
"""

from .base import (
    HARD_RULES,
    SOFT_RULES,
    HardRule,
    SoftRule,
    register_hard,
    register_soft,
)
from . import hard, soft  # noqa: E402,F401  imported for their registration side effects

__all__ = [
    "HARD_RULES",
    "SOFT_RULES",
    "HardRule",
    "SoftRule",
    "register_hard",
    "register_soft",
]
