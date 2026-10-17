"""
macOS audio player subsystem.
Prioritizes hardware-accelerated Pygame with CoreAudio pop mitigation,
falling back to built-in afplay command.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
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
    """Fallback silent timer-based player."""

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


class MacOSPygameAudioPlayer(BaseAudioPlayer):
    """Pygame audio player optimized for macOS CoreAudio buffer requirements."""

    def __init__(self, media_path: str) -> None:
        super().__init__(media_path)
        if not _HAS_PYGAME:
            raise RuntimeError("pygame is not available.")

        if not pygame.mixer.get_init():
            # macOS CoreAudio requires 4096 buffer size to prevent underruns
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
            except Exception:
                pygame.mixer.init(buffer=4096)

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

                # Mute momentarily to prevent CoreAudio stream crackle on pause
                pygame.mixer.music.set_volume(0.0)
                pygame.mixer.music.pause()
                pygame.mixer.music.set_volume(1.0)
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
                    pygame.mixer.music.set_volume(0.0)
                    pygame.mixer.music.pause()
                    pygame.mixer.music.set_volume(1.0)
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
                pygame.mixer.music.set_volume(0.0)
                pygame.mixer.music.stop()
                pygame.mixer.music.set_volume(1.0)
            except Exception:
                pass
            self.is_open = False
            self.is_paused = False
            self._seek_offset = 0.0
            self._paused_pos = 0.0

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused


class MacOSAfplayAudioPlayer(BaseAudioPlayer):
    """Zero-dependency fallback player using macOS native afplay."""

    def __init__(self, media_path: str) -> None:
        super().__init__(media_path)
        self._proc: subprocess.Popen | None = None
        self._start_perf: float | None = None
        self._seek_offset: float = 0.0
        self._paused_pos: float | None = None

    @classmethod
    def is_available(cls) -> bool:
        return sys.platform == "darwin" and shutil.which("afplay") is not None

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return
        self.stop()
        try:
            self._proc = subprocess.Popen(
                ["afplay", self.media_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.is_open = True
            self.is_paused = False
            self._start_perf = time.perf_counter()
            self._seek_offset = 0.0
            self._paused_pos = None
        except Exception:
            self._proc = None
            self.is_open = False

    def pause(self) -> None:
        if self._proc and self._proc.poll() is None and not self.is_paused:
            sig_stop = getattr(signal, "SIGSTOP", None)
            if sig_stop:
                try:
                    os.kill(self._proc.pid, sig_stop)
                    self.is_paused = True
                    self._paused_pos = self.get_pos()
                except Exception:
                    pass

    def resume(self) -> None:
        if self._proc and self._proc.poll() is None and self.is_paused:
            sig_cont = getattr(signal, "SIGCONT", None)
            if sig_cont:
                try:
                    os.kill(self._proc.pid, sig_cont)
                    self.is_paused = False
                    if self._paused_pos is not None:
                        self._start_perf = time.perf_counter()
                        self._seek_offset = self._paused_pos
                        self._paused_pos = None
                except Exception:
                    pass

    def seek(self, seconds: float) -> None:
        # afplay does not support live seeking; restart subprocess from offset
        if not os.path.exists(self.media_path):
            return
        self.stop()
        target = max(0.0, float(seconds))
        try:
            cmd = ["afplay", "-t", str(target), self.media_path]
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_open = True
            self.is_paused = False
            self._start_perf = time.perf_counter()
            self._seek_offset = target
            self._paused_pos = None
        except Exception:
            self._proc = None

    def get_pos(self) -> float:
        if not self.is_open:
            return 0.0
        if self.is_paused and self._paused_pos is not None:
            return self._paused_pos
        if self._start_perf is not None:
            return self._seek_offset + (time.perf_counter() - self._start_perf)
        return self._seek_offset

    def stop(self) -> None:
        if self._proc:
            try:
                if self.is_paused:
                    sig_cont = getattr(signal, "SIGCONT", None)
                    if sig_cont:
                        os.kill(self._proc.pid, sig_cont)
                sig_int = getattr(signal, "SIGINT", None)
                if sig_int:
                    os.kill(self._proc.pid, sig_int)
                    self._proc.wait(timeout=0.15)
                if self._proc.poll() is None:
                    self._proc.terminate()
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None
        self.is_open = False
        self.is_paused = False
        self._start_perf = None
        self._seek_offset = 0.0
        self._paused_pos = None

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused and (self._proc is not None and self._proc.poll() is None)


class MacOSFFplayAudioPlayer(BaseAudioPlayer):
    """
    Hardware/CLI audio player using ffplay with millisecond-accurate seeking and low latency.
    Supports SIGSTOP/SIGCONT for zero-overhead pause and resume.
    """

    def __init__(self, media_path: str) -> None:
        super().__init__(media_path)
        self._proc: subprocess.Popen | None = None
        self._start_perf: float | None = None
        self._seek_offset: float = 0.0
        self._paused_pos: float | None = None

    @classmethod
    def is_available(cls) -> bool:
        return sys.platform == "darwin" and shutil.which("ffplay") is not None

    def start(self) -> None:
        if not os.path.exists(self.media_path):
            return
        self.stop()
        try:
            self._proc = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", self.media_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.is_open = True
            self.is_paused = False
            self._start_perf = time.perf_counter()
            self._seek_offset = 0.0
            self._paused_pos = None
        except Exception:
            self._proc = None
            self.is_open = False

    def pause(self) -> None:
        if self._proc and self._proc.poll() is None and not self.is_paused:
            sig_stop = getattr(signal, "SIGSTOP", None)
            if sig_stop:
                try:
                    os.kill(self._proc.pid, sig_stop)
                    self.is_paused = True
                    self._paused_pos = self.get_pos()
                except Exception:
                    pass

    def resume(self) -> None:
        if self._proc and self._proc.poll() is None and self.is_paused:
            sig_cont = getattr(signal, "SIGCONT", None)
            if sig_cont:
                try:
                    os.kill(self._proc.pid, sig_cont)
                    self.is_paused = False
                    if self._paused_pos is not None:
                        self._start_perf = time.perf_counter()
                        self._seek_offset = self._paused_pos
                        self._paused_pos = None
                except Exception:
                    pass

    def seek(self, seconds: float) -> None:
        if not os.path.exists(self.media_path):
            return
        self.stop()
        target = max(0.0, float(seconds))
        try:
            cmd = [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-ss",
                str(target),
                "-loglevel",
                "quiet",
                self.media_path,
            ]
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_open = True
            self.is_paused = False
            self._start_perf = time.perf_counter()
            self._seek_offset = target
            self._paused_pos = None
        except Exception:
            self._proc = None

    def get_pos(self) -> float:
        if not self.is_open:
            return 0.0
        if self.is_paused and self._paused_pos is not None:
            return self._paused_pos
        if self._start_perf is not None:
            return self._seek_offset + (time.perf_counter() - self._start_perf)
        return self._seek_offset

    def stop(self) -> None:
        if self._proc:
            try:
                if self.is_paused:
                    sig_cont = getattr(signal, "SIGCONT", None)
                    if sig_cont:
                        os.kill(self._proc.pid, sig_cont)
                self._proc.terminate()
                self._proc.wait(timeout=0.2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None
        self.is_open = False
        self.is_paused = False
        self._start_perf = None
        self._seek_offset = 0.0
        self._paused_pos = None

    def is_playing(self) -> bool:
        return self.is_open and not self.is_paused and (self._proc is not None and self._proc.poll() is None)


def create_macos_audio_player(media_path: str, no_audio: bool = False) -> BaseAudioPlayer:
    """Factory selecting the best available audio player on macOS."""
    if no_audio:
        return DummyAudioPlayer(media_path)

    if MacOSPygameAudioPlayer.is_available():
        try:
            return MacOSPygameAudioPlayer(media_path)
        except Exception:
            pass

    if MacOSFFplayAudioPlayer.is_available():
        try:
            return MacOSFFplayAudioPlayer(media_path)
        except Exception:
            pass

    if MacOSAfplayAudioPlayer.is_available():
        try:
            return MacOSAfplayAudioPlayer(media_path)
        except Exception:
            pass

    return DummyAudioPlayer(media_path)
