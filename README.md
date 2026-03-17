# chordo

Tkinter chord sequencer experiments for macOS, using `pygame` for audio synthesis.

This project is still a work in progress. Please use GitHub on this repository for suggestions, comments, bug reports, and improvement ideas.

## Features

- 8-slot chord bank with per-slot editing and color-coded selection
- 16-step sequencer for sketching progressions and playback patterns
- Large built-in scale library including major, minor, modes, pentatonics, blues, whole tone, altered, and harmonic/melodic minor variants
- Large built-in chord formula library including triads, sevenths, extensions, suspended chords, altered dominants, and power chords
- Chord editor with:
  root note selection
  octave control
  slash bass selection
  24-step interval matrix across two octaves
  preset chord buttons and custom interval editing
- Smart enharmonic note display that favors flats in flat keys
- Per-step rhythm lengths for longer held chords in the sequence
- Save/load support for progression presets via JSON
- Pygame-generated synthesized playback rather than external samples

## Files

- `chordo-v2.py`: tracked app script in this repository
- `update_chordo.py`: simple Tk-based GitHub updater for this repo

## Run

Install dependencies:

```bash
python3 -m pip install pygame numpy
```

Start the app:

```bash
python3 chordo-v2.py
```

Update GitHub from a prompt:

```bash
python3 update_chordo.py
```

Update GitHub with a message passed on the command line:

```bash
python3 update_chordo.py "Describe your changes"
```

## Notes for macOS

- The app uses `tkinter`, which ships with Python on many macOS installs but may require the official Python.org build if your local Python lacks Tk support.
- `pygame` audio initialization depends on an available output device.
- The current app is a script, not a packaged `.app`.
- `chordo-gem.py` is intentionally ignored by Git and kept as a local variant.
