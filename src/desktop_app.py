"""Tkinter desktop interface for the real-time two-hand gesture synthesizer."""

from __future__ import annotations

from dataclasses import replace
import logging
import math
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk

from .camera import Camera
from .config import AppConfig, NoteConfig
from .gesture_detector import GestureStabilizer, count_extended_fingers, supported_gesture
from .hand_tracker import HandDetection, HandTracker
from .music import ROOT_SEMITONES, ScaleLayout
from .synth import Synthesizer
from .ui import FPSCounter, draw_overlay


LOGGER = logging.getLogger(__name__)


class GestureSynthApp:
    """Persistent desktop UI with a playing hand and an expressive control hand."""

    _PREVIEW_WIDTH = 960
    _PREVIEW_HEIGHT = 540
    _UPDATE_INTERVAL_MS = 15

    def __init__(self, config: AppConfig, *, audio_enabled: bool = True) -> None:
        self.config = config
        self.root = tk.Tk()
        self.root.title("Gesture Synth | Two-Hand Performance")
        self.root.minsize(1120, 720)
        self.root.configure(bg="#111827")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.camera = Camera(config.camera)
        self.tracker = HandTracker(config.gesture)
        self.synth = Synthesizer(config.synth)
        self.stabilizer = GestureStabilizer(config.gesture.stable_frames)
        self.fps_counter = FPSCounter()
        self.scale_layout = ScaleLayout(config.music.root, config.music.scale)
        self.base_amplitude = config.synth.amplitude
        self.last_note_name: Optional[str] = None
        self.closed = False
        self.audio_enabled = False

        self.connection_var = tk.StringVar(value=self.camera.status)
        self.scale_var = tk.StringVar(value=self.scale_layout.display_name)
        self.gesture_var = tk.StringVar(value="PLAY GESTURE: waiting")
        self.degree_var = tk.StringVar(value="DEGREE: -")
        self.note_var = tk.StringVar(value="NOTE: none")
        self.frequency_var = tk.StringVar(value="FREQUENCY: 0.00 Hz")
        self.control_var = tk.StringVar(value=f"CONTROL ({config.music.control_hand}): waiting")
        self.fps_var = tk.StringVar(value="FPS: 0.0")
        self.audio_var = tk.StringVar(value="AUDIO: off")
        self.waveform_var = tk.StringVar(value=config.synth.waveform)
        self.root_var = tk.StringVar(value=config.music.root)
        self.mode_var = tk.StringVar(value=config.music.scale.title())
        self.mapping_var = tk.StringVar(value=self.scale_layout.mapping_label())

        self._build_ui()
        if audio_enabled:
            self.set_audio(True)
        else:
            self.audio_button.configure(text="Enable audio")
        self.root.after(0, self._update_frame)

    def run(self) -> None:
        """Open the desktop UI event loop."""

        self.root.mainloop()

    def set_audio(self, enabled: bool) -> None:
        """Start or stop the continuous sounddevice stream without closing the UI."""

        if enabled and not self.audio_enabled:
            try:
                self.synth.start()
            except Exception as exc:
                LOGGER.exception("Could not start audio output")
                self.audio_var.set(f"AUDIO: error ({exc})")
                return
            self.audio_enabled = True
            self.audio_var.set("AUDIO: on")
            self.audio_button.configure(text="Mute audio")
            return

        if not enabled and self.audio_enabled:
            self.synth.note_off()
            self.synth.close()
            self.audio_enabled = False
            self.audio_var.set("AUDIO: muted")
            self.audio_button.configure(text="Enable audio")

    def close(self) -> None:
        """Release camera/audio resources and close the window."""

        if self.closed:
            return
        self.closed = True
        self.synth.note_off()
        self.synth.close()
        self.tracker.close()
        self.camera.close()
        self.root.destroy()

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg="#111827", padx=20, pady=14)
        header.pack(fill="x")
        tk.Label(
            header,
            text="GESTURE SYNTH",
            font=("Segoe UI", 18, "bold"),
            fg="#7ee8c3",
            bg="#111827",
        ).pack(side="left")
        tk.Label(
            header,
            text="Two-hand performance",
            font=("Segoe UI", 11),
            fg="#94a3b8",
            bg="#111827",
            padx=12,
        ).pack(side="left")
        tk.Label(
            header,
            textvariable=self.connection_var,
            font=("Segoe UI", 10),
            fg="#cbd5e1",
            bg="#111827",
        ).pack(side="right")

        content = tk.Frame(self.root, bg="#111827", padx=20, pady=4)
        content.pack(fill="both", expand=True)
        self.preview_label = tk.Label(content, bg="#020617", bd=0)
        self.preview_label.pack(side="left", fill="both", expand=True)

        panel = tk.Frame(content, bg="#1e293b", padx=18, pady=18, width=300)
        panel.pack(side="right", fill="y", padx=(16, 0))
        panel.pack_propagate(False)

        tk.Label(panel, text="Scale", anchor="w", font=("Segoe UI", 10), fg="#cbd5e1", bg="#1e293b").pack(fill="x")
        scale_controls = tk.Frame(panel, bg="#1e293b")
        scale_controls.pack(fill="x", pady=(4, 16))
        root_picker = ttk.Combobox(
            scale_controls,
            textvariable=self.root_var,
            values=tuple(ROOT_SEMITONES),
            state="readonly",
            width=6,
        )
        root_picker.pack(side="left")
        root_picker.bind("<<ComboboxSelected>>", self._change_scale)
        mode_picker = ttk.Combobox(
            scale_controls,
            textvariable=self.mode_var,
            values=("Major", "Minor"),
            state="readonly",
            width=10,
        )
        mode_picker.pack(side="right")
        mode_picker.bind("<<ComboboxSelected>>", self._change_scale)
        tk.Label(
            panel,
            textvariable=self.scale_var,
            anchor="w",
            font=("Segoe UI", 12, "bold"),
            fg="#7ee8c3",
            bg="#1e293b",
        ).pack(fill="x", pady=(0, 10))

        for variable in (self.gesture_var, self.degree_var, self.note_var, self.frequency_var, self.control_var, self.fps_var, self.audio_var):
            tk.Label(
                panel,
                textvariable=variable,
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                fg="#f8fafc",
                bg="#1e293b",
                wraplength=260,
                justify="left",
            ).pack(fill="x", pady=(0, 8))

        tk.Label(panel, text="Waveform", anchor="w", font=("Segoe UI", 10), fg="#cbd5e1", bg="#1e293b").pack(fill="x")
        waveform = ttk.Combobox(
            panel,
            textvariable=self.waveform_var,
            values=("sine", "square", "sawtooth", "triangle"),
            state="readonly",
            width=22,
        )
        waveform.pack(fill="x", pady=(4, 12))
        waveform.bind("<<ComboboxSelected>>", self._change_waveform)

        tk.Label(panel, text="Gesture map", anchor="w", font=("Segoe UI", 10), fg="#cbd5e1", bg="#1e293b").pack(fill="x")
        tk.Label(
            panel,
            textvariable=self.mapping_var,
            anchor="w",
            justify="left",
            font=("Consolas", 9),
            fg="#cbd5e1",
            bg="#1e293b",
        ).pack(fill="x", pady=(4, 12))

        self.audio_button = ttk.Button(panel, text="Mute audio", command=self._toggle_audio)
        self.audio_button.pack(fill="x", pady=(0, 8))
        ttk.Button(panel, text="Reconnect camera", command=self._reconnect_camera).pack(fill="x", pady=(0, 8))
        ttk.Button(panel, text="Close", command=self.close).pack(fill="x")

        footer = tk.Label(
            self.root,
            text=(
                f"{self.config.music.playing_hand} hand: 1-5 fingers play Root, 3rd, 4th, 5th, Octave. "
                f"{self.config.music.control_hand} hand: height controls volume, horizontal position bends pitch."
            ),
            font=("Segoe UI", 10),
            fg="#94a3b8",
            bg="#111827",
            pady=12,
        )
        footer.pack(fill="x")

    def _update_frame(self) -> None:
        if self.closed:
            return

        frame = self.camera.read()
        self.connection_var.set(self.camera.status)
        if frame is None:
            display_frame = self._placeholder_frame()
            self._release_note()
        else:
            display_frame = self._process_frame(frame)

        self._show_frame(display_frame)
        self.root.after(self._UPDATE_INTERVAL_MS, self._update_frame)

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        if self.config.gesture.mirror_camera:
            frame = cv2.flip(frame, 1)

        detections, results = self.tracker.process_all(frame)
        playing_hand = self._hand_for_role(detections, self.config.music.playing_hand)
        control_hand = self._hand_for_role(detections, self.config.music.control_hand)
        raw_count = None
        if playing_hand is not None:
            raw_count = count_extended_fingers(
                playing_hand.landmarks.landmark,
                playing_hand.handedness,
                mirrored=self.config.gesture.mirror_camera,
            )

        state = self.stabilizer.update(supported_gesture(raw_count, range(1, 6)))
        note = self.scale_layout.note_for_fingers(state.stable_fingers)
        volume, pitch_bend = self._expression_for_hand(control_hand)
        self.synth.config = replace(self.synth.config, amplitude=volume)
        self._update_note(note, pitch_bend)

        self.tracker.draw(frame, results)
        self._draw_hand_roles(frame, playing_hand, control_hand)
        fps = self.fps_counter.update()
        draw_overlay(frame, state, note, self.synth.config.waveform, fps)
        self.gesture_var.set(f"PLAY GESTURE: {state.label}")
        self.degree_var.set(f"DEGREE: {self.scale_layout.degree_label(state.stable_fingers)}")
        self.note_var.set(f"NOTE: {note.name if note else 'none'}")
        bent_frequency = note.frequency * math.pow(2.0, pitch_bend / 12.0) if note else 0.0
        self.frequency_var.set(f"FREQUENCY: {bent_frequency:.2f} Hz" if note else "FREQUENCY: 0.00 Hz")
        if control_hand is None:
            self.control_var.set(f"CONTROL ({self.config.music.control_hand}): waiting")
        else:
            self.control_var.set(f"CONTROL: volume {volume / self.base_amplitude:.0%} | bend {pitch_bend:+.1f} st")
        self.fps_var.set(f"FPS: {fps:.1f}")
        return frame

    @staticmethod
    def _hand_for_role(detections: list[HandDetection], handedness: str) -> Optional[HandDetection]:
        target = handedness.lower()
        return next((detection for detection in detections if detection.handedness.lower() == target), None)

    def _expression_for_hand(self, hand: Optional[HandDetection]) -> tuple[float, float]:
        if hand is None:
            return self.base_amplitude, 0.0
        wrist = hand.landmarks.landmark[0]
        height = max(0.0, min(1.0, 1.0 - wrist.y))
        volume = self.config.music.minimum_amplitude + height * (self.base_amplitude - self.config.music.minimum_amplitude)
        position = max(0.0, min(1.0, wrist.x))
        pitch_bend = (position - 0.5) * 2.0 * self.config.music.max_pitch_bend_semitones
        return volume, pitch_bend

    def _update_note(self, note: Optional[NoteConfig], pitch_bend: float) -> None:
        if note is None:
            self._release_note()
            return
        frequency = note.frequency * math.pow(2.0, pitch_bend / 12.0)
        if note.name != self.last_note_name:
            self.synth.note_on(note.name, frequency)
            self.last_note_name = note.name
        else:
            self.synth.set_frequency(frequency)

    def _release_note(self) -> None:
        if self.last_note_name is not None:
            self.synth.note_off()
            self.last_note_name = None

    def _draw_hand_roles(
        self,
        frame: np.ndarray,
        playing_hand: Optional[HandDetection],
        control_hand: Optional[HandDetection],
    ) -> None:
        for hand, label, color in (
            (playing_hand, "PLAY", (80, 220, 180)),
            (control_hand, "CONTROL", (255, 190, 80)),
        ):
            if hand is None:
                continue
            wrist = hand.landmarks.landmark[0]
            x = int(wrist.x * frame.shape[1])
            y = max(28, int(wrist.y * frame.shape[0]) - 18)
            cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

    def _show_frame(self, frame: np.ndarray) -> None:
        resized = cv2.resize(frame, (self._PREVIEW_WIDTH, self._PREVIEW_HEIGHT), interpolation=cv2.INTER_AREA)
        image = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)))
        self.preview_label.configure(image=image)
        self.preview_label.image = image

    def _placeholder_frame(self) -> np.ndarray:
        frame = np.zeros((self._PREVIEW_HEIGHT, self._PREVIEW_WIDTH, 3), dtype=np.uint8)
        cv2.putText(frame, "GESTURE SYNTH", (48, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (195, 232, 126), 2, cv2.LINE_AA)
        cv2.putText(frame, self.camera.status, (48, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (230, 230, 230), 2, cv2.LINE_AA)
        cv2.putText(frame, "Use Reconnect camera after allowing camera access.", (48, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)
        return frame

    def _change_scale(self, _event: object) -> None:
        self.scale_layout = ScaleLayout(self.root_var.get(), self.mode_var.get().lower())
        self.scale_var.set(self.scale_layout.display_name)
        self.mapping_var.set(self.scale_layout.mapping_label())
        self._release_note()

    def _change_waveform(self, _event: object) -> None:
        self.synth.config = replace(self.synth.config, waveform=self.waveform_var.get())

    def _toggle_audio(self) -> None:
        self.set_audio(not self.audio_enabled)

    def _reconnect_camera(self) -> None:
        self.camera.reconnect()
