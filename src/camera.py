"""OpenCV camera lifecycle helpers."""

from __future__ import annotations

import cv2
import os

from .config import CameraConfig


class Camera:
    """Thin wrapper around cv2.VideoCapture with clear errors."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self.capture = self._open_capture(config)
        if not self.capture.isOpened():
            raise RuntimeError(
                f"Could not open camera index {config.index}. "
                "Try changing camera.index in config.json."
            )
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
        self.capture.set(cv2.CAP_PROP_FPS, config.fps)

    def read(self):
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError("Camera frame read failed.")
        return frame

    def close(self) -> None:
        self.capture.release()

    @classmethod
    def _open_capture(cls, config: CameraConfig):
        for backend_id in cls._backend_ids(config.backend):
            capture = cv2.VideoCapture(config.index, backend_id)
            if capture.isOpened():
                return capture
            capture.release()
        return cv2.VideoCapture(config.index)

    @staticmethod
    def _backend_ids(name: str) -> list[int]:
        normalized = name.lower()
        if normalized == "auto":
            if os.name == "nt":
                return [cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY]
            return [cv2.CAP_ANY]
        if normalized == "dshow":
            return [cv2.CAP_DSHOW]
        if normalized == "msmf":
            return [cv2.CAP_MSMF]
        if normalized == "any":
            return [cv2.CAP_ANY]
        raise ValueError("camera.backend must be one of auto, dshow, msmf, or any")
