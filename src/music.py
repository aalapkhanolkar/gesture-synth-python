"""Musical scale layouts used by the gesture performance layer."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
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
CHORD_INTERVALS = {
    "major": (0, 4, 7),
    "minor": (0, 3, 7),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "major7": (0, 4, 7, 11),
    "minor7": (0, 3, 7, 10),
    "dominant7": (0, 4, 7, 10),
}
CHORD_QUALITY_LABELS = {
    "major": "Major",
    "minor": "Minor",
    "sus2": "Sus2",
    "sus4": "Sus4",
    "major7": "Major 7",
    "minor7": "Minor 7",
    "dominant7": "Dominant 7",
}


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


@dataclass(frozen=True)
class Chord:
    """A chord root and quality rendered as realtime synth voices."""

    root: str
    quality: str
    octave: int = 4

    def __post_init__(self) -> None:
        if self.root not in ROOT_SEMITONES:
            raise ValueError(f"Unsupported chord root: {self.root}")
        if self.quality not in CHORD_INTERVALS:
            raise ValueError(f"Unsupported chord quality: {self.quality}")

    @property
    def display_name(self) -> str:
        return f"{self.root} {CHORD_QUALITY_LABELS[self.quality]}"

    def notes(self) -> tuple[NoteConfig, ...]:
        """Return the chord's root-position notes."""

        root_midi = 12 * (self.octave + 1) + ROOT_SEMITONES[self.root]
        return tuple(
            NoteConfig(
                name=ScaleLayout._midi_name(root_midi + interval),
                frequency=ScaleLayout._midi_frequency(root_midi + interval),
            )
            for interval in CHORD_INTERVALS[self.quality]
        )


def chord_from_label(label: str) -> Chord:
    """Parse a combobox label such as ``C Major 7`` into a chord."""

    root, quality_label = label.split(" ", maxsplit=1)
    quality = next(
        (key for key, display in CHORD_QUALITY_LABELS.items() if display == quality_label),
        None,
    )
    if quality is None:
        raise ValueError(f"Unsupported chord label: {label}")
    return Chord(root, quality)


def available_chord_labels() -> tuple[str, ...]:
    """Return every root/quality combination offered by the chord slot controls."""

    return tuple(
        Chord(root, quality).display_name
        for root in ROOT_SEMITONES
        for quality in CHORD_QUALITY_LABELS
    )


def note_from_name(name: str) -> NoteConfig:
    """Return frequency metadata for a selectable note name such as ``F#4``."""

    match = re.fullmatch(r"([A-G]#?)(-?\d+)", name)
    if match is None or match.group(1) not in ROOT_SEMITONES:
        raise ValueError(f"Unsupported note name: {name}")
    root, octave_text = match.groups()
    midi_note = 12 * (int(octave_text) + 1) + ROOT_SEMITONES[root]
    return NoteConfig(name=name, frequency=ScaleLayout._midi_frequency(midi_note))


def available_note_names(start_octave: int = 3, end_octave: int = 5) -> tuple[str, ...]:
    """Return the chromatic note choices offered by the editable note slots."""

    return tuple(f"{root}{octave}" for octave in range(start_octave, end_octave + 1) for root in SHARP_NAMES)
