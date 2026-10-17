"""
Windows non-blocking keyboard input driver using standard msvcrt module.
Handles single-byte ASCII and two-byte extended virtual keys (arrow keys).
"""

from __future__ import annotations

import sys
from ..base import BaseInputHandler

try:
    import msvcrt
except ImportError:
    msvcrt = None


class WindowsInputHandler(BaseInputHandler):
    """Encapsulates non-blocking key polling on Windows without altering console flags."""

    def __init__(self) -> None:
        if sys.platform != "win32" or not msvcrt:
            raise RuntimeError("WindowsInputHandler is only supported on Windows.")

    def poll_key(self) -> str | None:
        """Polls for pending key press without blocking. Returns semantic key action token."""
        if not msvcrt or not msvcrt.kbhit():
            return None

        ch = msvcrt.getch()

        # Handle extended keys (Arrow keys prefix: 0x00 or 0xE0)
        if ch in (b"\x00", b"\xe0"):
            sub = msvcrt.getch()
            if sub == b"M":
                return "RIGHT"
            elif sub == b"K":
                return "LEFT"
            elif sub == b"H":
                return "UP"
            elif sub == b"P":
                return "DOWN"
            return None

        # Handle standard keys
        if ch == b"\x03":
            raise KeyboardInterrupt
        elif ch == b" ":
            return "SPACE"
        elif ch in (b"q", b"Q", b"\x1b"):
            return "QUIT"
        elif ch in (b"m", b"M"):
            return "MODE"
        elif ch in (b"c", b"C"):
            return "COLOR"
        elif ch in (b"l", b"L"):
            return "LOOP"
        elif ch in (b"r", b"R"):
            return "RESTART"

        return None

    def cleanup(self) -> None:
        """No teardown needed for msvcrt."""
        pass
