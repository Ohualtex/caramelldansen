"""
macOS isolated platform driver package.
"""

from __future__ import annotations

from ..base import BasePlatform, BaseAudioPlayer, BaseInputHandler, BaseTerminalManager
from .terminal import MacOSTerminalManager
from .input import MacOSInputHandler
from .audio import create_macos_audio_player


class MacOSPlatform(BasePlatform):
    """Encapsulates macOS-native terminal, input, and audio subsystems."""

    def __init__(self, audio_path: str = "assets/caramell_dansen.mp3", no_audio: bool = False) -> None:
        self._terminal = MacOSTerminalManager()
        self._input = MacOSInputHandler()
        self._audio = create_macos_audio_player(media_path=audio_path, no_audio=no_audio)

    @property
    def audio(self) -> BaseAudioPlayer:
        return self._audio

    @property
    def input(self) -> BaseInputHandler:
        return self._input

    @property
    def terminal(self) -> BaseTerminalManager:
        return self._terminal


__all__ = ["MacOSPlatform"]
