"""Launch the gesture-controlled synthesizer desktop application."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.config import AppConfig, default_config_path
from src.desktop_app import GestureSynthApp


def parse_args() -> argparse.Namespace:
    """Parse the small command-line surface for the desktop application."""

    parser = argparse.ArgumentParser(description="Gesture-controlled Python synthesizer")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to JSON config file")
    parser.add_argument("--no-audio", action="store_true", help="Open the camera UI without sound output")
    return parser.parse_args()


def main() -> int:
    """Create the persistent window and run until it is closed."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    config = AppConfig.load(args.config)
    app = GestureSynthApp(config, audio_enabled=not args.no_audio)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
