"""Finger-count gesture recognition and debouncing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


TIP_IDS = (4, 8, 12, 16, 20)
PIP_IDS = (3, 6, 10, 14, 18)


@dataclass(frozen=True)
class GestureState:
    """Stable gesture state exposed to the synth and UI."""

    stable_fingers: Optional[int]
    candidate_fingers: Optional[int]
    stable_frames: int
    confidence: float

    @property
    def label(self) -> str:
        return "None" if self.stable_fingers is None else str(self.stable_fingers)


class GestureStabilizer:
    """Debounce noisy frame-by-frame finger counts."""

    def __init__(self, required_stable_frames: int = 6) -> None:
        if required_stable_frames < 1:
            raise ValueError("required_stable_frames must be at least 1")
        self.required_stable_frames = required_stable_frames
        self._candidate: Optional[int] = None
        self._candidate_frames = 0
        self._stable: Optional[int] = None

    def update(self, detected_fingers: Optional[int]) -> GestureState:
        """Update with a raw detection and return the debounced state."""

        if detected_fingers == self._candidate:
            self._candidate_frames += 1
        else:
            self._candidate = detected_fingers
            self._candidate_frames = 1

        if self._candidate_frames >= self.required_stable_frames:
            self._stable = self._candidate

        confidence = min(1.0, self._candidate_frames / self.required_stable_frames)
        return GestureState(
            stable_fingers=self._stable,
            candidate_fingers=self._candidate,
            stable_frames=self._candidate_frames,
            confidence=confidence,
        )


def count_extended_fingers(
    landmarks: Sequence,
    handedness: str = "Right",
    *,
    mirrored: bool = True,
) -> int:
    """Count extended fingers from MediaPipe hand landmarks.

    The four non-thumb fingers are considered extended when the tip sits above
    the proximal interphalangeal joint. The thumb uses horizontal position and
    the detected hand label. The ``mirrored`` argument is kept so callers can
    preserve the same public API if they later process an unflipped camera feed.
    """

    if len(landmarks) < 21:
        raise ValueError("Expected 21 hand landmarks")

    fingers = 0
    for tip_id, pip_id in zip(TIP_IDS[1:], PIP_IDS[1:]):
        if landmarks[tip_id].y < landmarks[pip_id].y:
            fingers += 1

    thumb_tip_x = landmarks[4].x
    thumb_ip_x = landmarks[3].x
    is_right = handedness.lower() == "right"
    thumb_extended = thumb_tip_x > thumb_ip_x if is_right else thumb_tip_x < thumb_ip_x
    if thumb_extended:
        fingers += 1

    return fingers


def supported_gesture(raw_count: Optional[int], supported_counts: Iterable[int]) -> Optional[int]:
    """Return the count only when it maps to a configured musical gesture."""

    if raw_count in set(supported_counts):
        return raw_count
    return None
