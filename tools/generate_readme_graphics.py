"""Generate deterministic technical visuals used by the project README."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "readme"
BACKGROUND = "#0f172a"
PANEL = "#1e293b"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
MINT = "#7ee8c3"
GOLD = "#f6c453"
CORAL = "#fb7185"
BLUE = "#60a5fa"


def setup_figure(width: float = 12, height: float = 6):
    fig = plt.figure(figsize=(width, height), facecolor=BACKGROUND)
    return fig


def save(fig, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / name, dpi=180, bbox_inches="tight", facecolor=BACKGROUND)
    plt.close(fig)


def waveform_gallery() -> None:
    samples = np.linspace(0, 2, 600)
    waveforms = {
        "Sine": np.sin(2 * np.pi * samples),
        "Square": np.where((samples % 1) < 0.5, 1, -1),
        "Sawtooth": 2 * (samples % 1) - 1,
        "Triangle": 4 * np.abs((samples % 1) - 0.5) - 1,
    }
    fig, axes = plt.subplots(2, 2, figsize=(12, 6), facecolor=BACKGROUND)
    fig.suptitle("Oscillator Waveforms", color=TEXT, fontsize=20, fontweight="bold", y=0.97)
    for axis, (name, values), color in zip(axes.flat, waveforms.items(), (MINT, GOLD, CORAL, BLUE)):
        axis.set_facecolor(PANEL)
        axis.plot(samples, values, color=color, linewidth=2.5)
        axis.fill_between(samples, 0, values, color=color, alpha=0.13)
        axis.set_title(name, color=TEXT, loc="left", pad=10, fontsize=13, fontweight="bold")
        axis.set_ylim(-1.25, 1.25)
        axis.set_xlim(0, 2)
        axis.grid(alpha=0.15, color=TEXT)
        axis.tick_params(colors=MUTED)
        for spine in axis.spines.values():
            spine.set_color("#334155")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, "waveform-gallery.png")


def adsr_envelope() -> None:
    fig, axis = plt.subplots(figsize=(12, 5), facecolor=BACKGROUND)
    axis.set_facecolor(PANEL)
    points_x = np.array([0.0, 0.12, 0.32, 0.73, 1.0])
    points_y = np.array([0.0, 1.0, 0.68, 0.68, 0.0])
    axis.plot(points_x, points_y, color=MINT, linewidth=3)
    axis.fill_between(points_x, 0, points_y, color=MINT, alpha=0.15)
    phases = ((0.06, "Attack", MINT), (0.22, "Decay", GOLD), (0.53, "Sustain", BLUE), (0.87, "Release", CORAL))
    for x, label, color in phases:
        axis.axvline(x, color=color, alpha=0.45, linewidth=1.5, linestyle="--")
        axis.text(x, 1.08, label, ha="center", color=color, fontsize=12, fontweight="bold")
    axis.set_title("ADSR Envelope: Smooth Note Starts and Releases", color=TEXT, loc="left", pad=18, fontsize=19, fontweight="bold")
    axis.set_xlabel("Time", color=MUTED, labelpad=12)
    axis.set_ylabel("Amplitude", color=MUTED, labelpad=12)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1.22)
    axis.grid(alpha=0.15, color=TEXT)
    axis.tick_params(colors=MUTED)
    for spine in axis.spines.values():
        spine.set_color("#334155")
    save(fig, "adsr-envelope.png")


def signal_flow() -> None:
    fig, axis = plt.subplots(figsize=(14, 5), facecolor=BACKGROUND)
    axis.set_facecolor(BACKGROUND)
    axis.axis("off")
    labels = (
        ("Webcam", "OpenCV camera"),
        ("Hands", "MediaPipe tracking"),
        ("Gesture", "Stable 1-5 count"),
        ("Scale", "Root, 3rd, 4th, 5th"),
        ("Synth", "Oscillator + ADSR"),
        ("Speakers", "Realtime audio"),
    )
    colors = (BLUE, MINT, GOLD, CORAL, MINT, BLUE)
    x_positions = np.linspace(0.06, 0.94, len(labels))
    for index, ((title, subtitle), x, color) in enumerate(zip(labels, x_positions, colors)):
        box = FancyBboxPatch((x - 0.065, 0.36), 0.13, 0.29, boxstyle="round,pad=0.02,rounding_size=0.015", facecolor=PANEL, edgecolor=color, linewidth=2)
        axis.add_patch(box)
        axis.text(x, 0.55, title, ha="center", va="center", color=TEXT, fontsize=12, fontweight="bold")
        axis.text(x, 0.43, subtitle, ha="center", va="center", color=MUTED, fontsize=8.5, wrap=True)
        if index < len(labels) - 1:
            arrow = FancyArrowPatch((x + 0.07, 0.5), (x_positions[index + 1] - 0.075, 0.5), arrowstyle="-|>", mutation_scale=15, linewidth=1.8, color="#64748b")
            axis.add_patch(arrow)
    axis.text(0.5, 0.87, "Gesture Synth Signal Flow", ha="center", color=TEXT, fontsize=21, fontweight="bold")
    axis.text(0.5, 0.16, "The audio stream remains alive while gestures change, keeping transitions smooth and responsive.", ha="center", color=MUTED, fontsize=11)
    save(fig, "signal-flow.png")


def scale_map() -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), facecolor=BACKGROUND)
    rows = (("C Major", ("C4", "E4", "F4", "G4", "C5"), (MINT, GOLD, BLUE, CORAL, MINT)), ("C Minor", ("C4", "D#4", "F4", "G4", "C5"), (MINT, GOLD, BLUE, CORAL, MINT)))
    degrees = ("1 Root", "2 Third", "3 Fourth", "4 Fifth", "5 Octave")
    for axis, (title, notes, colors) in zip(axes, rows):
        axis.set_facecolor(PANEL)
        axis.set_xlim(0.5, 5.5)
        axis.set_ylim(0, 1)
        axis.axis("off")
        axis.text(0.05, 0.88, title, transform=axis.transAxes, color=TEXT, fontsize=15, fontweight="bold")
        for index, (note, degree, color) in enumerate(zip(notes, degrees, colors), start=1):
            axis.scatter(index, 0.48, s=1400, color=color, alpha=0.95, edgecolor="#f8fafc", linewidth=1.5)
            axis.text(index, 0.48, note, ha="center", va="center", color="#0f172a", fontsize=12, fontweight="bold")
            axis.text(index, 0.14, degree, ha="center", va="center", color=MUTED, fontsize=10)
        axis.plot([1, 5], [0.48, 0.48], color="#475569", linewidth=2, zorder=0)
    fig.suptitle("Five-Finger Scale Layout", color=TEXT, fontsize=20, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, "scale-map-major-minor.png")


def expression_controls() -> None:
    fig, axis = plt.subplots(figsize=(12, 6), facecolor=BACKGROUND)
    axis.set_facecolor(PANEL)
    x = np.linspace(0, 1, 200)
    y = np.linspace(0, 1, 200)
    xx, yy = np.meshgrid(x, y)
    color = np.zeros((200, 200, 3))
    color[..., 0] = 0.18 + 0.18 * xx
    color[..., 1] = 0.25 + 0.45 * yy
    color[..., 2] = 0.33 + 0.35 * (1 - xx)
    axis.imshow(color, extent=(0, 1, 0, 1), origin="lower", aspect="auto", alpha=0.75)
    axis.axvline(0.5, color=TEXT, alpha=0.55, linestyle="--")
    axis.axhline(0.5, color=TEXT, alpha=0.3, linestyle="--")
    axis.annotate("Lower volume", (0.03, 0.08), color=TEXT, fontsize=12, fontweight="bold")
    axis.annotate("Higher volume", (0.03, 0.88), color=TEXT, fontsize=12, fontweight="bold")
    axis.annotate("-3 semitones", (0.02, 0.53), color=TEXT, fontsize=12, fontweight="bold")
    axis.annotate("+3 semitones", (0.77, 0.53), color=TEXT, fontsize=12, fontweight="bold")
    axis.scatter(0.5, 0.5, s=320, color=GOLD, edgecolor=TEXT, linewidth=1.5, zorder=3)
    axis.text(0.5, 0.5, "Hand", ha="center", va="center", color="#0f172a", fontsize=11, fontweight="bold", zorder=4)
    axis.set_title("Control Hand: Position Becomes Expression", color=TEXT, loc="left", pad=18, fontsize=19, fontweight="bold")
    axis.set_xlabel("Horizontal position: pitch bend", color=MUTED, labelpad=12)
    axis.set_ylabel("Vertical position: volume", color=MUTED, labelpad=12)
    axis.set_xticks([])
    axis.set_yticks([])
    for spine in axis.spines.values():
        spine.set_color("#475569")
    save(fig, "expression-controls.png")


if __name__ == "__main__":
    waveform_gallery()
    adsr_envelope()
    signal_flow()
    scale_map()
    expression_controls()
