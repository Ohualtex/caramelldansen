#!/usr/bin/env python3
"""
Caramell Dansen Terminal Player
High-performance, TrueColor and Unicode terminal player with Dansen Loop mode.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
import shutil

from audio import get_audio_player, DummyAudioPlayer
from cache import BinaryCacheReader, BinaryCacheBuilder, BinaryCacheError
from input import get_input_handler
from renderer import TerminalRenderer
from ui import render_status_bar

DEFAULT_VIDEO_NAME = "caramell_dansen.mp4"
DEFAULT_AUDIO_NAME = "caramell_dansen.mp3"
DEFAULT_CACHE_NAME = "caramell_dansen.bin"
DEFAULT_VIDEO_PATH = "assets/caramell_dansen.mp4"
DEFAULT_AUDIO_PATH = "assets/caramell_dansen.mp3"
DEFAULT_CACHE_PATH = "assets/caramell_dansen.bin"


class CaramellPlayer:
    """Main player controller managing video, audio, rendering and input event loop."""

    def __init__(
        self,
        mode: str = "halfblock",
        color: bool = True,
        loop: bool = True,
        no_audio: bool = False,
        cache_path: str = DEFAULT_CACHE_PATH,
        audio_path: str = DEFAULT_AUDIO_PATH,
    ):
        self.mode = mode
        self.color = color
        self.loop = loop
        self.no_audio = no_audio
        self.cache_path = cache_path
        self.audio_path = audio_path

        self.running = False
        self.is_paused = False
        self._terminal_resized = False

        # Components
        self.cache: BinaryCacheReader | None = None
        self.audio = None
        self.renderer: TerminalRenderer | None = None
        self.input_handler = None

    def setup(self) -> None:
        """Initializes cache, audio, renderer, and terminal buffers."""
        from download import ensure_playback_assets, get_asset_path

        # Resolve asset paths
        self.cache_path = get_asset_path(DEFAULT_CACHE_NAME)
        self.audio_path = get_asset_path(DEFAULT_AUDIO_NAME)
        video_path = get_asset_path(DEFAULT_VIDEO_NAME)

        # 1. Ensure binary cache or source video exists
        if not os.path.exists(self.cache_path):
            print("[*] Assets missing locally, checking provisioning...")
            ensure_playback_assets()

            if not os.path.exists(self.cache_path):
                if not os.path.exists(video_path):
                    raise RuntimeError(
                        f"Neither cache '{self.cache_path}' nor source video '{video_path}' was found."
                    )
                print(f"[*] Building CDBP binary cache from '{video_path}'...")
                BinaryCacheBuilder.build_cache(
                    video_path,
                    self.cache_path,
                    target_width=160,
                    target_height=90,
                    fps=25.0,
                )
                print("[+] Cache generation complete.")

        self.cache = BinaryCacheReader(self.cache_path)

        # 2. Setup Audio
        if self.no_audio or not os.path.exists(self.audio_path):
            self.audio = DummyAudioPlayer(self.audio_path)
        else:
            self.audio = get_audio_player(self.audio_path)

        # 3. Setup Renderer & Input
        self.renderer = TerminalRenderer(
            mode=self.mode,
            aspect_ratio=16.0 / 9.0,
            color=self.color,
        )
        self.input_handler = get_input_handler()

        # 4. Handle window resize signal
        def on_sigwinch(signum, frame):
            self._terminal_resized = True

        if hasattr(signal, "SIGWINCH"):
            signal.signal(signal.SIGWINCH, on_sigwinch)

    def _enter_fullscreen(self) -> None:
        """Enters alternate screen buffer and hides cursor."""
        sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
        sys.stdout.flush()

    def _exit_fullscreen(self) -> None:
        """Restores main screen buffer and unhides cursor."""
        sys.stdout.write("\033[0m\033[?25h\033[?1049l")
        sys.stdout.flush()

    def run(self) -> None:
        """Main player execution loop."""
        self.setup()
        self._enter_fullscreen()
        self.running = True

        # If starting directly in loop mode, seek to chorus start
        if self.loop and self.cache:
            self.audio.seek(self.cache.loop_start_sec)
        else:
            self.audio.start()

        fps_timer = time.perf_counter()
        frame_counter = 0
        measured_fps = self.cache.fps if self.cache else 25.0

        try:
            while self.running:
                loop_start_time = time.perf_counter()

                # 1. Process keyboard inputs
                key = self.input_handler.poll_key()
                if key:
                    self._handle_key(key)

                if not self.running:
                    break

                # 2. Timing and Loop boundary checks
                current_time = self.audio.get_pos()

                if self.loop and self.cache:
                    if current_time >= self.cache.loop_end_sec:
                        self.audio.seek(self.cache.loop_start_sec)
                        current_time = self.cache.loop_start_sec
                elif current_time >= self.cache.duration:
                    # Video completed in normal mode
                    self.running = False
                    break

                # 3. Retrieve frame
                frame_rgb, frame_idx = self.cache.get_frame_for_time(current_time)

                # 4. Render video frame
                rendered_frame = self.renderer.render(frame_rgb)

                # 5. Render HUD status bar
                cols, _ = shutil.get_terminal_size(fallback=(80, 24))
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

                # 6. Flush output to terminal using home cursor
                buffer = "\033[H" + rendered_frame + "\n" + hud_line
                sys.stdout.write(buffer)
                sys.stdout.flush()

                # FPS calculation
                frame_counter += 1
                now = time.perf_counter()
                if now - fps_timer >= 1.0:
                    measured_fps = frame_counter / (now - fps_timer)
                    frame_counter = 0
                    fps_timer = now

                # Pace loop to target FPS (approx 25-30 FPS)
                target_frame_time = 1.0 / self.cache.fps
                elapsed = time.perf_counter() - loop_start_time
                sleep_dur = target_frame_time - elapsed
                if sleep_dur > 0.002:
                    time.sleep(sleep_dur)

        finally:
            self.cleanup()

    def _handle_key(self, key: str) -> None:
        """Processes interactive user keypress."""
        if key in ("Q", "ESC"):
            self.running = False

        elif key == "SPACE":
            if self.is_paused:
                self.audio.resume()
                self.is_paused = False
            else:
                self.audio.pause()
                self.is_paused = True

        elif key == "M":
            new_mode = self.renderer.cycle_mode()
            self.mode = new_mode

        elif key == "C":
            self.color = not self.color
            self.renderer.color = self.color

        elif key == "L":
            self.loop = not self.loop
            if self.loop and self.cache:
                curr = self.audio.get_pos()
                if curr < self.cache.loop_start_sec or curr >= self.cache.loop_end_sec:
                    self.audio.seek(self.cache.loop_start_sec)

        elif key == "RIGHT":
            new_pos = min(self.cache.duration, self.audio.get_pos() + 5.0)
            self.audio.seek(new_pos)

        elif key == "LEFT":
            new_pos = max(0.0, self.audio.get_pos() - 5.0)
            self.audio.seek(new_pos)

        elif key == "R":
            target = self.cache.loop_start_sec if self.loop else 0.0
            self.audio.seek(target)

    def cleanup(self) -> None:
        """Restores all system and terminal state."""
        if self.audio:
            try:
                self.audio.stop()
            except Exception:
                pass

        if self.input_handler:
            try:
                self.input_handler.cleanup()
            except Exception:
                pass

        if self.cache:
            try:
                self.cache.close()
            except Exception:
                pass

        self._exit_fullscreen()


def main() -> None:
    parser = argparse.ArgumentParser(
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
        BinaryCacheBuilder.build_cache(
            DEFAULT_VIDEO_PATH,
            DEFAULT_CACHE_PATH,
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
