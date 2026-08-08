"""Low-latency software synthesizer powered by sounddevice."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import threading
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - exercised on machines without audio libs
    sd = None

from .config import SynthConfig


LOGGER = logging.getLogger(__name__)


@dataclass
class ActiveNote:
    """Current note metadata."""

    name: str
    frequency: float


class Synthesizer:
    """Continuously running monophonic oscillator with ADSR envelope."""

    def __init__(self, config: SynthConfig) -> None:
        self.config = config
        self.sample_rate = config.sample_rate
        self.phase = 0.0
        self.current_frequency = 440.0
        self.target_frequency = 440.0
        self.active_note: Optional[ActiveNote] = None
        self._gate = False
        self._envelope = 0.0
        self._sustain_phase = False
        self._lock = threading.RLock()
        self._stream = None

    @property
    def is_running(self) -> bool:
        return self._stream is not None

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
        """Start or glide to a note without recreating the audio engine."""

        with self._lock:
            self.active_note = ActiveNote(name=name, frequency=frequency)
            self.target_frequency = float(frequency)
            self._gate = True
            self._sustain_phase = False

    def note_off(self) -> None:
        """Release the current note smoothly."""

        with self._lock:
            self._gate = False
            self.active_note = None
            self._sustain_phase = False

    def set_frequency(self, frequency: float) -> None:
        """Glide an active note to a new frequency without retriggering its envelope."""

        with self._lock:
            self.target_frequency = float(frequency)
            if self.active_note is not None:
                self.active_note.frequency = float(frequency)

    def render(self, frames: int) -> np.ndarray:
        """Render a block of mono audio samples for tests or offline use."""

        output = np.zeros(frames, dtype=np.float32)
        with self._lock:
            waveform = self.config.waveform.lower()
            amplitude = self.config.amplitude
            attack_step = 1.0 / max(1, int(self.config.attack * self.sample_rate))
            decay_step = (1.0 - self.config.sustain) / max(1, int(self.config.decay * self.sample_rate))
            release_step = self.config.sustain / max(1, int(self.config.release * self.sample_rate))
            glide = self._glide_coefficient()

            for index in range(frames):
                self.current_frequency += (self.target_frequency - self.current_frequency) * glide
                self._advance_envelope(attack_step, decay_step, release_step)
                output[index] = amplitude * self._envelope * self._oscillator_sample(waveform)
                self.phase = (self.phase + self.current_frequency / self.sample_rate) % 1.0

        return output

    def _audio_callback(self, outdata, frames, time, status) -> None:
        if status:
            LOGGER.warning("Audio callback status: %s", status)
        outdata[:, 0] = self.render(frames)

    def _advance_envelope(self, attack_step: float, decay_step: float, release_step: float) -> None:
        if self._gate:
            if self._envelope < 1.0 and not self._sustain_phase:
                self._envelope = min(1.0, self._envelope + attack_step)
                if math.isclose(self._envelope, 1.0):
                    self._sustain_phase = True
            elif self._envelope > self.config.sustain:
                self._envelope = max(self.config.sustain, self._envelope - decay_step)
            else:
                self._envelope = self.config.sustain
        else:
            self._envelope = max(0.0, self._envelope - release_step)

    def _oscillator_sample(self, waveform: str) -> float:
        if waveform == "sine":
            return math.sin(2.0 * math.pi * self.phase)
        if waveform == "square":
            return 1.0 if self.phase < 0.5 else -1.0
        if waveform == "sawtooth":
            return 2.0 * self.phase - 1.0
        if waveform == "triangle":
            return 4.0 * abs(self.phase - 0.5) - 1.0
        LOGGER.debug("Unknown waveform %s; falling back to sine.", waveform)
        return math.sin(2.0 * math.pi * self.phase)

    def _glide_coefficient(self) -> float:
        samples = max(1, int(self.config.portamento * self.sample_rate))
        return min(1.0, 1.0 / samples)
