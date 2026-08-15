from types import SimpleNamespace

import pytest

from src.gesture_detector import GestureStabilizer, count_extended_fingers, supported_gesture


def landmark(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


def base_landmarks():
    points = [landmark(0.5, 0.5) for _ in range(21)]
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        points[tip] = landmark(0.5, 0.7)
        points[pip] = landmark(0.5, 0.5)
    points[4] = landmark(0.45, 0.5)
    points[3] = landmark(0.5, 0.5)
    return points


def test_stabilizer_requires_repeated_frames():
    stabilizer = GestureStabilizer(required_stable_frames=3)

    assert stabilizer.update(1).stable_fingers is None
    assert stabilizer.update(1).stable_fingers is None
    state = stabilizer.update(1)

    assert state.stable_fingers == 1
    assert state.confidence == 1.0


def test_stabilizer_does_not_restart_on_same_state():
    stabilizer = GestureStabilizer(required_stable_frames=2)

    stabilizer.update(2)
    assert stabilizer.update(2).stable_fingers == 2
    state = stabilizer.update(2)

    assert state.stable_fingers == 2
    assert state.stable_frames == 3


def test_supported_gesture_filters_unmapped_counts():
    assert supported_gesture(2, [1, 2, 3]) == 2
    assert supported_gesture(5, [1, 2, 3]) is None
    assert supported_gesture(None, [1, 2, 3]) is None


def test_count_extended_index_middle_ring_only():
    points = base_landmarks()
    for tip, pip in [(8, 6), (12, 10), (16, 14)]:
        points[tip].y = 0.3
        points[pip].y = 0.5

    assert count_extended_fingers(points, "Right", mirrored=True) == 3


def test_index_only_is_not_confused_by_an_open_thumb():
    points = base_landmarks()
    points[8].y = 0.3
    points[8].x = 0.5
    points[6].y = 0.5
    points[4].x = 0.7

    assert count_extended_fingers(points, "Right", mirrored=True) == 1


def test_open_hand_counts_as_five_only_with_all_long_fingers_extended():
    points = base_landmarks()
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        points[tip].y = 0.3
        points[pip].y = 0.5
    points[4].x = 0.7

    assert count_extended_fingers(points, "Right", mirrored=True) == 5


def test_count_extended_rejects_short_landmark_list():
    with pytest.raises(ValueError):
        count_extended_fingers([], "Right")
