"""Resilient OpenCV webcam capture for the gesture synth."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import cv2

from .config import CameraConfig


LOGGER = logging.getLogger(__name__)


class Camera:
    """Keep a webcam stream alive and recover when a backend stops delivering frames."""

    _MAX_CONSECUTIVE_FAILURES = 12
    _RECONNECT_INTERVAL_SECONDS = 1.0
    _WARMUP_FRAMES = 8

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self.capture: Optional[cv2.VideoCapture] = None
        self.index: Optional[int] = None
        self.backend_name = "not connected"
        self.status = "Starting camera..."
        self._consecutive_failures = 0
        self._last_connect_attempt = 0.0
        self._connect()

    @property
    def connected(self) -> bool:
        """Whether an OpenCV camera backend is currently open."""

        return self.capture is not None and self.capture.isOpened()

    def read(self) -> Optional[object]:
        """Return the newest frame, reconnecting after a short run of failures."""

        if not self.connected:
            self._connect_if_due()
            return None

        try:
            ok, frame = self.capture.read()  # type: ignore[union-attr]
        except cv2.error as exc:
            LOGGER.debug("OpenCV camera read error: %s", exc)
            ok, frame = False, None

        if ok and frame is not None:
            self._consecutive_failures = 0
            self.status = f"Camera {self.index} | {self.backend_name}"
            return frame

        self._consecutive_failures += 1
        self.status = f"Camera frame unavailable ({self._consecutive_failures}/{self._MAX_CONSECUTIVE_FAILURES})"
        if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
            LOGGER.warning("Camera stream stopped; reconnecting.")
            self._release_capture()
            self._connect_if_due(force=True)
        return None

    def close(self) -> None:
        """Release the camera device."""

        self._release_capture()

    def _connect_if_due(self, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - self._last_connect_attempt >= self._RECONNECT_INTERVAL_SECONDS:
            self._connect()

    def _connect(self) -> None:
        self._last_connect_attempt = time.monotonic()
        self._release_capture()
        self.status = "Looking for webcam..."

        for index in self._candidate_indices():
            for backend_name, backend_id in self._backend_options():
                capture = cv2.VideoCapture(index, backend_id)
                if not capture.isOpened():
                    capture.release()
                    continue

                self._apply_settings(capture)
                if self._warm_up(capture):
                    self.capture = capture
                    self.index = index
                    self.backend_name = backend_name
                    self._consecutive_failures = 0
                    self.status = f"Camera {index} | {backend_name}"
                    LOGGER.info("Using camera index %d with %s backend.", index, backend_name)
                    return
                capture.release()

        self.index = None
        self.backend_name = "not connected"
        self.status = "No webcam frame available - retrying..."
        LOGGER.warning(
            "No usable webcam frame. Check Windows camera permissions or set camera.index/backend in config.json."
        )

    def _release_capture(self) -> None:
        if self.capture is not None:
            self.capture.release()
        self.capture = None

    def _candidate_indices(self) -> list[int]:
        """Try the configured camera first, then common local camera indices in auto mode."""

        if self.config.backend.lower() != "auto":
            return [self.config.index]
        return list(dict.fromkeys([self.config.index, 0, 1, 2]))

    def _backend_options(self) -> list[tuple[str, int]]:
        normalized = self.config.backend.lower()
        if normalized == "auto":
            # DirectShow is normally the most reliable OpenCV webcam backend on Windows.
            if os.name == "nt":
                return [("DirectShow", cv2.CAP_DSHOW), ("Media Foundation", cv2.CAP_MSMF), ("Auto", cv2.CAP_ANY)]
            return [("Auto", cv2.CAP_ANY)]
        if normalized == "dshow":
            return [("DirectShow", cv2.CAP_DSHOW)]
        if normalized == "msmf":
            return [("Media Foundation", cv2.CAP_MSMF)]
        if normalized == "any":
            return [("Auto", cv2.CAP_ANY)]
        raise ValueError("camera.backend must be one of auto, dshow, msmf, or any")

    def _apply_settings(self, capture: cv2.VideoCapture) -> None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _warm_up(self, capture: cv2.VideoCapture) -> bool:
        """Discard initial frames while a physical camera auto-exposes and starts streaming."""

        valid_frames = 0
        for _ in range(self._WARMUP_FRAMES):
            try:
                ok, frame = capture.read()
            except cv2.error:
                return False
            if ok and frame is not None and frame.size:
                valid_frames += 1
                if valid_frames >= 2:
                    return True
            time.sleep(0.02)
        return False
