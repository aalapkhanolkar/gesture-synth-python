import pytest

from src.music import Chord, ScaleLayout, available_note_names, chord_from_label, note_from_name


def test_major_scale_layout_is_root_third_fourth_fifth_octave():
    layout = ScaleLayout("C", "major")

    assert [layout.note_for_fingers(fingers).name for fingers in range(1, 6)] == ["C4", "E4", "F4", "G4", "C5"]


def test_minor_scale_layout_changes_the_third():
    layout = ScaleLayout("C", "minor")

    assert layout.note_for_fingers(2).name == "D#4"
    assert layout.note_for_fingers(4).name == "G4"


def test_scale_layout_rejects_unknown_root_or_mode():
    with pytest.raises(ValueError):
        ScaleLayout("H", "major")
    with pytest.raises(ValueError):
        ScaleLayout("C", "dorian")


def test_major_seventh_chord_contains_four_synth_notes():
    chord = Chord("C", "major7")

    assert chord.display_name == "C Major 7"
    assert [note.name for note in chord.notes()] == ["C4", "E4", "G4", "B4"]


def test_chord_label_round_trip():
    chord = chord_from_label("D Minor 7")

    assert chord.root == "D"
    assert chord.quality == "minor7"


def test_note_slot_options_resolve_chromatic_frequencies():
    assert note_from_name("A4").frequency == pytest.approx(440.0)
    assert "C3" in available_note_names()
    assert "B5" in available_note_names()
