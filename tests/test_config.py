from src.config import AppConfig


def test_default_gesture_map_contains_five_notes():
    config = AppConfig()

    assert list(config.gesture_notes) == [1, 2, 3, 4, 5]
    assert config.gesture_notes[3].name == "F4"
    assert config.gesture_notes[4].name == "G4"
    assert config.gesture_notes[5].name == "C5"
    assert config.gesture.max_num_hands == 2
