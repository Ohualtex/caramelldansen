"""
HUD Status Bar and Scrubber UI for Caramell Dansen Terminal Player.
"""

from __future__ import annotations

import re


def strip_ansi(text: str) -> str:
    """Removes ANSI escape codes to compute visible printable width."""
    return re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", text)


def format_time(seconds: float) -> str:
    """Formats seconds into MM:SS format."""
    seconds = max(0.0, seconds)
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins:02d}:{secs:02d}"


def create_progress_bar(current_sec: float, total_sec: float, bar_length: int = 16) -> str:
    """Creates a visual progress bar with smooth box-drawing characters."""
    if bar_length <= 0:
        return ""
    if total_sec <= 0:
        return f"\033[90m{'─' * bar_length}\033[0m"

    ratio = min(1.0, max(0.0, current_sec / total_sec))
    filled_len = int(round(ratio * bar_length))
    filled_len = min(bar_length, max(0, filled_len))
    unfilled_len = bar_length - filled_len

    left = "━" * filled_len
    right = "─" * unfilled_len
    return f"\033[95m{left}\033[90m{right}\033[0m"


def render_status_bar(
    current_time: float,
    duration: float,
    fps: float,
    mode: str,
    is_paused: bool,
    terminal_columns: int,
) -> str:
    """
    Renders an adaptive, centered status HUD bar.
    Displays playback state, scrubber, render mode, and FPS.
    Gracefully condenses layout on narrow terminals to prevent line wrapping.
    """
    time_str = f"{format_time(current_time)} / {format_time(duration)}"
    status_badge = "\033[93m⏸ PAUSED\033[0m" if is_paused else "\033[92m▶ PLAY\033[0m"
    fps_badge = f"\033[90m{fps:.1f} fps\033[0m"
    mode_badge = f"\033[97m{mode}\033[0m"

    if terminal_columns < 45:
        # Ultra-compact HUD for very small windows
        hud = f" {status_badge}  \033[97m{time_str}\033[0m "
    elif terminal_columns < 70:
        # Compact HUD with small scrubber and mode
        bar_len = max(6, min(12, terminal_columns - 42))
        progress_bar = create_progress_bar(current_time, duration, bar_length=bar_len)
        hud = f" {status_badge}  {progress_bar}  \033[97m{time_str}\033[0m  │  {mode_badge} "
    else:
        # Full rich HUD
        progress_bar = create_progress_bar(current_time, duration, bar_length=16)
        hud = (
            f" {status_badge}  {progress_bar}  \033[97m{time_str}\033[0m  "
            f"│  {mode_badge}  │  {fps_badge} "
        )

    vis_len = len(strip_ansi(hud))
    pad = max(0, (terminal_columns - vis_len) // 2)
    return " " * pad + hud + "\033[K"
