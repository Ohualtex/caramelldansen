"""
Base audio player interface defining common playback lifecycle methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import os


class BaseAudioPlayer(ABC):
    """
    Abstract base class for all platform-specific audio backends.
    Guarantees a unified API across macOS, Linux, and Windows.
    """

    def __init__(self, media_path: str = "assets/caramell_dansen.mp3"):
        self.media_path = os.path.abspath(media_path)
        self.is_open = False
        self.is_paused = False

    @abstractmethod
    def start(self) -> None:
        """Opens audio resource and begins playback from beginning."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Pauses audio playback."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resumes audio playback from paused position."""
        pass

    @abstractmethod
    def seek(self, target_seconds: float) -> None:
        """Seeks audio to specific target position in seconds."""
        pass

    @abstractmethod
    def get_pos(self) -> float:
        """Returns current playback position in seconds."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops audio and releases system handles."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """Returns True if audio is actively playing."""
        pass
