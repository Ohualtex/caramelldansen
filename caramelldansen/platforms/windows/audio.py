"""
Windows audio player subsystem.
Prioritizes hardware-accelerated Pygame mixer with seamless winmm.dll (MCI) fallback.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ..base import BaseAudioPlayer

try:
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame.mixer

    _HAS_PYGAME = True
except Exception:
    _HAS_PYGAME = False


class DummyAudioPlayer(BaseAudioPlayer):
    """Fallback timer-based clock player when no hardware audio is available."""

    def __init__(self, media_path: str) -> None:
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

    def seek(self, seconds: float) -> None:
        self._offset = max(0.0, float(seconds))
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


class WindowsPygameAudioPlayer(BaseAudioPlayer):
    """Hardware-accelerated audio player utilizing pygame.mixer for Windows."""

    def __init__(self, media_path: str) -> None:
        super().__init__(media_path)
        if not _HAS_PYGAME:
            raise RuntimeError("pygame.mixer is not available.")

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            except Exception:
                pygame.mixer.init()

        self._seek_offset: float = 0.0
        self._paused_pos: float = 0.0

    @classmethod
    def is_available(cls) -> bool:
        return _HAS_PYGAME

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return
        self.stop()
        try:
            pygame.mixer.music.load(self.media_path)
            pygame.mixer.music.play()
            self._seek_offset = 0.0
            self._paused_pos = 0.0
            self.is_open = True
            self.is_paused = False
        except Exception:
            self.is_open = False

    def pause(self) -> None:
        if self.is_open and not self.is_paused:
            try:
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms >= 0:
                    self._paused_pos = self._seek_offset + (pos_ms / 1000.0)
                pygame.mixer.music.pause()
                self.is_paused = True
            except Exception:
                pass

    def resume(self) -> None:
        if self.is_open and self.is_paused:
            try:
                pygame.mixer.music.unpause()
                self.is_paused = False
            except Exception:
                pass

    def seek(self, seconds: float) -> None:
        if self.is_open:
            target_sec = max(0.0, float(seconds))
            self._seek_offset = target_sec
            self._paused_pos = target_sec
            try:
                pygame.mixer.music.play(start=target_sec)
                if self.is_paused:
                    pygame.mixer.music.pause()
            except Exception:
                pass

    def get_pos(self) -> float:
        if not self.is_open:
            return 0.0
        if self.is_paused:
            return self._paused_pos
        pos_ms = pygame.mixer.music.get_pos()
        if pos_ms < 0:
            return self._seek_offset
        return self._seek_offset + (pos_ms / 1000.0)

    def stop(self) -> None:
        if self.is_open:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            self.is_open = False
            self.is_paused = False
            self._seek_offset = 0.0
            self._paused_pos = 0.0

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused


class WindowsMciAudioPlayer(BaseAudioPlayer):
    """Zero-dependency Windows audio player using winmm.dll MCI commands."""

    def __init__(self, media_path: str) -> None:
        super().__init__(media_path)
        if sys.platform != "win32":
            raise RuntimeError("WindowsMciAudioPlayer requires Windows.")

        self.alias = f"cd_win_audio_{id(self)}"
        self._winmm = getattr(ctypes.windll, "winmm", None)
        if not self._winmm:
            raise RuntimeError("Failed to load winmm.dll.")

    @classmethod
    def is_available(cls) -> bool:
        return sys.platform == "win32" and hasattr(ctypes, "windll") and hasattr(ctypes.windll, "winmm")

    def _send_mci(self, command: str) -> int:
        if not self._winmm:
            return -1
        return self._winmm.mciSendStringW(command, None, 0, 0)

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return
        self.stop()
        open_cmd = f'open "{self.media_path}" type mpegvideo alias {self.alias}'
        res = self._send_mci(open_cmd)
        if res == 0:
            self.is_open = True
            self._send_mci(f"set {self.alias} time format milliseconds")
            self._send_mci(f"play {self.alias}")
            self.is_paused = False

    def pause(self) -> None:
        if self.is_open and not self.is_paused:
            self._send_mci(f"pause {self.alias}")
            self.is_paused = True

    def resume(self) -> None:
        if self.is_open and self.is_paused:
            self._send_mci(f"resume {self.alias}")
            self.is_paused = False

    def seek(self, seconds: float) -> None:
        if self.is_open:
            ms = int(max(0.0, float(seconds)) * 1000)
            self._send_mci(f"seek {self.alias} to {ms}")
            if not self.is_paused:
                self._send_mci(f"play {self.alias}")

    def get_pos(self) -> float:
        if not self.is_open or not self._winmm:
            return 0.0
        buf = ctypes.create_unicode_buffer(128)
        res = self._winmm.mciSendStringW(f"status {self.alias} position", buf, 128, 0)
        if res == 0:
            try:
                return float(buf.value) / 1000.0
            except (ValueError, TypeError):
                pass
        return 0.0

    def stop(self) -> None:
        if self.is_open:
            self._send_mci(f"stop {self.alias}")
            self._send_mci(f"close {self.alias}")
            self.is_open = False
            self.is_paused = False

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused


def create_windows_audio_player(media_path: str, no_audio: bool = False) -> BaseAudioPlayer:
    """Factory selecting the best available audio player on Windows."""
    if no_audio:
        return DummyAudioPlayer(media_path)

    if WindowsPygameAudioPlayer.is_available():
        try:
            return WindowsPygameAudioPlayer(media_path)
        except Exception:
            pass

    if WindowsMciAudioPlayer.is_available():
        try:
            return WindowsMciAudioPlayer(media_path)
        except Exception:
            pass

    return DummyAudioPlayer(media_path)
