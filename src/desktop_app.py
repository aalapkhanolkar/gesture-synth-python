"""Professional dark-mode desktop UI for the two-hand gesture synthesizer."""

from __future__ import annotations

from dataclasses import replace
import logging
import math
from pathlib import Path
import time
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageGrab, ImageTk
import tkinter as tk
from tkinter import ttk

from .camera import Camera
from .config import AppConfig, NoteConfig
from .gesture_detector import GestureStabilizer, count_extended_fingers, supported_gesture
from .hand_tracker import HandDetection, HandTracker
from .music import (
    Chord,
    ROOT_SEMITONES,
    ScaleLayout,
    available_chord_labels,
    available_note_names,
    chord_from_label,
    note_from_name,
)
from .synth import Synthesizer
from .ui import FPSCounter, draw_overlay


LOGGER = logging.getLogger(__name__)

BACKGROUND = "#0d0f13"
SURFACE = "#151922"
SURFACE_RAISED = "#202631"
BORDER = "#303946"
TEXT = "#f4f7fb"
MUTED = "#9aa4b2"
MINT = "#77e6ca"
GOLD = "#f2c55c"
CORAL = "#f1788b"


class GestureSynthApp:
    """Persistent two-hand performance surface with note and chord modes."""

    _PREVIEW_WIDTH = 960
    _PREVIEW_HEIGHT = 540
    _UPDATE_INTERVAL_MS = 15

    def __init__(self, config: AppConfig, *, audio_enabled: bool = True) -> None:
        self.config = config
        self.root = tk.Tk()
        self.root.title("Gesture Synth | Performance Studio")
        self.root.geometry("1440x900")
        self.root.minsize(1180, 760)
        self.root.configure(bg=BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._configure_style()

        self.camera = Camera(config.camera)
        self.tracker = HandTracker(config.gesture)
        self.synth = Synthesizer(config.synth)
        self.stabilizer = GestureStabilizer(config.gesture.stable_frames)
        self.fps_counter = FPSCounter()
        self.scale_layout = ScaleLayout(config.music.root, config.music.scale)
        self.chord_slots = {
            fingers: Chord(slot.root, slot.quality)
            for fingers, slot in config.music.chord_slots.items()
        }
        self.base_amplitude = config.synth.amplitude
        self.last_sound_id: Optional[str] = None
        self.closed = False
        self.audio_enabled = False

        mode = config.music.performance_mode.lower()
        self.performance_mode = "scale" if mode not in {"scale", "notes", "chords"} else mode
        self.connection_var = tk.StringVar(value=self.camera.status)
        self.mode_status_var = tk.StringVar()
        self.gesture_var = tk.StringVar(value="GESTURE  -")
        self.now_playing_var = tk.StringVar(value="Waiting for playing hand")
        self.detail_var = tk.StringVar(value="Hold 1-5 fingers to begin")
        self.control_var = tk.StringVar(value=f"{config.music.control_hand} hand waiting")
        self.fps_var = tk.StringVar(value="FPS  0.0")
        self.audio_var = tk.StringVar(value="AUDIO  OFF")
        self.footer_var = tk.StringVar()
        self.waveform_var = tk.StringVar(value=config.synth.waveform)
        self.root_var = tk.StringVar(value=config.music.root)
        self.scale_var = tk.StringVar(value=config.music.scale.title())
        self.chord_slot_vars = {
            fingers: tk.StringVar(value=self.chord_slots[fingers].display_name)
            for fingers in range(1, 6)
        }
        self.note_slots = {
            fingers: note_from_name(slot.name)
            for fingers, slot in config.music.note_slots.items()
        }
        self.note_slot_vars = {
            fingers: tk.StringVar(value=self.note_slots[fingers].name)
            for fingers in range(1, 6)
        }
        self.note_selectors: list[ttk.Combobox] = []
        self.chord_selectors: list[ttk.Combobox] = []

        self._build_ui()
        self._refresh_performance_labels()
        if audio_enabled:
            self.set_audio(True)
        else:
            self.audio_button.configure(text="Enable audio")
        self.root.after(0, self._update_frame)

    def run(self) -> None:
        """Open the desktop UI event loop."""

        self.root.mainloop()

    def set_audio(self, enabled: bool) -> None:
        """Start or stop sound output without closing the camera application."""

        if enabled and not self.audio_enabled:
            try:
                self.synth.start()
            except Exception as exc:
                LOGGER.exception("Could not start audio output")
                self.audio_var.set("AUDIO  ERROR")
                self.detail_var.set(f"Audio device error: {exc}")
                return
            self.audio_enabled = True
            self.audio_var.set("AUDIO  ON")
            self.audio_button.configure(text="Mute audio")
            return

        if not enabled and self.audio_enabled:
            self.synth.note_off()
            self.synth.close()
            self.audio_enabled = False
            self.audio_var.set("AUDIO  MUTED")
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

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Dark.TCombobox", fieldbackground=SURFACE_RAISED, background=SURFACE_RAISED, foreground=TEXT, arrowcolor=MINT, bordercolor=BORDER)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", SURFACE_RAISED)], foreground=[("readonly", TEXT)])
        style.configure("Dark.TButton", background=SURFACE_RAISED, foreground=TEXT, bordercolor=BORDER, padding=(12, 8))
        style.map("Dark.TButton", background=[("active", "#283a57")])

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=BACKGROUND, padx=26, pady=18)
        header.pack(fill="x")
        tk.Label(header, text="GESTURE SYNTH", font=("Segoe UI", 21, "bold"), fg=TEXT, bg=BACKGROUND).pack(side="left")
        tk.Label(header, text="LIVE PERFORMANCE", font=("Segoe UI", 9, "bold"), fg=MINT, bg=BACKGROUND, padx=14).pack(side="left")
        tk.Label(header, textvariable=self.connection_var, font=("Segoe UI", 10), fg=MUTED, bg=BACKGROUND).pack(side="right")

        deck = tk.Frame(self.root, bg=SURFACE, padx=20, pady=15, highlightbackground=BORDER, highlightthickness=1)
        deck.pack(fill="x", padx=20)
        self._build_global_controls(deck)
        self._build_note_rack(deck)
        self._build_chord_rack(deck)

        content = tk.Frame(self.root, bg=BACKGROUND, padx=20, pady=18)
        content.pack(fill="both", expand=True)
        preview_surface = tk.Frame(content, bg="#020617", highlightbackground=BORDER, highlightthickness=1)
        preview_surface.pack(side="left", fill="both", expand=True)
        self.preview_label = tk.Label(preview_surface, bg="#020617", bd=0)
        self.preview_label.pack(fill="both", expand=True)

        panel = tk.Frame(content, bg=SURFACE, padx=20, pady=20, width=310, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(side="right", fill="y", padx=(18, 0))
        panel.pack_propagate(False)
        self._build_status_panel(panel)

        footer = tk.Label(self.root, textvariable=self.footer_var, font=("Segoe UI", 10), fg=MUTED, bg=BACKGROUND, pady=12)
        footer.pack(fill="x")

    def _build_global_controls(self, parent: tk.Frame) -> None:
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x")
        self._section_label(row, "PERFORM").pack(side="left")
        self.scale_button = self._mode_button(row, "Scale", lambda: self._set_performance_mode("scale"))
        self.scale_button.pack(side="left", padx=(10, 4))
        self.notes_button = self._mode_button(row, "Notes", lambda: self._set_performance_mode("notes"))
        self.notes_button.pack(side="left", padx=(0, 4))
        self.chords_button = self._mode_button(row, "Chords", lambda: self._set_performance_mode("chords"))
        self.chords_button.pack(side="left", padx=(0, 20))

        self._section_label(row, "SCALE").pack(side="left")
        self.root_picker = ttk.Combobox(row, textvariable=self.root_var, values=tuple(ROOT_SEMITONES), state="readonly", width=5, style="Dark.TCombobox")
        root_picker = self.root_picker
        root_picker.pack(side="left", padx=(10, 5))
        root_picker.bind("<<ComboboxSelected>>", self._change_scale)
        self.scale_picker = ttk.Combobox(row, textvariable=self.scale_var, values=("Major", "Minor"), state="readonly", width=9, style="Dark.TCombobox")
        scale_picker = self.scale_picker
        scale_picker.pack(side="left", padx=(0, 20))
        scale_picker.bind("<<ComboboxSelected>>", self._change_scale)

        self._section_label(row, "WAVEFORM").pack(side="left")
        waveform = ttk.Combobox(
            row,
            textvariable=self.waveform_var,
            values=("sine", "square", "sawtooth", "triangle"),
            state="readonly",
            width=11,
            style="Dark.TCombobox",
        )
        waveform.pack(side="left", padx=(10, 0))
        waveform.bind("<<ComboboxSelected>>", self._change_waveform)

    def _build_note_rack(self, parent: tk.Frame) -> None:
        self.note_rack = tk.Frame(parent, bg=SURFACE)
        header = tk.Frame(self.note_rack, bg=SURFACE)
        header.pack(fill="x", pady=(14, 8))
        self._section_label(header, "NOTE SLOTS").pack(side="left")
        tk.Label(header, text="Choose a specific note for each gesture", font=("Segoe UI", 9), fg=MUTED, bg=SURFACE).pack(side="left", padx=10)
        slots = tk.Frame(self.note_rack, bg=SURFACE)
        slots.pack(fill="x")
        note_names = available_note_names()
        for fingers in range(1, 6):
            slot = tk.Frame(slots, bg=SURFACE_RAISED, padx=10, pady=8, highlightbackground=BORDER, highlightthickness=1)
            slot.pack(side="left", fill="x", expand=True, padx=(0 if fingers == 1 else 8, 0))
            tk.Label(slot, text=f"GESTURE {fingers}", font=("Segoe UI", 8, "bold"), fg=MINT, bg=SURFACE_RAISED).pack(anchor="w")
            selector = ttk.Combobox(slot, textvariable=self.note_slot_vars[fingers], values=note_names, state="readonly", width=15, style="Dark.TCombobox")
            selector.pack(fill="x", pady=(3, 0))
            selector.bind("<<ComboboxSelected>>", lambda _event, slot_number=fingers: self._change_note_slot(slot_number))
            self.note_selectors.append(selector)

    def _build_chord_rack(self, parent: tk.Frame) -> None:
        self.chord_rack = tk.Frame(parent, bg=SURFACE)
        header = tk.Frame(self.chord_rack, bg=SURFACE)
        header.pack(fill="x", pady=(0, 8))
        self._section_label(header, "CHORD SLOTS").pack(side="left")
        tk.Label(header, text="Each stable finger count selects one live synth chord", font=("Segoe UI", 9), fg=MUTED, bg=SURFACE).pack(side="left", padx=10)
        slots = tk.Frame(self.chord_rack, bg=SURFACE)
        slots.pack(fill="x")
        labels = available_chord_labels()
        for fingers in range(1, 6):
            slot = tk.Frame(slots, bg=SURFACE_RAISED, padx=10, pady=8, highlightbackground=BORDER, highlightthickness=1)
            slot.pack(side="left", fill="x", expand=True, padx=(0 if fingers == 1 else 8, 0))
            tk.Label(slot, text=f"GESTURE {fingers}", font=("Segoe UI", 8, "bold"), fg=GOLD, bg=SURFACE_RAISED).pack(anchor="w")
            selector = ttk.Combobox(slot, textvariable=self.chord_slot_vars[fingers], values=labels, state="readonly", width=15, style="Dark.TCombobox")
            selector.pack(fill="x", pady=(3, 0))
            selector.bind("<<ComboboxSelected>>", lambda _event, slot_number=fingers: self._change_chord_slot(slot_number))
            self.chord_selectors.append(selector)

    def _build_status_panel(self, panel: tk.Frame) -> None:
        tk.Label(panel, text="LIVE STATUS", font=("Segoe UI", 11, "bold"), fg=MINT, bg=SURFACE).pack(anchor="w", pady=(0, 8))
        tk.Label(panel, text="Gesture state and expressive controls", font=("Segoe UI", 9), fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(0, 18))
        for variable, color in (
            (self.mode_status_var, GOLD),
            (self.gesture_var, TEXT),
            (self.now_playing_var, TEXT),
            (self.detail_var, MUTED),
            (self.control_var, TEXT),
            (self.fps_var, MUTED),
            (self.audio_var, MINT),
        ):
            tk.Label(panel, textvariable=variable, anchor="w", justify="left", wraplength=260, font=("Segoe UI", 10, "bold"), fg=color, bg=SURFACE).pack(fill="x", pady=(0, 12))

        divider = tk.Frame(panel, bg=BORDER, height=1)
        divider.pack(fill="x", pady=(5, 15))
        self.audio_button = ttk.Button(panel, text="Mute audio", command=self._toggle_audio, style="Dark.TButton")
        self.audio_button.pack(fill="x", pady=(0, 8))
        ttk.Button(panel, text="Save screenshot", command=self._save_screenshot, style="Dark.TButton").pack(fill="x", pady=(0, 8))
        ttk.Button(panel, text="Reconnect camera", command=self._reconnect_camera, style="Dark.TButton").pack(fill="x", pady=(0, 8))
        ttk.Button(panel, text="Close", command=self.close, style="Dark.TButton").pack(fill="x")

    @staticmethod
    def _section_label(parent: tk.Frame, text: str) -> tk.Label:
        return tk.Label(parent, text=text, font=("Segoe UI", 9, "bold"), fg=MUTED, bg=parent.cget("bg"))

    @staticmethod
    def _mode_button(parent: tk.Frame, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, font=("Segoe UI", 10, "bold"), fg=TEXT, bg=SURFACE_RAISED, activeforeground=TEXT, activebackground="#283a57", relief="flat", padx=14, pady=6, cursor="hand2")

    def _update_frame(self) -> None:
        if self.closed:
            return
        frame = self.camera.read()
        self.connection_var.set(self.camera.status)
        if frame is None:
            display_frame = self._placeholder_frame()
            self._release_sound()
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
            raw_count = count_extended_fingers(playing_hand.landmarks.landmark, playing_hand.handedness, mirrored=self.config.gesture.mirror_camera)

        state = self.stabilizer.update(supported_gesture(raw_count, range(1, 6)))
        volume, pitch_bend = self._expression_for_hand(control_hand)
        self.synth.config = replace(self.synth.config, amplitude=volume)
        display_note, sound_name, detail = self._play_selected_sound(state.stable_fingers, pitch_bend)

        self.tracker.draw(frame, results)
        self._draw_hand_roles(frame, playing_hand, control_hand)
        fps = self.fps_counter.update()
        draw_overlay(frame, state, display_note, self.synth.config.waveform, fps)
        self.gesture_var.set(f"GESTURE  {state.label}")
        self.now_playing_var.set(sound_name or "Waiting for playing hand")
        self.detail_var.set(detail)
        if control_hand is None:
            self.control_var.set(f"{self.config.music.control_hand} hand waiting")
        else:
            self.control_var.set(f"EXPRESSION  volume {volume / self.base_amplitude:.0%}  |  bend {pitch_bend:+.1f} st")
        self.fps_var.set(f"FPS  {fps:.1f}")
        return frame

    def _play_selected_sound(self, fingers: Optional[int], pitch_bend: float) -> tuple[Optional[NoteConfig], str, str]:
        if self.performance_mode == "scale":
            note = self.scale_layout.note_for_fingers(fingers)
            if note is None:
                self._release_sound()
                return None, "", "Hold a stable 1-5 finger gesture"
            frequency = self._bent_frequency(note.frequency, pitch_bend)
            sound_id = f"note:{note.name}"
            if sound_id != self.last_sound_id:
                self.synth.note_on(note.name, frequency)
                self.last_sound_id = sound_id
            else:
                self.synth.set_frequency(frequency)
            return note, f"NOTE  {note.name}", f"{self.scale_layout.degree_label(fingers)}  |  {frequency:.2f} Hz"

        if self.performance_mode == "notes":
            note = self.note_slots.get(fingers or 0)
            if note is None:
                self._release_sound()
                return None, "", "Hold a stable 1-5 finger gesture"
            frequency = self._bent_frequency(note.frequency, pitch_bend)
            sound_id = f"note-slot:{fingers}:{note.name}"
            if sound_id != self.last_sound_id:
                self.synth.note_on(note.name, frequency)
                self.last_sound_id = sound_id
            else:
                self.synth.set_frequency(frequency)
            return note, f"NOTE  {note.name}", f"Slot {fingers}  |  {frequency:.2f} Hz"

        chord = self.chord_slots.get(fingers or 0)
        if chord is None:
            self._release_sound()
            return None, "", "Hold a stable 1-5 finger gesture"
        notes = chord.notes()
        bent_frequencies = tuple(self._bent_frequency(note.frequency, pitch_bend) for note in notes)
        sound_id = f"chord:{chord.display_name}"
        if sound_id != self.last_sound_id:
            self.synth.chord_on(chord.display_name, tuple((note.name, frequency) for note, frequency in zip(notes, bent_frequencies)))
            self.last_sound_id = sound_id
        else:
            self.synth.set_chord_frequencies(bent_frequencies)
        note_names = "  ".join(note.name for note in notes)
        return notes[0], f"CHORD  {chord.display_name}", f"{note_names}  |  {bent_frequencies[0]:.2f} Hz"

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
        return volume, (position - 0.5) * 2.0 * self.config.music.max_pitch_bend_semitones

    @staticmethod
    def _bent_frequency(frequency: float, pitch_bend: float) -> float:
        return frequency * math.pow(2.0, pitch_bend / 12.0)

    def _release_sound(self) -> None:
        if self.last_sound_id is not None:
            self.synth.note_off()
            self.last_sound_id = None

    def _draw_hand_roles(self, frame: np.ndarray, playing_hand: Optional[HandDetection], control_hand: Optional[HandDetection]) -> None:
        for hand, label, color in ((playing_hand, "PLAY", (80, 220, 180)), (control_hand, "CONTROL", (255, 190, 80))):
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

    def _set_performance_mode(self, mode: str) -> None:
        if mode == self.performance_mode:
            return
        self.performance_mode = mode
        self._release_sound()
        self._refresh_performance_labels()

    def _refresh_performance_labels(self) -> None:
        scale_active = self.performance_mode == "scale"
        notes_active = self.performance_mode == "notes"
        chords_active = self.performance_mode == "chords"
        self.scale_button.configure(bg=MINT if scale_active else SURFACE_RAISED, fg=BACKGROUND if scale_active else TEXT)
        self.notes_button.configure(bg=MINT if notes_active else SURFACE_RAISED, fg=BACKGROUND if notes_active else TEXT)
        self.chords_button.configure(bg=GOLD if chords_active else SURFACE_RAISED, fg=BACKGROUND if chords_active else TEXT)
        self.root_picker.configure(state="readonly" if scale_active else "disabled")
        self.scale_picker.configure(state="readonly" if scale_active else "disabled")
        for selector in self.note_selectors:
            selector.configure(state="readonly" if notes_active else "disabled")
        for selector in self.chord_selectors:
            selector.configure(state="readonly" if chords_active else "disabled")
        self.note_rack.pack_forget()
        self.chord_rack.pack_forget()
        if scale_active:
            self.mode_status_var.set(f"SCALE  |  {self.scale_layout.display_name}")
            self.footer_var.set(f"{self.config.music.playing_hand} hand: Root, 3rd, 4th, 5th, Octave. {self.config.music.control_hand} hand: volume and pitch bend.")
        elif notes_active:
            self.note_rack.pack(fill="x", pady=(14, 0))
            self.mode_status_var.set("NOTES  |  Five editable gesture slots")
            self.footer_var.set(f"{self.config.music.playing_hand} hand: gestures 1-5 trigger selected notes. {self.config.music.control_hand} hand: volume and pitch bend.")
        else:
            self.chord_rack.pack(fill="x", pady=(14, 0))
            self.mode_status_var.set("CHORDS  |  Gestures 1-5 select chord slots")
            self.footer_var.set(f"{self.config.music.playing_hand} hand: gestures 1-5 trigger selected chords. {self.config.music.control_hand} hand: volume and pitch bend.")

    def _change_scale(self, _event: object) -> None:
        self.scale_layout = ScaleLayout(self.root_var.get(), self.scale_var.get().lower())
        self._release_sound()
        self._refresh_performance_labels()

    def _change_chord_slot(self, fingers: int) -> None:
        self.chord_slots[fingers] = chord_from_label(self.chord_slot_vars[fingers].get())
        self._release_sound()

    def _change_note_slot(self, fingers: int) -> None:
        self.note_slots[fingers] = note_from_name(self.note_slot_vars[fingers].get())
        self._release_sound()

    def _change_waveform(self, _event: object) -> None:
        self.synth.config = replace(self.synth.config, waveform=self.waveform_var.get())

    def _toggle_audio(self) -> None:
        self.set_audio(not self.audio_enabled)

    def _reconnect_camera(self) -> None:
        self.camera.reconnect()

    def _save_screenshot(self) -> None:
        """Save only this application window as a real runtime screenshot."""

        self.root.update_idletasks()
        left = self.root.winfo_rootx()
        top = self.root.winfo_rooty()
        right = left + self.root.winfo_width()
        bottom = top + self.root.winfo_height()
        output_dir = Path(__file__).resolve().parents[1] / "assets" / "screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"gesture-synth-{time.strftime('%Y%m%d-%H%M%S')}.png"
        ImageGrab.grab(bbox=(left, top, right, bottom)).save(destination)
        self.connection_var.set(f"Screenshot saved: {destination.name}")
