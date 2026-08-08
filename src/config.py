"""Application configuration for the gesture synth."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Dict, Mapping, Optional


LOGGER = logging.getLogger(__name__)


NOTE_FREQUENCIES = {
    "C4": 261.63,
    "E4": 329.63,
    "G4": 392.00,
    "C5": 523.25,
    "E5": 659.25,
}


@dataclass(frozen=True)
class NoteConfig:
    """Musical note metadata used by gesture mappings."""

    name: str
    frequency: float


@dataclass(frozen=True)
class SynthConfig:
    """Realtime synthesizer settings."""

    sample_rate: int = 44100
    block_size: int = 512
    waveform: str = "sine"
    amplitude: float = 0.25
    attack: float = 0.015
    decay: float = 0.08
    sustain: float = 0.75
    release: float = 0.16
    portamento: float = 0.025


@dataclass(frozen=True)
class GestureConfig:
    """Gesture detection and stabilization settings."""

    stable_frames: int = 6
    min_detection_confidence: float = 0.65
    min_tracking_confidence: float = 0.55
    max_num_hands: int = 1
    mirror_camera: bool = True


@dataclass(frozen=True)
class CameraConfig:
    """Camera capture settings."""

    index: int = 0
    backend: str = "auto"
    width: int = 1280
    height: int = 720
    fps: int = 30


@dataclass(frozen=True)
class AppConfig:
    """Top-level application settings."""

    camera: CameraConfig = field(default_factory=CameraConfig)
    gesture: GestureConfig = field(default_factory=GestureConfig)
    synth: SynthConfig = field(default_factory=SynthConfig)
    gesture_notes: Mapping[int, NoteConfig] = field(
        default_factory=lambda: {
            1: NoteConfig("C4", NOTE_FREQUENCIES["C4"]),
            2: NoteConfig("E4", NOTE_FREQUENCIES["E4"]),
            3: NoteConfig("G4", NOTE_FREQUENCIES["G4"]),
        }
    )

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> "AppConfig":
        """Load config from JSON, falling back to defaults when omitted."""

        if path is None:
            return cls()

        config_path = Path(path)
        if not config_path.exists():
            LOGGER.warning("Config file %s not found; using defaults.", config_path)
            return cls()

        with config_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Dict) -> "AppConfig":
        """Create config from a dictionary, keeping unspecified defaults."""

        defaults = cls()
        camera = CameraConfig(**{**defaults.camera.__dict__, **raw.get("camera", {})})
        gesture = GestureConfig(**{**defaults.gesture.__dict__, **raw.get("gesture", {})})
        synth = SynthConfig(**{**defaults.synth.__dict__, **raw.get("synth", {})})

        note_map = dict(defaults.gesture_notes)
        for key, value in raw.get("gesture_notes", {}).items():
            fingers = int(key)
            note_name = value.get("name", f"Gesture {fingers}")
            frequency = float(value.get("frequency", NOTE_FREQUENCIES.get(note_name, 440.0)))
            note_map[fingers] = NoteConfig(note_name, frequency)

        return cls(camera=camera, gesture=gesture, synth=synth, gesture_notes=note_map)


def default_config_path() -> Path:
    """Return the conventional config path for the repository."""

    return Path(__file__).resolve().parents[1] / "config.json"
