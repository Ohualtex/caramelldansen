"""
Windows-specific terminal manager.
Configures Win32 Virtual Terminal Processing (VT100), alternate screen buffer,
cursor visibility, and responsive window dimension tracking.
"""

from __future__ import annotations

import ctypes
import shutil
import sys
from ..base import BaseTerminalManager

try:
    import colorama

    _HAS_COLORAMA = True
except ImportError:
    _HAS_COLORAMA = False


class WindowsTerminalManager(BaseTerminalManager):
    """Encapsulates all Windows-native console and terminal operations."""

    def __init__(self) -> None:
        self._last_size: tuple[int, int] = self.get_size()
        self._in_fullscreen: bool = False
        self._setup_virtual_terminal()

    def _setup_virtual_terminal(self) -> None:
        """Enables VT100 ANSI escape sequence processing in Win32 console host."""
        if _HAS_COLORAMA:
            try:
                colorama.just_fix_windows_console()
            except Exception:
                pass

        # Fallback to direct Win32 SetConsoleMode API
        try:
            kernel32 = ctypes.windll.kernel32
            h_stdout = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode)):
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                kernel32.SetConsoleMode(h_stdout, mode.value | 0x0004)
        except Exception:
            pass

    def enter_fullscreen(self) -> None:
        """Enters alternate screen buffer, hides cursor, and clears viewport."""
        sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
        sys.stdout.flush()
        self._in_fullscreen = True
        self._last_size = self.get_size()

    def leave_fullscreen(self) -> None:
        """Restores standard terminal buffer and unhides cursor."""
        if self._in_fullscreen:
            sys.stdout.write("\033[?1049l\033[?25h")
            sys.stdout.flush()
            self._in_fullscreen = False

    def get_size(self) -> tuple[int, int]:
        """Returns current terminal dimensions as (columns, rows)."""
        sz = shutil.get_terminal_size(fallback=(80, 24))
        return (sz.columns, sz.lines)

    def check_resized(self) -> bool:
        """Detects if terminal window has resized since the last call."""
        current = self.get_size()
        if current != self._last_size:
            self._last_size = current
            return True
        return False

    def cleanup(self) -> None:
        """Safely restores terminal mode on exit."""
        self.leave_fullscreen()
