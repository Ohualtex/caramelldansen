"""
Audio engine package for Caramell Dansen. Automatically selects best player for current platform.
"""

from __future__ import annotations

import sys
from .base import BaseAudioPlayer
from .dummy import DummyAudioPlayer


def get_audio_player(media_path: str = "assets/caramell_dansen.mp3") -> BaseAudioPlayer:
    """Factory creating the best available audio player for the operating system."""
    if sys.platform == "darwin":
        from .macos import MacOSAudioPlayer

        if MacOSAudioPlayer.is_available():
            return MacOSAudioPlayer(media_path)

    return DummyAudioPlayer(media_path)
