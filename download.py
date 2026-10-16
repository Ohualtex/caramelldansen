"""
Asset management and automatic provisioning for Caramell Dansen terminal player.
Handles local paths and verification.
"""

from __future__ import annotations

import hashlib
import os
import sys

DEFAULT_VIDEO_NAME = "caramell_dansen.mp4"
DEFAULT_AUDIO_NAME = "caramell_dansen.mp3"
DEFAULT_CACHE_NAME = "caramell_dansen.bin"


def get_media_cache_dir() -> str:
    """Returns platform standard persistent cache directory."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        cache_dir = os.path.join(base, "caramell-dansen")
    elif sys.platform == "darwin":
        cache_dir = os.path.expanduser("~/Library/Caches/caramell-dansen")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        cache_dir = os.path.join(base, "caramell-dansen")

    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_asset_path(filename: str) -> str:
    """
    Finds asset path:
    1. Check assets/ folder in current directory.
    2. Check current working directory.
    3. Check persistent platform cache directory.
    """
    assets_dir_path = os.path.join("assets", filename)
    if os.path.exists(assets_dir_path):
        return assets_dir_path

    if os.path.exists(filename):
        return filename

    return os.path.join(get_media_cache_dir(), filename)


def verify_md5(file_path: str, expected_md5: str) -> bool:
    """Verifies MD5 hash of an asset for integrity."""
    if not os.path.exists(file_path):
        return False
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower() == expected_md5.lower()
