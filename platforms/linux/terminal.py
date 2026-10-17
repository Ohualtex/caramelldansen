"""
Linux terminal manager driver.
Handles xterm/VT ANSI alternate screen buffer, cursor hiding, and SIGWINCH window resize signals.
"""

from __future__ import annotations

import shutil
import signal
import sys
from ..base import BaseTerminalManager


class LinuxTerminalManager(BaseTerminalManager):
    """Manages terminal buffers and window resize signals on Linux."""

    def __init__(self) -> None:
        self._last_size: tuple[int, int] = self.get_size()
        self._resized_flag: bool = False
        self._old_sigwinch = None
        self._in_fullscreen: bool = False
        self._setup_signals()

    def _setup_signals(self) -> None:
        """Hooks POSIX SIGWINCH for asynchronous window resize notifications."""
        if hasattr(signal, "SIGWINCH"):
            try:
                def _on_sigwinch(signum, frame):
                    self._resized_flag = True

                self._old_sigwinch = signal.signal(signal.SIGWINCH, _on_sigwinch)
            except Exception:
                pass

    def enter_fullscreen(self) -> None:
        """Enters alternate screen buffer and hides terminal cursor."""
        sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
        sys.stdout.flush()
        self._in_fullscreen = True
        self._last_size = self.get_size()
        self._resized_flag = False

    def leave_fullscreen(self) -> None:
        """Restores main screen buffer and unhides cursor."""
        if self._in_fullscreen:
            sys.stdout.write("\033[?1049l\033[?25h")
            sys.stdout.flush()
            self._in_fullscreen = False

    def get_size(self) -> tuple[int, int]:
        """Returns terminal dimensions (columns, rows)."""
        sz = shutil.get_terminal_size(fallback=(80, 24))
        return (sz.columns, sz.lines)

    def check_resized(self) -> bool:
        """Returns True if terminal was resized via SIGWINCH or dimension polling."""
        current = self.get_size()
        if self._resized_flag or current != self._last_size:
            self._resized_flag = False
            self._last_size = current
            return True
        return False

    def cleanup(self) -> None:
        """Restores screen buffer and original signal handlers."""
        self.leave_fullscreen()
        if self._old_sigwinch is not None and hasattr(signal, "SIGWINCH"):
            try:
                signal.signal(signal.SIGWINCH, self._old_sigwinch)
            except Exception:
                pass
            self._old_sigwinch = None
