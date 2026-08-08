"""MediaPipe hand tracking wrapper."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Optional

import cv2

from .config import GestureConfig

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[1] / ".cache" / "matplotlib"),
)

try:
    import mediapipe as mp
except Exception:  # pragma: no cover - depends on local installation
    mp = None


LOGGER = logging.getLogger(__name__)


@dataclass
class HandDetection:
    """Single-hand detection data returned by MediaPipe."""

    landmarks: object
    handedness: str
    score: float


class HandTracker:
    """Track hands and draw landmarks for an OpenCV frame."""

    def __init__(self, config: GestureConfig) -> None:
        if mp is None:
            raise RuntimeError("mediapipe is not installed. Run pip install -r requirements.txt")
        self.config = config
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=config.max_num_hands,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        self._draw = mp.solutions.drawing_utils
        self._styles = mp.solutions.drawing_styles
        self._mp_hands = mp.solutions.hands

    def process(self, frame_bgr) -> tuple[Optional[HandDetection], object]:
        """Process a BGR frame and return the first detected hand."""

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._hands.process(rgb)
        rgb.flags.writeable = True

        if not results.multi_hand_landmarks:
            return None, results

        landmarks = results.multi_hand_landmarks[0]
        handedness = "Right"
        score = 0.0
        if results.multi_handedness:
            classification = results.multi_handedness[0].classification[0]
            handedness = classification.label
            score = classification.score
        return HandDetection(landmarks=landmarks, handedness=handedness, score=score), results

    def draw(self, frame_bgr, results) -> None:
        """Draw all tracked hand landmarks on a frame."""

        if not getattr(results, "multi_hand_landmarks", None):
            return
        for hand_landmarks in results.multi_hand_landmarks:
            self._draw.draw_landmarks(
                frame_bgr,
                hand_landmarks,
                self._mp_hands.HAND_CONNECTIONS,
                self._styles.get_default_hand_landmarks_style(),
                self._styles.get_default_hand_connections_style(),
            )

    def close(self) -> None:
        self._hands.close()
