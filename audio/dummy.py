"""
Dummy audio player fallback for systems without audio devices or in headless mode.
"""

from __future__ import annotations

import time
from .base import BaseAudioPlayer


class DummyAudioPlayer(BaseAudioPlayer):
    """Fallback timer-based clock player when no hardware audio is available."""

    def __init__(self, media_path: str = "assets/caramell_dansen.mp3"):
        super().__init__(media_path)
        self._start_perf: float | None = None
        self._offset: float = 0.0
        self._paused_pos: float | None = None

    def start(self) -> None:
        self._start_perf = time.perf_counter()
        self._offset = 0.0
        self.is_open = True
        self.is_paused = False

    def pause(self) -> None:
        if not self.is_paused and self._start_perf is not None:
            self._paused_pos = self.get_pos()
            self.is_paused = True

    def resume(self) -> None:
        if self.is_paused and self._paused_pos is not None:
            self._offset = self._paused_pos
            self._start_perf = time.perf_counter()
            self.is_paused = False
            self._paused_pos = None

    def seek(self, target_seconds: float) -> None:
        self._offset = max(0.0, target_seconds)
        self._start_perf = time.perf_counter()
        self._paused_pos = None
        self.is_open = True
        self.is_paused = False

    def get_pos(self) -> float:
        if self.is_paused and self._paused_pos is not None:
            return self._paused_pos
        if self._start_perf is not None:
            return self._offset + (time.perf_counter() - self._start_perf)
        return self._offset

    def stop(self) -> None:
        self.is_open = False
        self.is_paused = False
        self._start_perf = None

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused
