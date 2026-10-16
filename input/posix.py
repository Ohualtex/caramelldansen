"""
POSIX non-blocking keyboard input listener using termios and select.
Supports Space, M, L, C, R, Q, Esc, and arrow keys.
"""

from __future__ import annotations

import os
import select
import sys
import termios
from .base import BaseInputHandler


class PosixInputHandler(BaseInputHandler):
    """
    Non-blocking keyboard listener for macOS and Linux.
    Places stdin in cbreak/raw mode without ECHO.
    """

    def __init__(self):
        super().__init__()
        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)

        # Configure non-canonical, no-echo terminal mode
        new_settings = termios.tcgetattr(self._fd)
        new_settings[3] = new_settings[3] & ~(termios.ICANON | termios.ECHO)
        new_settings[6][termios.VMIN] = 0
        new_settings[6][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSANOW, new_settings)

    def poll_key(self) -> str | None:
        """Polls for keypress without blocking."""
        try:
            rlist, _, _ = select.select([self._fd], [], [], 0.0)
            if not rlist:
                return None

            ch = os.read(self._fd, 1)
            if not ch:
                return None

            # Handle Escape Sequences
            if ch == b"\x1b":
                r2, _, _ = select.select([self._fd], [], [], 0.05)
                if not r2:
                    return "ESC"

                seq = os.read(self._fd, 4)
                if seq in (b"[C", b"OC"):
                    return "RIGHT"
                elif seq in (b"[D", b"OD"):
                    return "LEFT"
                elif seq in (b"[A", b"OA"):
                    return "UP"
                elif seq in (b"[B", b"OB"):
                    return "DOWN"
                return "ESC"

            char = ch.decode("utf-8", errors="ignore")
            if char == " ":
                return "SPACE"
            elif char in ("q", "Q"):
                return "Q"
            elif char in ("m", "M"):
                return "M"
            elif char in ("l", "L"):
                return "L"
            elif char in ("c", "C"):
                return "C"
            elif char in ("r", "R"):
                return "R"

            return char.upper()

        except Exception:
            return None

    def cleanup(self) -> None:
        """Restores original terminal attributes."""
        if self._old_settings is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
            self._old_settings = None
