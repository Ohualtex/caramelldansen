"""
macOS-native audio player using system afplay or ffplay with graceful signal control.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from .base import BaseAudioPlayer


class MacOSAudioPlayer(BaseAudioPlayer):
    """
    Zero-dependency audio player leveraging ffplay or macOS built-in afplay.
    Uses POSIX signals (SIGSTOP / SIGCONT) for zero-latency pause and resume.
    """

    def __init__(self, media_path: str = "assets/caramell_dansen.mp3"):
        super().__init__(media_path)
        self._proc: subprocess.Popen | None = None
        self._start_perf: float | None = None
        self._seek_offset: float = 0.0
        self._paused_pos: float | None = None
        self._use_ffplay: bool = shutil.which("ffplay") is not None

    @classmethod
    def is_available(cls) -> bool:
        """Checks if current platform is macOS and an audio player is available."""
        return sys.platform == "darwin" and (
            shutil.which("ffplay") is not None or shutil.which("afplay") is not None
        )

    def start(self) -> None:
        """Starts audio playback from the beginning."""
        if not os.path.exists(self.media_path):
            return

        self.stop()
        self._seek_offset = 0.0
        self._paused_pos = None

        cmd = (
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", self.media_path]
            if self._use_ffplay
            else ["afplay", self.media_path]
        )

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._start_perf = time.perf_counter()
            self.is_open = True
            self.is_paused = False
        except Exception:
            self.is_open = False

    def pause(self) -> None:
        """Pauses audio playback using SIGSTOP."""
        if self._proc and self._proc.poll() is None and not self.is_paused:
            try:
                os.kill(self._proc.pid, signal.SIGSTOP)
                self._paused_pos = self.get_pos()
                self.is_paused = True
            except OSError:
                pass

    def resume(self) -> None:
        """Resumes audio playback using SIGCONT."""
        if self._proc and self._proc.poll() is None and self.is_paused:
            try:
                os.kill(self._proc.pid, signal.SIGCONT)
                if self._paused_pos is not None and self._start_perf is not None:
                    # Adjust reference clock to account for paused duration
                    self._start_perf = time.perf_counter() - (self._paused_pos - self._seek_offset)
                self.is_paused = False
                self._paused_pos = None
            except OSError:
                pass

    def seek(self, target_seconds: float) -> None:
        """Seeks to target time in seconds."""
        target_seconds = max(0.0, target_seconds)
        self.stop()

        cmd = (
            [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-ss",
                str(target_seconds),
                "-loglevel",
                "quiet",
                self.media_path,
            ]
            if self._use_ffplay
            else ["afplay", self.media_path]
        )

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._seek_offset = target_seconds
            self._start_perf = time.perf_counter()
            self._paused_pos = None
            self.is_open = True
            self.is_paused = False
        except Exception:
            self.is_open = False

    def get_pos(self) -> float:
        """Returns current playback position in seconds."""
        if self.is_paused and self._paused_pos is not None:
            return self._paused_pos

        if self._start_perf is not None:
            return self._seek_offset + (time.perf_counter() - self._start_perf)
        return self._seek_offset

    def stop(self) -> None:
        """Stops and terminates the audio process."""
        if self._proc:
            try:
                if self.is_paused:
                    os.kill(self._proc.pid, signal.SIGCONT)
                self._proc.terminate()
                self._proc.wait(timeout=0.2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        self.is_open = False
        self.is_paused = False
        self._start_perf = None

    def is_playing(self) -> bool:
        """Checks if process is alive."""
        return self._proc is not None and self._proc.poll() is None
