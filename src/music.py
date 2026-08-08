"""Musical scale layouts used by the gesture performance layer."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from .config import NoteConfig


ROOT_SEMITONES = {
    "C": 0,
    "C#": 1,
    "D": 2,
    "D#": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "G": 7,
    "G#": 8,
    "A": 9,
    "A#": 10,
    "B": 11,
}
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
SCALE_INTERVALS = {
    "major": (0, 4, 5, 7, 12),
    "minor": (0, 3, 5, 7, 12),
}
DEGREE_LABELS = ("Root", "3rd", "4th", "5th", "Octave")


@dataclass(frozen=True)
class ScaleLayout:
    """Five note positions: root, third, fourth, fifth, and octave."""

    root: str = "C"
    mode: str = "major"
    octave: int = 4

    def __post_init__(self) -> None:
        if self.root not in ROOT_SEMITONES:
            raise ValueError(f"Unsupported root note: {self.root}")
        if self.mode not in SCALE_INTERVALS:
            raise ValueError("scale mode must be 'major' or 'minor'")

    @property
    def display_name(self) -> str:
        return f"{self.root} {self.mode.title()}"

    def note_for_fingers(self, fingers: Optional[int]) -> Optional[NoteConfig]:
        """Return the scale note played by a stable one-to-five finger count."""

        if fingers is None or not 1 <= fingers <= len(DEGREE_LABELS):
            return None
        root_midi = 12 * (self.octave + 1) + ROOT_SEMITONES[self.root]
        midi_note = root_midi + SCALE_INTERVALS[self.mode][fingers - 1]
        return NoteConfig(name=self._midi_name(midi_note), frequency=self._midi_frequency(midi_note))

    def degree_label(self, fingers: Optional[int]) -> str:
        """Return a readable label for the current gesture position."""

        if fingers is None or not 1 <= fingers <= len(DEGREE_LABELS):
            return "-"
        return DEGREE_LABELS[fingers - 1]

    def mapping_label(self) -> str:
        """Describe the current gesture map for the desktop controls."""

        entries = []
        for fingers in range(1, 6):
            note = self.note_for_fingers(fingers)
            entries.append(f"{fingers}: {self.degree_label(fingers)} {note.name}")
        return "\n".join(entries)

    @staticmethod
    def _midi_frequency(midi_note: int) -> float:
        return 440.0 * math.pow(2.0, (midi_note - 69) / 12.0)

    @staticmethod
    def _midi_name(midi_note: int) -> str:
        return f"{SHARP_NAMES[midi_note % 12]}{midi_note // 12 - 1}"
