import pytest

from src.music import ScaleLayout


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
