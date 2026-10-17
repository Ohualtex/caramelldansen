"""
Strict Platform Abstraction Layer (PAL) interface contracts.
Guarantees clean isolation between core game/player logic and OS-specific drivers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAudioPlayer(ABC):
    """Abstract interface for hardware or platform audio playback backends."""

    def __init__(self, media_path: str) -> None:
        self.media_path = media_path
        self.is_open: bool = False
        self.is_paused: bool = False

    @abstractmethod
    def start(self) -> None:
        """Opens audio resource and begins playback from 0.0s."""
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
    def seek(self, seconds: float) -> None:
        """Seeks audio to the specified target position in seconds."""
        pass

    @abstractmethod
    def get_pos(self) -> float:
        """Returns the current playback position in seconds with millisecond precision."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops audio playback and releases hardware resources."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """Returns True if audio is actively playing."""
        pass


class BaseInputHandler(ABC):
    """Abstract interface for non-blocking keyboard input polling."""

    @abstractmethod
    def poll_key(self) -> str | None:
        """
        Polls for a key press without blocking.
        Returns semantic key tokens ('SPACE', 'QUIT', 'MODE', 'COLOR', 'LOOP',
        'RESTART', 'RIGHT', 'LEFT', 'UP', 'DOWN') or None.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Restores original terminal input flags and modes."""
        pass


class BaseTerminalManager(ABC):
    """Abstract interface for terminal buffer management and window resizing."""

    @abstractmethod
    def enter_fullscreen(self) -> None:
        """Enters alternate screen buffer, hides cursor, and clears screen."""
        pass

    @abstractmethod
    def leave_fullscreen(self) -> None:
        """Restores main screen buffer and unhides cursor."""
        pass

    @abstractmethod
    def get_size(self) -> tuple[int, int]:
        """Returns current terminal dimensions as (columns, rows)."""
        pass

    @abstractmethod
    def check_resized(self) -> bool:
        """Returns True if the terminal window size has changed since last call."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Ensures terminal state is cleanly restored on exit."""
        pass


class BasePlatform(ABC):
    """Unified container encapsulating all OS-specific drivers."""

    @property
    @abstractmethod
    def audio(self) -> BaseAudioPlayer:
        """The active audio player instance for this platform."""
        pass

    @property
    @abstractmethod
    def input(self) -> BaseInputHandler:
        """The active non-blocking input listener for this platform."""
        pass

    @property
    @abstractmethod
    def terminal(self) -> BaseTerminalManager:
        """The active terminal manager for this platform."""
        pass

    def cleanup(self) -> None:
        """Gracefully shuts down audio, input, and terminal."""
        try:
            self.audio.stop()
        except Exception:
            pass
        try:
            self.input.cleanup()
        except Exception:
            pass
        try:
            self.terminal.cleanup()
        except Exception:
            pass
