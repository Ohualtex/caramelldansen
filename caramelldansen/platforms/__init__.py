"""
Platform Abstraction Layer (PAL) factory for Caramelldansen.
Dynamically resolves and instantiates the fully isolated OS-specific platform driver.
"""

from __future__ import annotations

import sys
from .base import BasePlatform, BaseAudioPlayer, BaseInputHandler, BaseTerminalManager


def get_platform(audio_path: str = "assets/caramell_dansen.mp3", no_audio: bool = False) -> BasePlatform:
    """
    Factory function returning the isolated platform driver for the host OS.
    Imports are isolated and lazy to guarantee zero spillover.
    """
    if sys.platform == "win32":
        from .windows import WindowsPlatform

        return WindowsPlatform(audio_path=audio_path, no_audio=no_audio)

    elif sys.platform == "darwin":
        from .macos import MacOSPlatform

        return MacOSPlatform(audio_path=audio_path, no_audio=no_audio)

    else:
        from .linux import LinuxPlatform

        return LinuxPlatform(audio_path=audio_path, no_audio=no_audio)


__all__ = [
    "BasePlatform",
    "BaseAudioPlayer",
    "BaseInputHandler",
    "BaseTerminalManager",
    "get_platform",
]
