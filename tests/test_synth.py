import numpy as np

from src.config import SynthConfig
from src.synth import Synthesizer


def test_synth_renders_audio_after_note_on():
    synth = Synthesizer(SynthConfig(sample_rate=8000, waveform="sine", attack=0.001))
    synth.note_on("A4", 440.0)

    audio = synth.render(512)

    assert audio.shape == (512,)
    assert audio.dtype == np.float32
    assert np.max(np.abs(audio)) > 0.01


def test_synth_releases_after_note_off():
    synth = Synthesizer(SynthConfig(sample_rate=8000, release=0.01))
    synth.note_on("A4", 440.0)
    synth.render(256)
    synth.note_off()

    tail = synth.render(2000)

    assert abs(float(tail[-1])) < 1e-4


def test_all_supported_waveforms_render():
    for waveform in ["sine", "square", "sawtooth", "triangle"]:
        synth = Synthesizer(SynthConfig(sample_rate=8000, waveform=waveform))
        synth.note_on("C4", 261.63)
        audio = synth.render(128)

        assert np.isfinite(audio).all()


def test_frequency_changes_without_retriggering_note():
    synth = Synthesizer(SynthConfig(sample_rate=8000, portamento=0.001))
    synth.note_on("C4", 261.63)
    synth.render(100)
    synth.set_frequency(293.66)
    synth.render(100)

    assert synth.active_note is not None
    assert synth.active_note.name == "C4"
    assert synth.target_frequency == 293.66


def test_chord_renders_multiple_active_voices():
    synth = Synthesizer(SynthConfig(sample_rate=8000, attack=0.001))
    synth.chord_on("C Major", (("C4", 261.63), ("E4", 329.63), ("G4", 392.00)))

    audio = synth.render(512)

    assert synth.active_voice_count == 3
    assert np.max(np.abs(audio)) > 0.01


def test_chord_frequency_glides_without_retriggering_voices():
    synth = Synthesizer(SynthConfig(sample_rate=8000, attack=0.001, portamento=0.001))
    synth.chord_on("C Major", (("C4", 261.63), ("E4", 329.63), ("G4", 392.00)))
    synth.render(100)
    synth.set_chord_frequencies((293.66, 369.99, 440.00))

    assert synth.active_voice_count == 3
    assert synth.target_frequency == 293.66
