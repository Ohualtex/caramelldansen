"""
High-performance color and Unicode terminal rendering engine for Caramell Dansen.
Supports TrueColor (24-bit) halfblock, color-ASCII, and Braille 2x4 dot matrix.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Optional, Tuple
import numpy as np

# ASCII brightness ramp (from dark to light)
ASCII_CHARS = np.array(list(" .:-=+*#%@"), dtype="<U1")

# Braille dot weights for 2x4 dot matrix
# Dot positions:
# (0,0)=0x01, (1,0)=0x02, (2,0)=0x04, (3,0)=0x40
# (0,1)=0x08, (1,1)=0x10, (2,1)=0x20, (3,1)=0x80
BRAILLE_BASE = 0x2800


def get_terminal_size(fallback: Tuple[int, int] = (80, 24)) -> Tuple[int, int]:
    """
    Returns real-time terminal dimensions (columns, lines).
    Bypasses static os.environ['COLUMNS'] / ['LINES'] caches by querying
    file descriptors directly via kernel ioctl.
    """
    for stream in (sys.stdout, sys.stdin, sys.stderr):
        try:
            if hasattr(stream, "fileno"):
                size = os.get_terminal_size(stream.fileno())
                if size.columns > 0 and size.lines > 0:
                    return size.columns, size.lines
        except (AttributeError, ValueError, OSError):
            continue

    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
        try:
            size = os.get_terminal_size(fd)
            if size.columns > 0 and size.lines > 0:
                return size.columns, size.lines
        finally:
            os.close(fd)
    except Exception:
        pass

    cols, lines = shutil.get_terminal_size(fallback=fallback)
    return max(4, cols), max(2, lines)


class TerminalRenderer:
    """
    Renders RGB video frames into ANSI TrueColor terminal character buffers.
    Optimized for zero-flicker and minimal I/O overhead.
    """

    MODES = ["halfblock", "color-ascii", "braille"]

    def __init__(
        self,
        mode: str = "halfblock",
        aspect_ratio: float = 16.0 / 9.0,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
    ):
        self.mode = mode if mode in self.MODES else "halfblock"
        self.aspect_ratio = aspect_ratio
        self.target_width = target_width
        self.target_height = target_height

        # Cached grid mapping
        self._grid_key = None
        self._y_indices = None
        self._x_indices = None

    def set_mode(self, mode: str) -> None:
        """Switches the active rendering mode."""
        if mode in self.MODES:
            self.mode = mode
            self._grid_key = None

    def cycle_mode(self) -> str:
        """Cycles to the next available rendering mode and returns it."""
        idx = (self.MODES.index(self.mode) + 1) % len(self.MODES)
        self.set_mode(self.MODES[idx])
        return self.mode

    def get_dimensions(
        self,
        terminal_cols: Optional[int] = None,
        terminal_lines: Optional[int] = None,
    ) -> Tuple[int, int, int, int, int, int]:
        """
        Calculates character width, height, required pixel width/height,
        and margin paddings to preserve video aspect ratio centered in terminal.

        Returns: (char_w, char_h, pix_w, pix_h, pad_left, pad_top)
        """
        if terminal_cols is None or terminal_lines is None:
            cols, lines = get_terminal_size(fallback=(80, 24))
        else:
            cols, lines = max(4, terminal_cols), max(2, terminal_lines)

        # Reserve lines for bottom HUD/status bar and safety margins
        avail_w = max(4, self.target_width if self.target_width is not None else (cols - 2))
        avail_h = max(2, self.target_height if self.target_height is not None else (lines - 3))

        ar = self.aspect_ratio

        if self.mode == "halfblock":
            # 1 char cell = 1 horizontal pixel, 2 vertical pixels (half-block ▀).
            # Terminal character cells are ~1:2 ratio (height is twice width).
            # Therefore, 2 vertical pixels inside 1 character cell make square pixels!
            # char_h = char_w / (ar * 2)
            h_by_w = int(round(avail_w / (ar * 2.0)))
            w_by_h = int(round(avail_h * 2.0 * ar))

            if h_by_w <= avail_h:
                char_w = avail_w
                char_h = max(2, h_by_w)
            else:
                char_w = min(avail_w, max(4, w_by_h))
                char_h = avail_h

            pix_w = char_w
            pix_h = char_h * 2

        elif self.mode == "braille":
            # Braille character has 2x4 dots (width 2, height 4).
            # Aspect ratio correction: char_cell is 1:2.
            # 2 dots wide, 4 dots tall matches the 1:2 cell ratio perfectly!
            # char_h = char_w / ar
            h_by_w = int(round(avail_w / ar))
            w_by_h = int(round(avail_h * ar))

            if h_by_w <= avail_h:
                char_w = avail_w
                char_h = max(2, h_by_w)
            else:
                char_w = min(avail_w, max(4, w_by_h))
                char_h = avail_h

            pix_w = char_w * 2
            pix_h = char_h * 4

        else:
            # color-ascii
            # 1 character cell = 1 pixel.
            # Because cell is 1:2, char_h = char_w / (ar * 2)
            h_by_w = int(round(avail_w / (ar * 2.0)))
            w_by_h = int(round(avail_h * 2.0 * ar))

            if h_by_w <= avail_h:
                char_w = avail_w
                char_h = max(2, h_by_w)
            else:
                char_w = min(avail_w, max(4, w_by_h))
                char_h = avail_h

            pix_w = char_w
            pix_h = char_h

        pad_left = max(0, (cols - char_w) // 2)
        pad_top = max(0, (lines - 3 - char_h) // 2)

        return char_w, char_h, pix_w, pix_h, pad_left, pad_top

    def resize_frame(self, frame_rgb: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """Fast nearest-neighbor downsampling of an RGB frame."""
        src_h, src_w, _ = frame_rgb.shape
        if src_w == target_w and src_h == target_h:
            return frame_rgb

        # Cache coordinate mapping for identical resolutions
        key = (src_w, src_h, target_w, target_h)
        if self._grid_key != key:
            self._x_indices = (np.linspace(0, src_w - 1, target_w)).astype(np.int32)
            self._y_indices = (np.linspace(0, src_h - 1, target_h)).astype(np.int32)
            self._grid_key = key

        return frame_rgb[self._y_indices[:, None], self._x_indices]

    def render(
        self,
        frame_rgb: np.ndarray,
        terminal_cols: Optional[int] = None,
        terminal_lines: Optional[int] = None,
    ) -> str:
        """
        Converts an RGB numpy array (H, W, 3) into an ANSI formatted string
        centered and ready for terminal output.
        """
        char_w, char_h, pix_w, pix_h, pad_left, pad_top = self.get_dimensions(
            terminal_cols, terminal_lines
        )
        scaled = self.resize_frame(frame_rgb, pix_w, pix_h)

        left_margin = " " * pad_left
        lines: list[str] = ["\033[K\n" * pad_top] if pad_top > 0 else []

        if self.mode == "halfblock":
            lines.extend(self._render_halfblock(scaled, char_w, char_h, left_margin))
        elif self.mode == "color-ascii":
            lines.extend(self._render_color_ascii(scaled, char_w, char_h, left_margin))
        elif self.mode == "braille":
            lines.extend(self._render_braille(scaled, char_w, char_h, left_margin))
        else:
            lines.extend(self._render_halfblock(scaled, char_w, char_h, left_margin))

        return "".join(lines)

    def _render_halfblock(
        self, frame: np.ndarray, char_w: int, char_h: int, margin: str
    ) -> list[str]:
        """
        Renders halfblock (▀) with upper pixel as foreground and lower pixel as background.
        Optimizes ANSI output by caching last emitted colors.
        """
        output: list[str] = []
        top_pixels = frame[0::2, :, :]
        bot_pixels = frame[1::2, :, :]

        # TrueColor Halfblock with ANSI run-length compression
        for y in range(char_h):
            output.append(margin)
            last_fg = (-1, -1, -1)
            last_bg = (-1, -1, -1)

            row_top = top_pixels[y]
            row_bot = bot_pixels[y]

            for x in range(char_w):
                rt, gt, bt = int(row_top[x, 0]), int(row_top[x, 1]), int(row_top[x, 2])
                rb, gb, bb = int(row_bot[x, 0]), int(row_bot[x, 1]), int(row_bot[x, 2])

                # Check if colors need changing
                if (rt, gt, bt) != last_fg:
                    output.append(f"\033[38;2;{rt};{gt};{bt}m")
                    last_fg = (rt, gt, bt)
                if (rb, gb, bb) != last_bg:
                    output.append(f"\033[48;2;{rb};{gb};{bb}m")
                    last_bg = (rb, gb, bb)

                output.append("▀")

            output.append("\033[0m\033[K\n")

        return output

    def _render_color_ascii(
        self, frame: np.ndarray, char_w: int, char_h: int, margin: str
    ) -> list[str]:
        """Renders ASCII characters colored by the pixel's RGB."""
        output: list[str] = []
        lum = (frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114).astype(np.float32)
        indices = (lum * ((len(ASCII_CHARS) - 1) / 255.0)).astype(np.int32)

        for y in range(char_h):
            output.append(margin)
            last_fg = (-1, -1, -1)
            row_chars = ASCII_CHARS[indices[y]]
            row_rgb = frame[y]

            for x in range(char_w):
                r, g, b = int(row_rgb[x, 0]), int(row_rgb[x, 1]), int(row_rgb[x, 2])
                if (r, g, b) != last_fg:
                    output.append(f"\033[38;2;{r};{g};{b}m")
                    last_fg = (r, g, b)
                output.append(row_chars[x])

            output.append("\033[0m\033[K\n")

        return output

    def _render_braille(
        self, frame: np.ndarray, char_w: int, char_h: int, margin: str
    ) -> list[str]:
        """Renders 2x4 dot Unicode Braille matrix with TrueColor RGB."""
        lum = (frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114) > 120
        output: list[str] = []

        for cy in range(char_h):
            output.append(margin)
            last_fg = (-1, -1, -1)
            for cx in range(char_w):
                px = cx * 2
                py = cy * 4

                # Braille standard dot mapping:
                dot0 = int(lum[py, px])
                dot1 = int(lum[py + 1, px])
                dot2 = int(lum[py + 2, px])
                dot3 = int(lum[py, px + 1])
                dot4 = int(lum[py + 1, px + 1])
                dot5 = int(lum[py + 2, px + 1])
                dot6 = int(lum[py + 3, px])
                dot7 = int(lum[py + 3, px + 1])

                code = (
                    (dot0 << 0)
                    | (dot1 << 1)
                    | (dot2 << 2)
                    | (dot3 << 3)
                    | (dot4 << 4)
                    | (dot5 << 5)
                    | (dot6 << 6)
                    | (dot7 << 7)
                )

                ch = chr(BRAILLE_BASE + code)

                cell_rgb = frame[py : py + 4, px : px + 2].mean(axis=(0, 1)).astype(np.int32)
                r, g, b = int(cell_rgb[0]), int(cell_rgb[1]), int(cell_rgb[2])
                if (r, g, b) != last_fg:
                    output.append(f"\033[38;2;{r};{g};{b}m")
                    last_fg = (r, g, b)

                output.append(ch)

            output.append("\033[0m\033[K\n")

        return output
