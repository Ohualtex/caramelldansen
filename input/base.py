"""
Base keyboard input handler interface for Caramell Dansen terminal player.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseInputHandler(ABC):
    """Abstract base class for keyboard listeners across platforms."""

    @abstractmethod
    def poll_key(self) -> str | None:
        """Polls for a single pressed key without blocking. Returns key name or None."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Restores original terminal input settings."""
        pass
