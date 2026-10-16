"""
Asset management and automatic provisioning for Caramell Dansen terminal player.
Downloads media assets from GitHub Releases if not present locally.
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request

RELEASE_TAG = "v0.0.1"
RELEASE_BASE_URL = f"https://github.com/Ohualtex/caramelldansen/releases/download/{RELEASE_TAG}"

DEFAULT_VIDEO_NAME = "caramell_dansen.mp4"
DEFAULT_AUDIO_NAME = "caramell_dansen.mp3"
DEFAULT_CACHE_NAME = "caramell_dansen.bin"

ASSET_MD5_CHECKSUMS = {
    "caramell_dansen.bin": "8433fce43d9f43b77d7cb67ed7f750e5",
    "caramell_dansen.mp3": "bdc346654f84cfe98bba911bf1561851",
    "caramell_dansen.mp4": "2f2750018417b71a3361f841a79918ce",
}


def compute_md5(filepath: str) -> str:
    """Calculates MD5 hash of a local file in chunks."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


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
    if os.path.isfile(assets_dir_path) and os.path.getsize(assets_dir_path) > 0:
        return assets_dir_path

    if os.path.isfile(filename) and os.path.getsize(filename) > 0:
        return filename

    return os.path.join(get_media_cache_dir(), filename)


def download_asset(filename: str, label: str = "") -> str:
    """Downloads an asset from GitHub Releases and validates its integrity."""
    dest_path = get_asset_path(filename)
    if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
        return dest_path

    # Ensure parent dir exists
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    url = f"{RELEASE_BASE_URL}/{filename}"
    display_label = label or filename
    print(f"[*] Downloading {display_label} from GitHub Releases...")

    def progress(block_num: int, block_size: int, total_size: int):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100.0, downloaded * 100.0 / total_size)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r    [{percent:5.1f}%] {mb:6.1f}MB / {total_mb:6.1f}MB")
        else:
            mb = downloaded / (1024 * 1024)
            sys.stdout.write(f"\r    {mb:6.1f}MB downloaded")
        sys.stdout.flush()

    temp_dest = dest_path + ".tmp"
    try:
        urllib.request.urlretrieve(url, temp_dest, reporthook=progress)
        print()

        expected_md5 = ASSET_MD5_CHECKSUMS.get(filename)
        if expected_md5:
            actual_md5 = compute_md5(temp_dest)
            if actual_md5 != expected_md5.lower():
                raise ValueError(
                    f"Checksum mismatch for {filename}: expected {expected_md5}, got {actual_md5}"
                )

        os.rename(temp_dest, dest_path)
        print(f"[+] Successfully provisioned {filename}")
        return dest_path
    except Exception as e:
        if os.path.exists(temp_dest):
            try:
                os.remove(temp_dest)
            except OSError:
                pass
        print(f"\n[!] Failed to download {filename}: {e}")
        raise


def ensure_playback_assets() -> tuple[str, str]:
    """Ensures that either pre-rendered cache or video + audio are available."""
    cache_path = get_asset_path(DEFAULT_CACHE_NAME)
    audio_path = get_asset_path(DEFAULT_AUDIO_NAME)

    if not os.path.exists(cache_path):
        # Try downloading binary cache directly
        try:
            cache_path = download_asset(DEFAULT_CACHE_NAME, "CDBP Binary Cache (~140MB)")
        except Exception:
            pass

    if not os.path.exists(audio_path):
        try:
            audio_path = download_asset(DEFAULT_AUDIO_NAME, "Audio Track (~5MB)")
        except Exception:
            pass

    return cache_path, audio_path
