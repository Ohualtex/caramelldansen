"""
Asset management and automatic provisioning for Caramelldansen terminal player.
Downloads pre-rendered binary cache and audio from GitHub Releases with live progress bar,
MD5 integrity verification, and persistent OS-standard caching.
"""

from __future__ import annotations

import hashlib
import os
import socket
import sys
import time
import urllib.request

DEFAULT_VIDEO_NAME = "caramell_dansen.mp4"
DEFAULT_AUDIO_NAME = "caramell_dansen.mp3"
DEFAULT_CACHE_NAME = "caramell_dansen.bin"

CACHE_URLS = [
    "https://github.com/Ohualtex/caramelldansen/releases/download/v0.0.1/caramell_dansen.bin",
]
CACHE_MD5 = "8433fce43d9f43b77d7cb67ed7f750e5"

AUDIO_URLS = [
    "https://github.com/Ohualtex/caramelldansen/releases/download/v0.0.1/caramell_dansen.mp3",
]
AUDIO_MD5 = "bdc346654f84cfe98bba911bf1561851"

VIDEO_URLS = [
    "https://github.com/Ohualtex/caramelldansen/releases/download/v0.0.1/caramell_dansen.mp4",
]
VIDEO_MD5 = "2f2750018417b71a3361f841a79918ce"


def get_media_cache_dir() -> str:
    """Returns the platform-standard persistent cache directory for Caramelldansen."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        cache_dir = os.path.join(base, "caramelldansen")
    elif sys.platform == "darwin":
        cache_dir = os.path.expanduser("~/Library/Caches/caramelldansen")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        cache_dir = os.path.join(base, "caramelldansen")

    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_asset_path(filename: str) -> str:
    """
    Finds the asset path with the following priority:
    1. Check assets/ folder in current directory (local dev / repository checkout).
    2. Check current working directory.
    3. Return path inside OS persistent platform cache directory.
    """
    assets_dir_path = os.path.join("assets", filename)
    if os.path.exists(assets_dir_path):
        return assets_dir_path

    if os.path.exists(filename):
        return filename

    return os.path.join(get_media_cache_dir(), filename)


def verify_md5(file_path: str, expected_md5: str) -> bool:
    """Verifies MD5 hash of a file for cryptographic integrity."""
    if not os.path.exists(file_path):
        return False
    hasher = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest().lower() == expected_md5.lower()
    except Exception:
        return False


def _download_file(url_or_urls: str | list[str], destination: str, expected_md5: str, label: str) -> str:
    """Downloads a remote file with progress reporting and MD5 verification."""
    if os.path.exists(destination):
        if verify_md5(destination, expected_md5):
            return destination
        else:
            print(f"[!] Existing {label} integrity check failed. Re-downloading...")
            try:
                os.remove(destination)
            except OSError:
                pass

    urls = [url_or_urls] if isinstance(url_or_urls, str) else list(url_or_urls)
    socket.setdefaulttimeout(30.0)

    class ProgressHook:
        def __init__(self):
            self.start_time = time.time()
            self.last_update = 0.0

        def __call__(self, block_num: int, block_size: int, total_size: int) -> None:
            now = time.time()
            if now - self.last_update < 0.1 and block_num * block_size < total_size:
                return
            self.last_update = now

            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, int(downloaded * 100 / total_size))
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                elapsed = max(0.001, now - self.start_time)
                speed_mb = mb_downloaded / elapsed
                remaining_bytes = total_size - downloaded
                eta = (remaining_bytes / (speed_mb * 1024 * 1024)) if speed_mb > 0 else 0

                bar_width = 30
                filled = int(bar_width * percent / 100)
                bar = "=" * filled + "-" * (bar_width - filled)
                sys.stdout.write(
                    f"\r[{bar}] {percent:3d}% ({mb_downloaded:5.1f}/{mb_total:5.1f} MB) | "
                    f"{speed_mb:4.1f} MB/s | ETA: {int(eta):2d}s"
                )
                sys.stdout.flush()

    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Caramelldansen-Terminal-Player/1.0")]
    urllib.request.install_opener(opener)

    last_error: Exception | None = None
    for idx, url in enumerate(urls, 1):
        print(f"[*] Downloading {label}...")
        temp_destination = destination + ".tmp"
        if os.path.exists(temp_destination):
            try:
                os.remove(temp_destination)
            except OSError:
                pass

        try:
            urllib.request.urlretrieve(url, temp_destination, reporthook=ProgressHook())
            sys.stdout.write("\n")
            sys.stdout.flush()

            print(f"[*] Verifying {label} integrity (MD5)...")
            if verify_md5(temp_destination, expected_md5):
                print(f"[+] {label} verified successfully.")
                os.replace(temp_destination, destination)
                return destination
            else:
                raise ValueError(f"{label} MD5 mismatch. File may be corrupted.")
        except KeyboardInterrupt:
            print(f"\n[!] Download cancelled by user.")
            if os.path.exists(temp_destination):
                try:
                    os.remove(temp_destination)
                except OSError:
                    pass
            raise
        except Exception as e:
            last_error = e
            if os.path.exists(temp_destination):
                try:
                    os.remove(temp_destination)
                except OSError:
                    pass
            print(f"\n[!] Failed to download from {url}: {e}")
            if idx < len(urls):
                print("[*] Retrying with alternative mirror...")

    raise RuntimeError(f"Failed to provision {label}: {last_error}")


def download_binary_cache(destination: str | None = None) -> str:
    """Downloads the pre-rendered Caramelldansen TrueColor CDBP binary cache file."""
    dest = destination or get_asset_path(DEFAULT_CACHE_NAME)
    return _download_file(CACHE_URLS, dest, CACHE_MD5, "Caramelldansen Binary Cache")


def download_audio(destination: str | None = None) -> str:
    """Downloads the original Caramelldansen MP3 audio file."""
    dest = destination or get_asset_path(DEFAULT_AUDIO_NAME)
    return _download_file(AUDIO_URLS, dest, AUDIO_MD5, "Caramelldansen Audio")


def ensure_assets(cache_path: str | None = None, audio_path: str | None = None) -> tuple[str, str]:
    """
    Ensures required assets are available locally.
    Downloads them automatically if missing. Returns (cache_path, audio_path).
    """
    target_cache = cache_path or get_asset_path(DEFAULT_CACHE_NAME)
    target_audio = audio_path or get_asset_path(DEFAULT_AUDIO_NAME)

    if not os.path.exists(target_cache):
        download_binary_cache(target_cache)

    if not os.path.exists(target_audio):
        download_audio(target_audio)

    return target_cache, target_audio


if __name__ == "__main__":
    ensure_assets()
