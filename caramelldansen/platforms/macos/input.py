"""
macOS non-blocking keyboard input driver using termios and select.
"""

from __future__ import annotations

import os
import select
import sys
from ..base import BaseInputHandler

try:
    import termios

    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False


class MacOSInputHandler(BaseInputHandler):
    """Configures stdin in non-canonical raw mode for instant single-key polling."""

    def __init__(self) -> None:
        if sys.platform != "darwin" or not _HAS_TERMIOS:
            return

        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)

        # Set raw mode without echo
        new_settings = termios.tcgetattr(self._fd)
        new_settings[3] = new_settings[3] & ~(termios.ICANON | termios.ECHO)
        new_settings[6][termios.VMIN] = 0
        new_settings[6][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSANOW, new_settings)

    def poll_key(self) -> str | None:
        """Polls for pending key press without blocking."""
        if not _HAS_TERMIOS:
            return None

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
                    return "QUIT"

                seq = os.read(self._fd, 4)
                if seq in (b"[C", b"OC"):
                    return "RIGHT"
                elif seq in (b"[D", b"OD"):
                    return "LEFT"
                elif seq in (b"[A", b"OA"):
                    return "UP"
                elif seq in (b"[B", b"OB"):
                    return "DOWN"
                return "QUIT"

            if ch == b"\x03":
                raise KeyboardInterrupt
            elif ch == b" ":
                return "SPACE"
            elif ch in (b"q", b"Q"):
                return "QUIT"
            elif ch in (b"m", b"M"):
                return "MODE"
            elif ch in (b"r", b"R"):
                return "RESTART"

            return None
        except Exception:
            return None

    def cleanup(self) -> None:
        """Restores original terminal attributes."""
        if _HAS_TERMIOS and hasattr(self, "_old_settings") and self._old_settings is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
            self._old_settings = None
