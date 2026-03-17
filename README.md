# chordo

Tkinter chord sequencer experiments for macOS, using `pygame` for audio synthesis.

## Files

- `chordo-gem.py`: current mac-oriented version
- `chordo-v2.py`: alternate script version kept in the repo

## Run

Install dependencies:

```bash
python3 -m pip install pygame numpy
```

Start the app:

```bash
python3 chordo-gem.py
```

## Notes for macOS

- The app uses `tkinter`, which ships with Python on many macOS installs but may require the official Python.org build if your local Python lacks Tk support.
- `pygame` audio initialization depends on an available output device.
- The current app is a script, not a packaged `.app`.
