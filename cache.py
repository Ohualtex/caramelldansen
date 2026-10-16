"""
CDBP (Caramell Dansen Binary Pre-rendered) cache engine.

Provides zero-CPU, instant random-access playback of color Caramelldansen frames
by storing RGB video frames compressed with zlib alongside an indexed lookup table
and loop-point markers.
"""

from __future__ import annotations

import os
import struct
import subprocess
import time
import zlib
from typing import Callable, Optional, Tuple
import numpy as np

# Header specification (Total: 32 bytes)
# <4s : Magic bytes (b"CDBP")
# H   : Version (uint16 = 1)
# H   : Width (uint16)
# H   : Height (uint16)
# f   : FPS (float32)
# I   : Total frames (uint32)
# B   : Color format (1 = RGB24 zlib)
# I   : Loop start frame (uint32)
# I   : Loop end frame (uint32)
# 3s  : Reserved padding
CDBP_MAGIC = b"CDBP"
CDBP_VERSION = 1
COLOR_FORMAT_RGB24 = 1

HEADER_STRUCT = struct.Struct("<4sHHHfIBII3s")
INDEX_ENTRY_STRUCT = struct.Struct("<IH")  # offset (uint32), compressed_size (uint16)


class BinaryCacheError(Exception):
    """Exception raised for cache corruption or builder errors."""
    pass


class BinaryCacheBuilder:
    """Encodes MP4 video frames into a high-speed CDBP binary container using ffmpeg."""

    @staticmethod
    def build_cache(
        video_path: str,
        output_path: str,
        target_width: int = 160,
        target_height: int = 90,
        fps: float = 25.0,
        loop_start_sec: float = 30.5,
        loop_end_sec: float = 59.5,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
    ) -> None:
        """
        Extracts RGB frames from source video using ffmpeg, compresses each frame
        with zlib, and builds an indexed CDBP binary cache file.
        """
        if not os.path.exists(video_path):
            raise BinaryCacheError(f"Source video not found at '{video_path}'.")

        # Get video duration using ffprobe
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        try:
            dur_str = subprocess.check_output(probe_cmd, text=True).strip()
            duration = float(dur_str)
        except Exception as e:
            raise BinaryCacheError(f"Failed to probe video duration: {e}")

        total_frames = int(duration * fps)
        if total_frames <= 0:
            raise BinaryCacheError("Invalid video duration or empty stream.")

        loop_start_frame = int(loop_start_sec * fps)
        loop_end_frame = int(loop_end_sec * fps)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        temp_output = output_path + ".tmp"
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass

        frame_bytes_len = target_width * target_height * 3
        ffmpeg_cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            video_path,
            "-vf",
            f"scale={target_width}:{target_height}",
            "-r",
            str(fps),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]

        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=frame_bytes_len * 4,
        )

        index_entries: list[tuple[int, int]] = []
        start_time = time.perf_counter()

        try:
            with open(temp_output, "wb") as f:
                # 1. Placeholder header (32 bytes)
                f.write(b"\x00" * HEADER_STRUCT.size)

                # 2. Frames will be written directly, indices tracked in memory
                current_frame = 0
                while True:
                    raw_frame = proc.stdout.read(frame_bytes_len)
                    if not raw_frame or len(raw_frame) < frame_bytes_len:
                        break

                    compressed = zlib.compress(raw_frame, level=6)
                    offset = f.tell()
                    comp_size = len(compressed)

                    if comp_size > 65535:
                        raise BinaryCacheError(
                            f"Compressed frame {current_frame} exceeded uint16 max size ({comp_size} bytes)."
                        )

                    f.write(compressed)
                    index_entries.append((offset, comp_size))
                    current_frame += 1

                    if progress_callback and (current_frame % 25 == 0 or current_frame == total_frames):
                        elapsed = time.perf_counter() - start_time
                        progress_callback(current_frame, total_frames, elapsed)

                actual_total_frames = len(index_entries)
                if actual_total_frames == 0:
                    raise BinaryCacheError("No frames were extracted from the video stream.")

                # 3. Write index table at end of file
                index_table_offset = f.tell()
                for offset, comp_size in index_entries:
                    f.write(INDEX_ENTRY_STRUCT.pack(offset, comp_size))

                # 4. Seek back and write final header
                f.seek(0)
                f.write(
                    HEADER_STRUCT.pack(
                        CDBP_MAGIC,
                        CDBP_VERSION,
                        target_width,
                        target_height,
                        fps,
                        actual_total_frames,
                        COLOR_FORMAT_RGB24,
                        loop_start_frame,
                        loop_end_frame,
                        b"\x00" * 3,
                    )
                )

        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait()

        # Atomic rename
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(temp_output, output_path)


class BinaryCacheReader:
    """Reads CDBP binary cache files with instant seek and low memory overhead."""

    def __init__(self, cache_path: str):
        self.cache_path = os.path.abspath(cache_path)
        if not os.path.exists(self.cache_path):
            raise BinaryCacheError(f"Cache file not found at '{self.cache_path}'.")

        self._file = open(self.cache_path, "rb")
        header_data = self._file.read(HEADER_STRUCT.size)
        if len(header_data) < HEADER_STRUCT.size:
            raise BinaryCacheError("Incomplete cache header.")

        (
            magic,
            version,
            self.width,
            self.height,
            self.fps,
            self.total_frames,
            self.color_format,
            self.loop_start_frame,
            self.loop_end_frame,
            _,
        ) = HEADER_STRUCT.unpack(header_data)

        if magic != CDBP_MAGIC:
            raise BinaryCacheError(f"Invalid magic bytes '{magic!r}', expected '{CDBP_MAGIC!r}'.")
        if version != CDBP_VERSION:
            raise BinaryCacheError(f"Unsupported CDBP version {version}.")

        self.duration = float(self.total_frames) / float(self.fps) if self.fps > 0 else 0.0
        self.loop_start_sec = float(self.loop_start_frame) / float(self.fps) if self.fps > 0 else 0.0
        self.loop_end_sec = float(self.loop_end_frame) / float(self.fps) if self.fps > 0 else self.duration

        # Read index table
        index_table_size = self.total_frames * INDEX_ENTRY_STRUCT.size
        self._file.seek(-index_table_size, os.SEEK_END)
        index_data = self._file.read(index_table_size)
        if len(index_data) < index_table_size:
            raise BinaryCacheError("Incomplete index table.")

        # Unpack index table: offsets (uint32) and sizes (uint16)
        table = np.frombuffer(index_data, dtype=[("offset", "<u4"), ("size", "<u2")])
        self._offsets = table["offset"]
        self._sizes = table["size"]

    def get_frame(self, frame_index: int) -> np.ndarray:
        """Retrieves and decompresses an RGB frame as numpy array (H, W, 3)."""
        idx = max(0, min(self.total_frames - 1, frame_index))
        offset = int(self._offsets[idx])
        size = int(self._sizes[idx])

        self._file.seek(offset)
        compressed = self._file.read(size)
        raw_rgb = zlib.decompress(compressed)

        frame = np.frombuffer(raw_rgb, dtype=np.uint8).reshape((self.height, self.width, 3))
        return frame

    def get_frame_for_time(self, seconds: float) -> Tuple[np.ndarray, int]:
        """Returns the frame corresponding to the specified playback time."""
        seconds = max(0.0, seconds)
        idx = int(seconds * self.fps)
        idx = min(self.total_frames - 1, idx)
        return self.get_frame(idx), idx

    def close(self) -> None:
        """Closes the underlying binary file."""
        if hasattr(self, "_file") and self._file:
            self._file.close()

    def __enter__(self) -> "BinaryCacheReader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
