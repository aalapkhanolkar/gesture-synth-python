# Gesture Synth Python

A webcam-driven software synthesizer built in Python. Hold up one, two, or three fingers and the app plays configurable synthesized notes in real time.

This project is inspired by the browser-based reference at <https://gesture-synth-weld.vercel.app/> and is designed as a clean Python portfolio repo that runs from VS Code, a standard terminal, or a Jupyter notebook.

## Demo

Add your demo media here after recording:

- GIF demo: `assets/screenshots/demo.gif`
- Screenshot: `assets/screenshots/main-window.png`
- YouTube or demo video: `https://...`

## Features

- Realtime webcam hand tracking with MediaPipe Hands
- Finger-count gestures for one hand
- Debounced gesture state so notes do not retrigger every frame
- Continuous audio stream with a real oscillator, not prerecorded files
- Sine, square, sawtooth, and triangle waveforms
- ADSR envelope with attack, decay, sustain, and release
- Portamento-style frequency glide to reduce clicks when changing notes
- OpenCV camera overlay with landmarks, gesture, note, frequency, waveform, stability, and FPS
- JSON configuration for camera, synth, gesture stabilization, and gesture-to-note mapping
- Tests for gesture stabilization, finger counting, and synth rendering
- Jupyter notebook for waveform and hand-tracking experiments

## Gesture Mapping

Default notes are configured in `config.json`:

| Gesture | Note | Frequency |
| --- | --- | --- |
| 1 finger | C4 | 261.63 Hz |
| 2 fingers | E4 | 329.63 Hz |
| 3 fingers | G4 | 392.00 Hz |

Unsupported gestures, including no hand or an unmapped finger count, smoothly release the active note.

## Project Structure

```text
gesture-synth-python/
├── assets/
│   └── screenshots/
├── notebooks/
│   └── gesture_synth_experiments.ipynb
├── src/
│   ├── camera.py
│   ├── config.py
│   ├── gesture_detector.py
│   ├── hand_tracker.py
│   ├── synth.py
│   └── ui.py
├── tests/
│   ├── test_gesture_detector.py
│   └── test_synth.py
├── config.json
├── main.py
├── requirements.txt
└── README.md
```

## Setup

Python 3.9 through 3.11 is recommended. On Windows, use the VS Code terminal or PowerShell.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Activate it on Windows Command Prompt:

```bat
.\.venv\Scripts\activate.bat
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Run

Start the full webcam and audio app:

```bash
python main.py
```

Run the camera and gesture UI without audio:

```bash
python main.py --no-audio
```

Use a different config file:

```bash
python main.py --config path/to/config.json
```

Press `Q` or `Esc` in the OpenCV window to quit.

## Configuration

Edit `config.json` to change:

- `camera.index`, `camera.backend`, `camera.width`, `camera.height`, and `camera.fps`
- `gesture.stable_frames`
- MediaPipe confidence thresholds
- `synth.waveform`, `synth.amplitude`, ADSR values, and portamento
- `gesture_notes` for different notes, scales, or chords later

Example waveform options:

```json
"waveform": "triangle"
```

Example gesture extension:

```json
"4": {
  "name": "C5",
  "frequency": 523.25
}
```

## Architecture

`main.py` coordinates the realtime loop:

1. `Camera` reads frames from OpenCV.
2. `HandTracker` detects MediaPipe hand landmarks.
3. `count_extended_fingers` estimates the raw finger count.
4. `GestureStabilizer` debounces noisy detections.
5. `Synthesizer` starts, releases, or glides notes without recreating the audio engine.
6. `draw_overlay` renders the status panel and FPS.

The synth is monophonic for the MVP, but the modules are separated so future two-hand control can be added without rewriting the camera, gesture, or oscillator layers.

## Jupyter Notebook

Launch Jupyter:

```bash
jupyter notebook
```

Open:

```text
notebooks/gesture_synth_experiments.ipynb
```

The notebook includes waveform visualization and a webcam landmark debugging loop.

## Tests

Run:

```bash
pytest
```

The tests avoid requiring a real webcam or speaker, so they are useful for quick validation in CI or before pushing to GitHub.

## Troubleshooting

If the camera does not open, change `camera.index` in `config.json` from `0` to `1` or another available camera index. On Windows, `camera.backend` defaults to DirectShow through `auto`; if your webcam prefers another backend, try `"msmf"` or `"any"`.

If the OpenCV window appears but no hand is detected, improve lighting, keep your hand fully in frame, and try raising or lowering `gesture.min_detection_confidence`.

If audio does not play, confirm your default output device works and that `sounddevice` installed correctly. You can still test gestures with:

```bash
python main.py --no-audio
```

If dependency installation fails on a newer Python version, create the virtual environment with Python 3.9, 3.10, or 3.11 because MediaPipe wheels are version-specific.

## Future Improvements

- Add 4- and 5-finger mappings
- Add chords and scale modes
- Use hand height for volume
- Use hand position for pitch bend, filter cutoff, vibrato, or waveform selection
- Add two-hand controls
- Add a low-pass filter, delay, or reverb
- Add MIDI output
- Record performances to WAV
- Build a graphical synth panel beside the webcam feed

## Git And GitHub

This workspace is already initialized as a Git repository. For a new clone, these are the usual commands:

```bash
git init
git add .
git commit -m "Initial gesture synth project"
```

Create an empty repository on GitHub, then push with your own repository URL:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git branch -M main
git push -u origin main
```
