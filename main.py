#!/usr/bin/env python3
"""
Caramell Dansen Terminal Player
High-performance, TrueColor and Unicode terminal player with Dansen Loop mode.
Built with Platform Abstraction Layer (PAL) and Audio Master Clock architecture.
"""

from __future__ import annotations

import argparse
import sys
import time

from cache import BinaryCacheReader, BinaryCacheBuilder
from download import ensure_assets, DEFAULT_CACHE_NAME, DEFAULT_AUDIO_NAME, DEFAULT_VIDEO_NAME, get_asset_path
from platforms import get_platform, BasePlatform
from renderer import TerminalRenderer
from ui import render_status_bar


class CaramellPlayer:
    """Main player controller managing video, audio, rendering and input event loop."""

    def __init__(
        self,
        mode: str = "halfblock",
        color: bool = True,
        loop: bool = True,
        no_audio: bool = False,
        cache_path: str | None = None,
        audio_path: str | None = None,
    ):
        self.mode = mode
        self.color = color
        self.loop = loop
        self.no_audio = no_audio
        self.cache_path = cache_path
        self.audio_path = audio_path

        self.running: bool = False
        self.is_paused: bool = False

        # Components
        self.cache: BinaryCacheReader | None = None
        self.platform: BasePlatform | None = None
        self.renderer: TerminalRenderer | None = None

    def setup(self) -> None:
        """Initializes assets, cache reader, audio, renderer, and terminal buffers."""
        # 1. Resolve and ensure assets (automatically downloads on first run if missing)
        cache_file, audio_file = ensure_assets(self.cache_path, self.audio_path)
        self.cache_path = cache_file
        self.audio_path = audio_file

        self.cache = BinaryCacheReader(self.cache_path)

        # 2. Instantiate isolated OS platform subsystem (Audio, Input, Terminal)
        self.platform = get_platform(audio_path=self.audio_path, no_audio=self.no_audio)

        # 3. Setup Video Renderer
        self.renderer = TerminalRenderer(
            mode=self.mode,
            aspect_ratio=16.0 / 9.0,
            color=self.color,
        )

    def run(self) -> None:
        """Main player execution loop driven by Audio Master Clock."""
        self.setup()
        if not self.platform or not self.cache or not self.renderer:
            return

        self.platform.terminal.enter_fullscreen()
        self.running = True

        # If starting directly in Dansen Loop mode, seek audio to chorus start
        if self.loop:
            self.platform.audio.start()
            self.platform.audio.seek(self.cache.loop_start_sec)
        else:
            self.platform.audio.start()

        fps_timer = time.perf_counter()
        frame_counter = 0
        measured_fps = self.cache.fps

        try:
            while self.running:
                loop_start_time = time.perf_counter()

                # 1. Process non-blocking keyboard inputs
                key = self.platform.input.poll_key()
                if key:
                    self._handle_key(key)

                if not self.running:
                    break

                # 2. Check responsive window resizing
                if self.platform.terminal.check_resized():
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.flush()

                # 3. Audio Master Clock: Timing and Dansen Loop boundary checks
                current_time = self.platform.audio.get_pos()

                if self.loop:
                    if current_time >= self.cache.loop_end_sec:
                        self.platform.audio.seek(self.cache.loop_start_sec)
                        current_time = self.cache.loop_start_sec
                    elif current_time < self.cache.loop_start_sec:
                        self.platform.audio.seek(self.cache.loop_start_sec)
                        current_time = self.cache.loop_start_sec
                elif current_time >= self.cache.duration:
                    # Video playback finished in full video mode
                    self.running = False
                    break

                # 4. Fetch synchronized video frame
                frame_rgb, frame_idx = self.cache.get_frame_for_time(current_time)

                # 5. Get terminal dimensions and render video frame
                cols, lines = self.platform.terminal.get_size()
                rendered_frame = self.renderer.render(
                    frame_rgb,
                    terminal_cols=cols,
                    terminal_lines=lines,
                )

                # 6. Render adaptive HUD status bar
                hud_line = render_status_bar(
                    current_time=current_time,
                    duration=self.cache.duration,
                    fps=measured_fps,
                    mode=self.renderer.mode,
                    color=self.renderer.color,
                    loop_active=self.loop,
                    is_paused=self.is_paused,
                    terminal_columns=cols,
                )

                # 7. Atomic frame flush using home cursor, line clear, and bottom clear
                buffer = "\033[H" + rendered_frame + "\n" + hud_line + "\033[K\033[J"
                sys.stdout.write(buffer)
                sys.stdout.flush()

                # Measure actual rendering FPS
                frame_counter += 1
                now = time.perf_counter()
                if now - fps_timer >= 1.0:
                    measured_fps = frame_counter / (now - fps_timer)
                    frame_counter = 0
                    fps_timer = now

                # Pace loop to target frame rate (~25 FPS)
                target_frame_time = 1.0 / self.cache.fps
                elapsed = time.perf_counter() - loop_start_time
                sleep_dur = target_frame_time - elapsed
                if sleep_dur > 0.002:
                    time.sleep(sleep_dur)

        finally:
            self.cleanup()

    def _handle_key(self, key: str) -> None:
        """Processes interactive user keypress."""
        if not self.platform or not self.cache or not self.renderer:
            return

        if key in ("QUIT", "Q", "ESC"):
            self.running = False

        elif key == "SPACE":
            if self.is_paused:
                self.platform.audio.resume()
                self.is_paused = False
            else:
                self.platform.audio.pause()
                self.is_paused = True

        elif key == "MODE":
            new_mode = self.renderer.cycle_mode()
            self.mode = new_mode

        elif key == "COLOR":
            self.color = not self.color
            self.renderer.color = self.color

        elif key == "LOOP":
            self.loop = not self.loop
            if self.loop:
                curr = self.platform.audio.get_pos()
                if curr < self.cache.loop_start_sec or curr >= self.cache.loop_end_sec:
                    self.platform.audio.seek(self.cache.loop_start_sec)

        elif key == "RIGHT":
            new_pos = min(self.cache.duration, self.platform.audio.get_pos() + 5.0)
            self.platform.audio.seek(new_pos)

        elif key == "LEFT":
            new_pos = max(0.0, self.platform.audio.get_pos() - 5.0)
            self.platform.audio.seek(new_pos)

        elif key == "RESTART":
            target = self.cache.loop_start_sec if self.loop else 0.0
            self.platform.audio.seek(target)

    def cleanup(self) -> None:
        """Restores all system and terminal state."""
        if self.cache:
            try:
                self.cache.close()
            except Exception:
                pass

        if self.platform:
            try:
                self.platform.cleanup()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="caramelldansen",
        description="Caramell Dansen Terminal Player — High Performance TrueColor & Unicode",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["halfblock", "color-ascii", "braille", "ascii"],
        default="halfblock",
        help="Rendering mode",
    )
    parser.add_argument(
        "--no-color",
        "--mono",
        dest="color",
        action="store_false",
        help="Disable TrueColor rendering and run in monochrome",
    )
    parser.add_argument(
        "--loop",
        dest="loop",
        action="store_true",
        default=True,
        help="Start in infinite Dansen Loop mode",
    )
    parser.add_argument(
        "--full",
        dest="loop",
        action="store_false",
        help="Play full music video from start to finish",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Mute audio and run on internal clock",
    )
    parser.add_argument(
        "--build-cache",
        action="store_true",
        help="Force rebuild CDBP binary cache",
    )

    args = parser.parse_args()

    if args.build_cache:
        print("[*] Rebuilding CDBP binary cache...")
        video_src = get_asset_path(DEFAULT_VIDEO_NAME)
        cache_dest = get_asset_path(DEFAULT_CACHE_NAME)
        BinaryCacheBuilder.build_cache(
            video_src,
            cache_dest,
            target_width=160,
            target_height=90,
            fps=25.0,
        )
        print("[+] Cache rebuilt successfully.")
        return

    player = CaramellPlayer(
        mode=args.mode,
        color=args.color,
        loop=args.loop,
        no_audio=args.no_audio,
    )

    try:
        player.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
