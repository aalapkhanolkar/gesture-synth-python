"""OpenCV drawing helpers for the camera interface."""

from __future__ import annotations

import time
from typing import Optional

import cv2

from .config import NoteConfig
from .gesture_detector import GestureState


class FPSCounter:
    """Smoothed frames-per-second counter."""

    def __init__(self, smoothing: float = 0.9) -> None:
        self.smoothing = smoothing
        self._last = time.perf_counter()
        self._fps = 0.0

    def update(self) -> float:
        now = time.perf_counter()
        instant = 1.0 / max(1e-6, now - self._last)
        self._last = now
        self._fps = instant if self._fps == 0.0 else self.smoothing * self._fps + (1 - self.smoothing) * instant
        return self._fps


def draw_overlay(
    frame,
    gesture_state: GestureState,
    note: Optional[NoteConfig],
    waveform: str,
    fps: float,
) -> None:
    """Render a compact status panel over the webcam frame."""

    panel_x, panel_y = 20, 20
    panel_w, panel_h = 430, 205
    cv2.rectangle(frame, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (18, 18, 18), -1)
    cv2.rectangle(frame, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (80, 220, 180), 2)

    note_name = note.name if note else "None"
    frequency = f"{note.frequency:.2f} Hz" if note else "0.00 Hz"
    lines = [
        "GESTURE SYNTH",
        f"GESTURE: {gesture_state.label}",
        f"NOTE: {note_name}",
        f"FREQUENCY: {frequency}",
        f"WAVEFORM: {waveform}",
        f"STABILITY: {gesture_state.confidence:.0%} ({gesture_state.stable_frames} frames)",
        f"FPS: {fps:.1f}",
    ]

    y = panel_y + 32
    for index, line in enumerate(lines):
        scale = 0.82 if index == 0 else 0.65
        color = (80, 220, 180) if index == 0 else (238, 238, 238)
        cv2.putText(frame, line, (panel_x + 18, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)
        y += 28

    hint = "Press Q or Esc to quit"
    cv2.putText(frame, hint, (20, frame.shape[0] - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (235, 235, 235), 2, cv2.LINE_AA)

