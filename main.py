"""Run the webcam gesture-controlled synthesizer."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from src.camera import Camera
from src.config import AppConfig, NoteConfig, default_config_path
from src.gesture_detector import GestureStabilizer, count_extended_fingers, supported_gesture
from src.hand_tracker import HandTracker
from src.synth import Synthesizer
from src.ui import FPSCounter, draw_overlay


LOGGER = logging.getLogger("gesture_synth")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gesture-controlled Python synthesizer")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to JSON config file")
    parser.add_argument("--no-audio", action="store_true", help="Run camera and gesture UI without starting audio")
    return parser.parse_args()


def note_for_gesture(config: AppConfig, fingers: Optional[int]) -> Optional[NoteConfig]:
    if fingers is None:
        return None
    return config.gesture_notes.get(fingers)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    config = AppConfig.load(args.config)
    if args.no_audio:
        LOGGER.info("Audio disabled. Running camera and gesture detection only.")

    camera = tracker = synth = None
    last_note_name: Optional[str] = None

    try:
        camera = Camera(config.camera)
        tracker = HandTracker(config.gesture)
        synth = Synthesizer(config.synth)
        if not args.no_audio:
            synth.start()

        stabilizer = GestureStabilizer(config.gesture.stable_frames)
        fps_counter = FPSCounter()
        LOGGER.info("Gesture Synth running. Press Q or Esc in the camera window to quit.")

        while True:
            frame = camera.read()
            if frame is None:
                frame = np.zeros((config.camera.height, config.camera.width, 3), dtype=np.uint8)
                cv2.putText(
                    frame,
                    "GESTURE SYNTH",
                    (40, config.camera.height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (80, 220, 180),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    frame,
                    camera.status,
                    (40, config.camera.height // 2 + 44),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (235, 235, 235),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    frame,
                    "Allow camera access in Windows Settings > Privacy & security > Camera",
                    (40, config.camera.height // 2 + 82),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (190, 190, 190),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    frame,
                    "Press Q or Esc to quit",
                    (40, config.camera.height // 2 + 116),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (190, 190, 190),
                    1,
                    cv2.LINE_AA,
                )
                cv2.imshow("Gesture Synth", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
                continue

            if config.gesture.mirror_camera:
                frame = cv2.flip(frame, 1)

            detection, results = tracker.process(frame)
            raw_count = None
            if detection is not None:
                raw_count = count_extended_fingers(
                    detection.landmarks.landmark,
                    detection.handedness,
                    mirrored=config.gesture.mirror_camera,
                )
            mapped_count = supported_gesture(raw_count, config.gesture_notes.keys())
            gesture_state = stabilizer.update(mapped_count)
            note = note_for_gesture(config, gesture_state.stable_fingers)

            if note is None:
                if last_note_name is not None:
                    synth.note_off()
                    last_note_name = None
            elif note.name != last_note_name:
                synth.note_on(note.name, note.frequency)
                last_note_name = note.name

            tracker.draw(frame, results)
            draw_overlay(frame, gesture_state, note, config.synth.waveform, fps_counter.update())
            cv2.imshow("Gesture Synth", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break

    except Exception as exc:
        LOGGER.error("%s", exc)
        return 1
    finally:
        if synth is not None:
            synth.note_off()
            synth.close()
        if tracker is not None:
            tracker.close()
        if camera is not None:
            camera.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
