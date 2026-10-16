"""
Keyboard input package for Caramell Dansen terminal player.
"""

from __future__ import annotations

import sys
from .base import BaseInputHandler


def get_input_handler() -> BaseInputHandler:
    """Returns the platform-specific non-blocking keyboard input handler."""
    if sys.platform != "win32":
        from .posix import PosixInputHandler

        return PosixInputHandler()

    raise NotImplementedError("Windows keyboard handler is not yet implemented.")
