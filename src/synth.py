"""Low-latency polyphonic software synthesizer powered by sounddevice."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import threading
from typing import Iterable, Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - exercised on machines without audio libs
    sd = None

from .config import SynthConfig


LOGGER = logging.getLogger(__name__)


@dataclass
class ActiveNote:
    """Current note or chord root metadata exposed to the UI."""

    name: str
    frequency: float


@dataclass
class _Voice:
    """Internal oscillator state for one note in a chord."""

    name: str
    current_frequency: float
    target_frequency: float
    phase: float = 0.0
    envelope: float = 0.0
    gate: bool = True
    sustain_phase: bool = False
    current: bool = True


class Synthesizer:
    """Continuous mono or chord synthesizer with ADSR, glide, and release tails."""

    def __init__(self, config: SynthConfig) -> None:
        self.config = config
        self.sample_rate = config.sample_rate
        self.phase = 0.0
        self.current_frequency = 440.0
        self.target_frequency = 440.0
        self.active_note: Optional[ActiveNote] = None
        self._voices: list[_Voice] = []
        self._lock = threading.RLock()
        self._stream = None

    @property
    def is_running(self) -> bool:
        return self._stream is not None

    @property
    def active_voice_count(self) -> int:
        """Number of currently held voices, excluding release tails."""

        with self._lock:
            return sum(voice.current for voice in self._voices)

    def start(self) -> None:
        """Start the realtime audio stream."""

        if sd is None:
            raise RuntimeError("sounddevice is not installed. Run pip install -r requirements.txt")
        if self._stream is not None:
            return
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            blocksize=self.config.block_size,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()
        LOGGER.info("Audio stream started at %s Hz.", self.sample_rate)

    def close(self) -> None:
        """Stop and dispose of the audio stream."""

        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None
        LOGGER.info("Audio stream stopped.")

    def note_on(self, name: str, frequency: float) -> None:
        """Start one note without rebuilding the continuous audio stream."""

        self._trigger(name, ((name, frequency),))

    def chord_on(self, name: str, notes: Iterable[tuple[str, float]]) -> None:
        """Start a chord as independent oscillator voices with a shared ADSR shape."""

        voice_notes = tuple(notes)
        if not voice_notes:
            raise ValueError("A chord must contain at least one note")
        self._trigger(name, voice_notes)

    def note_off(self) -> None:
        """Release all held notes smoothly while existing tails finish rendering."""

        with self._lock:
            for voice in self._voices:
                if voice.current:
                    voice.current = False
                    voice.gate = False
            self.active_note = None

    def set_frequency(self, frequency: float) -> None:
        """Glide the active single-note voice without retriggering its envelope."""

        self.set_chord_frequencies((frequency,))

    def set_chord_frequencies(self, frequencies: Iterable[float]) -> None:
        """Glide the currently held chord voices without retriggering their envelopes."""

        with self._lock:
            current_voices = [voice for voice in self._voices if voice.current]
            for voice, frequency in zip(current_voices, frequencies):
                voice.target_frequency = float(frequency)
            if current_voices:
                self.target_frequency = current_voices[0].target_frequency
                if self.active_note is not None:
                    self.active_note.frequency = self.target_frequency

    def render(self, frames: int) -> np.ndarray:
        """Render a block of mono audio samples for audio callbacks or tests."""

        output = np.zeros(frames, dtype=np.float32)
        with self._lock:
            waveform = self.config.waveform.lower()
            attack_step = 1.0 / max(1, int(self.config.attack * self.sample_rate))
            decay_step = (1.0 - self.config.sustain) / max(1, int(self.config.decay * self.sample_rate))
            glide = self._glide_coefficient()

            for index in range(frames):
                sample = 0.0
                audible_voices = 0
                for voice in self._voices:
                    voice.current_frequency += (voice.target_frequency - voice.current_frequency) * glide
                    self._advance_envelope(voice, attack_step, decay_step)
                    if voice.envelope > 0.0:
                        sample += voice.envelope * self._oscillator_sample(waveform, voice.phase)
                        audible_voices += 1
                    voice.phase = (voice.phase + voice.current_frequency / self.sample_rate) % 1.0

                if audible_voices:
                    output[index] = self.config.amplitude * sample / math.sqrt(audible_voices)
                self._voices = [voice for voice in self._voices if voice.gate or voice.envelope > 1e-5]

            current_voices = [voice for voice in self._voices if voice.current]
            if current_voices:
                self.current_frequency = current_voices[0].current_frequency
                self.target_frequency = current_voices[0].target_frequency
                self.phase = current_voices[0].phase
        return output

    def _trigger(self, name: str, notes: tuple[tuple[str, float], ...]) -> None:
        with self._lock:
            for voice in self._voices:
                if voice.current:
                    voice.current = False
                    voice.gate = False
            self._voices.extend(
                _Voice(note_name, float(frequency), float(frequency))
                for note_name, frequency in notes
            )
            self.active_note = ActiveNote(name=name, frequency=float(notes[0][1]))
            self.current_frequency = float(notes[0][1])
            self.target_frequency = float(notes[0][1])

    def _audio_callback(self, outdata, frames, time, status) -> None:
        if status:
            LOGGER.warning("Audio callback status: %s", status)
        outdata[:, 0] = self.render(frames)

    def _advance_envelope(self, voice: _Voice, attack_step: float, decay_step: float) -> None:
        if voice.gate:
            if voice.envelope < 1.0 and not voice.sustain_phase:
                voice.envelope = min(1.0, voice.envelope + attack_step)
                if math.isclose(voice.envelope, 1.0):
                    voice.sustain_phase = True
            elif voice.envelope > self.config.sustain:
                voice.envelope = max(self.config.sustain, voice.envelope - decay_step)
            else:
                voice.envelope = self.config.sustain
            return

        release_step = max(voice.envelope, self.config.sustain) / max(1, int(self.config.release * self.sample_rate))
        voice.envelope = max(0.0, voice.envelope - release_step)

    @staticmethod
    def _oscillator_sample(waveform: str, phase: float) -> float:
        if waveform == "sine":
            return math.sin(2.0 * math.pi * phase)
        if waveform == "square":
            return 1.0 if phase < 0.5 else -1.0
        if waveform == "sawtooth":
            return 2.0 * phase - 1.0
        if waveform == "triangle":
            return 4.0 * abs(phase - 0.5) - 1.0
        return math.sin(2.0 * math.pi * phase)

    def _glide_coefficient(self) -> float:
        samples = max(1, int(self.config.portamento * self.sample_rate))
        return min(1.0, 1.0 / samples)
