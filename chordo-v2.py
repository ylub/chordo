import math
import os
import struct
import sys
import tempfile
import wave
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

TRIADS = {
    "Major": [0, 4, 7],
    "Minor": [0, 3, 7],
    "Diminished": [0, 3, 6],
    "Augmented": [0, 4, 8],
    "Sus2": [0, 2, 7],
    "Sus4": [0, 5, 7],
    "Power (5)": [0, 7],
}

EXTENSIONS = {
    "6": 9,
    "7": 10,
    "Maj7": 11,
    "Dim7": 9,
    "9": 14,
    "11": 17,
    "13": 21,
}

ALTERATIONS = ["b5", "#5", "b9", "#9", "#11", "b13"]

SCALES = {
    "Major (Ionian)": [0, 2, 4, 5, 7, 9, 11],
    "Natural Minor (Aeolian)": [0, 2, 3, 5, 7, 8, 10],
    "Harmonic Minor": [0, 2, 3, 5, 7, 8, 11],
    "Melodic Minor": [0, 2, 3, 5, 7, 9, 11],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Phrygian": [0, 1, 3, 5, 7, 8, 10],
    "Lydian": [0, 2, 4, 6, 7, 9, 11],
    "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "Locrian": [0, 1, 3, 5, 6, 8, 10],
}

DEFAULT_TEMPO_BPM = 120

KEY_SIGNATURES = {
    # Major keys
    ("C", "Major"): 0,
    ("G", "Major"): 1,
    ("D", "Major"): 2,
    ("A", "Major"): 3,
    ("E", "Major"): 4,
    ("B", "Major"): 5,
    ("F#", "Major"): 6,
    ("C#", "Major"): 7,
    ("F", "Major"): -1,
    ("Bb", "Major"): -2,
    ("Eb", "Major"): -3,
    ("Ab", "Major"): -4,
    ("Db", "Major"): -5,
    ("Gb", "Major"): -6,
    ("Cb", "Major"): -7,
    # Minor keys
    ("A", "Minor"): 0,
    ("E", "Minor"): 1,
    ("B", "Minor"): 2,
    ("F#", "Minor"): 3,
    ("C#", "Minor"): 4,
    ("G#", "Minor"): 5,
    ("D#", "Minor"): 6,
    ("A#", "Minor"): 7,
    ("D", "Minor"): -1,
    ("G", "Minor"): -2,
    ("C", "Minor"): -3,
    ("F", "Minor"): -4,
    ("Bb", "Minor"): -5,
    ("Eb", "Minor"): -6,
    ("Ab", "Minor"): -7,
}


def midi_note_for(root_index: int, octave: int) -> int:
    return (octave + 1) * 12 + root_index


def apply_alterations(intervals, alterations):
    out = set(intervals)

    def replace_interval(old, new):
        if old in out:
            out.remove(old)
        out.add(new)

    if "b5" in alterations:
        replace_interval(7, 6)
        replace_interval(8, 6)
    if "#5" in alterations:
        replace_interval(7, 8)
        replace_interval(6, 8)
    if "b9" in alterations:
        replace_interval(14, 13)
    if "#9" in alterations:
        replace_interval(14, 15)
    if "#11" in alterations:
        replace_interval(17, 18)
    if "b13" in alterations:
        replace_interval(21, 20)

    return sorted(out)


def apply_voicing(notes, voicing):
    if not notes:
        return notes

    notes = sorted(notes)

    if voicing == "Close":
        return notes

    if voicing == "Open":
        spread = []
        for idx, n in enumerate(notes):
            spread.append(n + (12 if idx % 2 == 1 else 0))
        return sorted(spread)

    if voicing == "Drop 2" and len(notes) >= 3:
        notes = notes[:]
        notes[-2] -= 12
        return sorted(notes)

    if voicing == "Drop 3" and len(notes) >= 4:
        notes = notes[:]
        notes[-3] -= 12
        return sorted(notes)

    if voicing == "Spread":
        spread = []
        for idx, n in enumerate(notes):
            spread.append(n + (12 * (idx // 2)))
        return sorted(spread)

    return notes


def apply_inversion(notes, inversion):
    notes = sorted(notes)
    for _ in range(inversion):
        if notes:
            n = notes.pop(0)
            notes.append(n + 12)
    return sorted(notes)


def build_chord(
    root_index,
    octave,
    triad_name,
    ext_flags,
    alt_flags,
    max_notes,
    voicing,
    inversion,
    extra_intervals,
    octave_shift=0,
    extra_abs_notes=None,
):
    intervals = list(TRIADS[triad_name])

    for name, semis in EXTENSIONS.items():
        if ext_flags.get(name):
            intervals.append(semis)

    intervals.extend(extra_intervals)
    intervals = apply_alterations(intervals, {k for k, v in alt_flags.items() if v})
    intervals = sorted(set(intervals))

    # Always include root, then prioritize 3rd/5th, then extensions
    priority = []
    for base in TRIADS[triad_name]:
        if base in intervals:
            priority.append(base)

    extensions_sorted = [i for i in intervals if i not in priority]
    intervals = priority + extensions_sorted

    if max_notes and len(intervals) > max_notes:
        intervals = intervals[:max_notes]

    base_midi = midi_note_for(root_index, octave + octave_shift)
    notes = [base_midi + i for i in intervals]

    notes = apply_voicing(notes, voicing)
    notes = apply_inversion(notes, inversion)

    if extra_abs_notes:
        notes = sorted(set(notes + list(extra_abs_notes)))
    else:
        notes = sorted(notes)

    return notes


def note_name(index, prefer_flats=False):
    return (NOTE_NAMES_FLAT if prefer_flats else NOTE_NAMES_SHARP)[index % 12]


def note_index(name):
    if name in NOTE_NAMES_SHARP:
        return NOTE_NAMES_SHARP.index(name)
    if name in NOTE_NAMES_FLAT:
        return NOTE_NAMES_FLAT.index(name)
    return 0


def note_label_for_midi(midi_note):
    return note_name(midi_note % 12) + str((midi_note // 12) - 1)


def parse_note_label(label):
    label = label.strip()
    if len(label) < 2:
        return None
    name = label[:-1]
    octave_str = label[-1]
    if len(label) >= 3 and (label[-2] == "-" or label[-2].isdigit()):
        name = label[:-2]
        octave_str = label[-2:]
    try:
        octave = int(octave_str)
    except ValueError:
        return None
    idx = note_index(name)
    return midi_note_for(idx, octave)


def key_from_signature(sf, is_minor):
    for (root, mode), value in KEY_SIGNATURES.items():
        if value == sf and ((mode == "Minor") == bool(is_minor)):
            return root, mode
    return None


def read_vlq(data, idx):
    value = 0
    while idx < len(data):
        b = data[idx]
        idx += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return value, idx


def parse_midi_file(path):
    with open(path, "rb") as f:
        header = f.read(14)
        if len(header) < 14 or header[:4] != b"MThd":
            raise ValueError("Invalid MIDI header.")
        header_len = struct.unpack(">I", header[4:8])[0]
        fmt, tracks, division = struct.unpack(">HHH", header[8:14])
        if header_len > 6:
            f.read(header_len - 6)

        ticks_per_beat = division
        tempo = None
        key_sig = None
        note_events = []

        for _ in range(tracks):
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id = chunk_header[:4]
            chunk_len = struct.unpack(">I", chunk_header[4:8])[0]
            data = f.read(chunk_len)
            if chunk_id != b"MTrk":
                continue

            idx = 0
            time = 0
            running_status = None
            while idx < len(data):
                delta, idx = read_vlq(data, idx)
                time += delta
                if idx >= len(data):
                    break
                status = data[idx]
                if status < 0x80:
                    if running_status is None:
                        break
                    status = running_status
                else:
                    idx += 1
                    running_status = status

                if status == 0xFF:
                    if idx >= len(data):
                        break
                    meta_type = data[idx]
                    idx += 1
                    length, idx = read_vlq(data, idx)
                    meta_data = data[idx : idx + length]
                    idx += length
                    if meta_type == 0x51 and length == 3:
                        tempo = int.from_bytes(meta_data, "big")
                    elif meta_type == 0x59 and length >= 2:
                        sf = struct.unpack("b", meta_data[:1])[0]
                        is_minor = meta_data[1]
                        key_sig = (sf, is_minor)
                elif status in (0xF0, 0xF7):
                    length, idx = read_vlq(data, idx)
                    idx += length
                else:
                    event_type = status & 0xF0
                    if event_type in (0x80, 0x90):
                        if idx + 2 > len(data):
                            break
                        note = data[idx]
                        vel = data[idx + 1]
                        idx += 2
                        if event_type == 0x90 and vel > 0:
                            note_events.append((time, "on", note))
                        else:
                            note_events.append((time, "off", note))
                    elif event_type in (0xA0, 0xB0, 0xE0):
                        idx += 2
                    elif event_type in (0xC0, 0xD0):
                        idx += 1
                    else:
                        break

        note_events.sort(key=lambda x: x[0])
        active = {}
        intervals = []
        for t, typ, note in note_events:
            if typ == "on":
                active.setdefault(note, []).append(t)
            else:
                if note in active and active[note]:
                    start = active[note].pop(0)
                    intervals.append((start, t, note))

        by_start = {}
        for start, end, note in intervals:
            by_start.setdefault(start, []).append((note, end))

        chord_events = []
        for start in sorted(by_start.keys()):
            notes_with_end = by_start[start]
            notes = [n for n, _ in notes_with_end]
            duration = max(e for _, e in notes_with_end) - start
            chord_events.append((notes, duration))

        tempo_bpm = None
        if tempo:
            tempo_bpm = int(round(60_000_000 / tempo))

        return chord_events, ticks_per_beat, tempo_bpm, key_sig


def analyze_chord_notes(notes):
    if not notes:
        return 0, "Major", {name: False for name in EXTENSIONS}, {name: False for name in ALTERATIONS}, []
    root_midi = min(notes)
    root_index = root_midi % 12
    intervals = sorted(set(n - root_midi for n in notes))
    intervals_mod = {i % 12 for i in intervals}

    if 4 in intervals_mod and 7 in intervals_mod:
        triad_name = "Major"
        triad_intervals = {0, 4, 7}
    elif 3 in intervals_mod and 7 in intervals_mod:
        triad_name = "Minor"
        triad_intervals = {0, 3, 7}
    elif 3 in intervals_mod and 6 in intervals_mod:
        triad_name = "Diminished"
        triad_intervals = {0, 3, 6}
    elif 4 in intervals_mod and 8 in intervals_mod:
        triad_name = "Augmented"
        triad_intervals = {0, 4, 8}
    elif 2 in intervals_mod and 7 in intervals_mod:
        triad_name = "Sus2"
        triad_intervals = {0, 2, 7}
    elif 5 in intervals_mod and 7 in intervals_mod:
        triad_name = "Sus4"
        triad_intervals = {0, 5, 7}
    else:
        triad_name = "Major"
        triad_intervals = {0, 4, 7}

    ext_flags = {name: False for name in EXTENSIONS}
    alt_flags = {name: False for name in ALTERATIONS}

    if 11 in intervals_mod:
        ext_flags["Maj7"] = True
    elif 10 in intervals_mod:
        ext_flags["7"] = True
    elif 9 in intervals_mod:
        if triad_name == "Diminished":
            ext_flags["Dim7"] = True
        else:
            ext_flags["6"] = True

    if 14 in intervals:
        ext_flags["9"] = True
    if 17 in intervals:
        ext_flags["11"] = True
    if 21 in intervals:
        ext_flags["13"] = True

    if 6 in intervals_mod:
        alt_flags["b5"] = True
    if 8 in intervals_mod:
        alt_flags["#5"] = True
    if 13 in intervals:
        alt_flags["b9"] = True
    if 15 in intervals:
        alt_flags["#9"] = True
    if 18 in intervals:
        alt_flags["#11"] = True
    if 20 in intervals:
        alt_flags["b13"] = True

    used = set(triad_intervals)
    if ext_flags["6"]:
        used.add(9)
    if ext_flags["7"]:
        used.add(10)
    if ext_flags["Maj7"]:
        used.add(11)
    if ext_flags["Dim7"]:
        used.add(9)
    if ext_flags["9"]:
        used.add(14)
    if ext_flags["11"]:
        used.add(17)
    if ext_flags["13"]:
        used.add(21)
    if alt_flags["b5"]:
        used.add(6)
    if alt_flags["#5"]:
        used.add(8)
    if alt_flags["b9"]:
        used.add(13)
    if alt_flags["#9"]:
        used.add(15)
    if alt_flags["#11"]:
        used.add(18)
    if alt_flags["b13"]:
        used.add(20)

    extra_intervals = [i for i in intervals if i not in used and i != 0]

    return root_index, triad_name, ext_flags, alt_flags, extra_intervals


def key_signature_info(key_root_name, key_mode):
    sf = KEY_SIGNATURES.get((key_root_name, key_mode), 0)
    is_minor = 1 if key_mode == "Minor" else 0
    return sf, is_minor


def scale_degrees_for_mode(key_mode):
    if key_mode == "Minor":
        return [0, 2, 3, 5, 7, 8, 10]
    return [0, 2, 4, 5, 7, 9, 11]


def roman_for_degree(degree, quality):
    numerals = ["I", "II", "III", "IV", "V", "VI", "VII"]
    base = numerals[degree]
    if quality in ("Minor", "Diminished"):
        base = base.lower()
    if quality == "Diminished":
        base += "o"
    if quality == "Augmented":
        base += "+"
    return base


def roman_chord_label(root_index, triad_name, ext_flags, alt_flags, key_root_index, key_mode, extra_intervals=None, extra_abs_notes=None):
    degrees = scale_degrees_for_mode(key_mode)
    dist = (root_index - key_root_index) % 12
    accidental = ""
    degree = None
    if dist in degrees:
        degree = degrees.index(dist)
    else:
        for idx, d in enumerate(degrees):
            if (d - 1) % 12 == dist:
                degree = idx
                accidental = "b"
                break
            if (d + 1) % 12 == dist:
                degree = idx
                accidental = "#"
                break

    if degree is None:
        base = "?"
    else:
        base = accidental + roman_for_degree(degree, triad_name)

    if triad_name in ("Sus2", "Sus4"):
        base += triad_name.lower()
    elif triad_name == "Power (5)":
        base += "5"

    for name in ["6", "7", "Maj7", "Dim7", "9", "11", "13"]:
        if ext_flags.get(name):
            base += name

    for name in ALTERATIONS:
        if alt_flags.get(name):
            base += name

    if extra_intervals:
        base += "(+" + ",".join(str(i) for i in extra_intervals) + ")"
    if extra_abs_notes:
        names = ",".join(note_label_for_midi(n) for n in extra_abs_notes)
        base += "(+" + names + ")"

    return base


def chord_label(root_index, triad_name, ext_flags, alt_flags, extra_intervals, extra_abs_notes=None):
    parts = [note_name(root_index)]
    if triad_name == "Minor":
        parts.append("m")
    elif triad_name == "Diminished":
        parts.append("dim")
    elif triad_name == "Augmented":
        parts.append("aug")
    elif triad_name == "Sus2":
        parts.append("sus2")
    elif triad_name == "Sus4":
        parts.append("sus4")
    elif triad_name == "Power (5)":
        parts.append("5")

    for name in ["6", "7", "Maj7", "Dim7", "9", "11", "13"]:
        if ext_flags.get(name):
            parts.append(name)

    for name in ALTERATIONS:
        if alt_flags.get(name):
            parts.append(name)

    if extra_intervals:
        parts.append("(+" + ",".join(str(i) for i in extra_intervals) + ")")
    if extra_abs_notes:
        parts.append("(+" + ",".join(note_label_for_midi(n) for n in extra_abs_notes) + ")")

    return "".join(parts)


def write_midi(path, notes, tempo_bpm=DEFAULT_TEMPO_BPM, duration_beats=2, velocity=90, key_signature=None):
    # Standard MIDI file format 1 track, type 0
    ticks_per_beat = 480
    tempo = int(60_000_000 / tempo_bpm)
    events = []

    def vlq(n):
        bytes_out = []
        bytes_out.append(n & 0x7F)
        n >>= 7
        while n:
            bytes_out.append(0x80 | (n & 0x7F))
            n >>= 7
        return bytes(reversed(bytes_out))

    # Tempo meta event at time 0
    events.append(vlq(0) + bytes([0xFF, 0x51, 0x03]) + tempo.to_bytes(3, "big"))

    if key_signature is not None:
        sf, is_minor = key_signature
        sf_byte = sf & 0xFF
        events.append(vlq(0) + bytes([0xFF, 0x59, 0x02, sf_byte, is_minor & 0xFF]))

    # Program change at time 0 (acoustic grand)
    events.append(vlq(0) + bytes([0xC0, 0x00]))

    # Note on
    for n in notes:
        events.append(vlq(0) + bytes([0x90, n & 0x7F, velocity & 0x7F]))

    # Note off after duration
    delta = int(duration_beats * ticks_per_beat)
    for idx, n in enumerate(notes):
        events.append(vlq(delta if idx == 0 else 0) + bytes([0x80, n & 0x7F, 0x00]))

    # End of track
    events.append(vlq(0) + bytes([0xFF, 0x2F, 0x00]))

    track_data = b"".join(events)
    track_header = b"MTrk" + struct.pack(">I", len(track_data))

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks_per_beat)

    with open(path, "wb") as f:
        f.write(header)
        f.write(track_header)
        f.write(track_data)


def write_midi_sequence(path, chord_events, tempo_bpm=DEFAULT_TEMPO_BPM, velocity=90, key_signature=None):
    ticks_per_beat = 480
    tempo = int(60_000_000 / tempo_bpm)
    events = []

    def vlq(n):
        bytes_out = []
        bytes_out.append(n & 0x7F)
        n >>= 7
        while n:
            bytes_out.append(0x80 | (n & 0x7F))
            n >>= 7
        return bytes(reversed(bytes_out))

    events.append(vlq(0) + bytes([0xFF, 0x51, 0x03]) + tempo.to_bytes(3, "big"))
    if key_signature is not None:
        sf, is_minor = key_signature
        sf_byte = sf & 0xFF
        events.append(vlq(0) + bytes([0xFF, 0x59, 0x02, sf_byte, is_minor & 0xFF]))
    events.append(vlq(0) + bytes([0xC0, 0x00]))

    time_accum = 0
    for notes, duration_beats in chord_events:
        delta = int(duration_beats * ticks_per_beat)
        if not notes:
            time_accum += delta
            continue

        events.append(vlq(time_accum) + bytes([0x90, notes[0] & 0x7F, velocity & 0x7F]))
        for n in notes[1:]:
            events.append(vlq(0) + bytes([0x90, n & 0x7F, velocity & 0x7F]))

        for idx, n in enumerate(notes):
            events.append(vlq(delta if idx == 0 else 0) + bytes([0x80, n & 0x7F, 0x00]))

        time_accum = 0

    events.append(vlq(0) + bytes([0xFF, 0x2F, 0x00]))

    track_data = b"".join(events)
    track_header = b"MTrk" + struct.pack(">I", len(track_data))
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks_per_beat)

    with open(path, "wb") as f:
        f.write(header)
        f.write(track_header)
        f.write(track_data)


def generate_wav(notes, sample_rate=44100, duration=1.5, arpeggio=False):
    num_samples = int(sample_rate * duration)
    data = [0.0] * num_samples

    if not notes:
        return b"", sample_rate

    def midi_to_freq(n):
        return 440.0 * (2 ** ((n - 69) / 12))

    if arpeggio:
        step = max(1, num_samples // max(1, len(notes)))
        for i, n in enumerate(notes):
            freq = midi_to_freq(n)
            start = i * step
            end = min(num_samples, (i + 1) * step)
            for t in range(start, end):
                data[t] += math.sin(2 * math.pi * freq * (t / sample_rate))
    else:
        for n in notes:
            freq = midi_to_freq(n)
            for t in range(num_samples):
                data[t] += math.sin(2 * math.pi * freq * (t / sample_rate))

    max_amp = max(abs(x) for x in data) or 1.0
    scale = 0.6 / max_amp
    frames = bytearray()
    for x in data:
        val = int(max(-1.0, min(1.0, x * scale)) * 32767)
        frames += struct.pack("<h", val)

    return bytes(frames), sample_rate


def play_wav_bytes(wav_bytes, sample_rate):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        path = tmp.name
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(wav_bytes)

    try:
        if sys.platform.startswith("win"):
            import winsound

            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["aplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        messagebox.showwarning("Preview", "Could not play audio on this system.")


def triad_quality(intervals):
    triad = sorted(intervals[:3])
    if triad == [0, 4, 7]:
        return "Major"
    if triad == [0, 3, 7]:
        return "Minor"
    if triad == [0, 3, 6]:
        return "Diminished"
    if triad == [0, 4, 8]:
        return "Augmented"
    if triad == [0, 2, 7]:
        return "Sus2"
    if triad == [0, 5, 7]:
        return "Sus4"
    return "Major"


def seventh_quality(intervals):
    triad = sorted(intervals[:3])
    seventh = sorted(intervals[:4])
    if seventh == [0, 4, 7, 11]:
        return "Maj7"
    if seventh == [0, 4, 7, 10]:
        return "7"
    if seventh == [0, 3, 7, 10]:
        return "7"
    if seventh == [0, 3, 6, 10]:
        return "7"
    if seventh == [0, 3, 6, 9]:
        return "Dim7"
    if triad == [0, 3, 7]:
        return "7"
    return "7"


def build_scale_chords(scale_intervals):
    chords = []
    for degree in range(7):
        root = scale_intervals[degree]
        third = scale_intervals[(degree + 2) % 7]
        fifth = scale_intervals[(degree + 4) % 7]
        seventh = scale_intervals[(degree + 6) % 7]
        triad = sorted([(third - root) % 12, (fifth - root) % 12])
        triad = [0] + triad
        seventh_interval = (seventh - root) % 12
        chord_intervals = sorted(set(triad + [seventh_interval]))
        chords.append((root, triad, chord_intervals))
    return chords


def build_ui(root):
    root.title("Chordo-v2 - Chord Builder")
    root.geometry("960x640")
    root.minsize(900, 620)

    palette = {
        "bg": "#f3efe6",
        "panel": "#fbf7ef",
        "accent": "#6a4b2b",
        "accent2": "#b08b5a",
        "muted": "#8b775a",
        "ink": "#2a1f16",
    }

    root.configure(bg=palette["bg"])

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TFrame", background=palette["bg"])
    style.configure("Panel.TFrame", background=palette["panel"])
    style.configure("TLabel", background=palette["panel"], foreground=palette["ink"])
    style.configure("Title.TLabel", background=palette["bg"], foreground=palette["accent"], font=("Georgia", 16, "bold"))
    style.configure("Sub.TLabel", background=palette["bg"], foreground=palette["muted"], font=("Georgia", 10))
    style.configure("TLabelframe", background=palette["panel"], foreground=palette["accent"])
    style.configure("TLabelframe.Label", background=palette["panel"], foreground=palette["accent"], font=("Georgia", 10, "bold"))
    style.configure("TButton", background=palette["panel"], foreground=palette["ink"], padding=(6, 3))
    style.map("TButton", background=[("active", palette["accent2"])], foreground=[("active", palette["ink"])])
    style.configure("TCheckbutton", background=palette["panel"], foreground=palette["ink"])
    style.configure("TRadiobutton", background=palette["panel"], foreground=palette["ink"])
    style.configure("TCombobox", fieldbackground=palette["panel"], background=palette["panel"], foreground=palette["ink"])
    style.configure("TSpinbox", fieldbackground=palette["panel"], background=palette["panel"], foreground=palette["ink"])
    style.configure("Treeview", background=palette["panel"], fieldbackground=palette["panel"], foreground=palette["ink"], rowheight=20)
    style.configure("Treeview.Heading", background=palette["accent2"], foreground=palette["ink"], font=("Georgia", 9, "bold"))
    style.configure("TNotebook", background=palette["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=palette["panel"], foreground=palette["ink"], padding=(10, 4))
    style.map("TNotebook.Tab", background=[("selected", palette["accent2"])], foreground=[("selected", palette["ink"])])

    main = ttk.Frame(root, padding=6, style="Panel.TFrame")
    main.pack(fill="both", expand=True)

    header = ttk.Frame(main, style="Panel.TFrame")
    header.pack(fill="x", pady=(0, 4))
    ttk.Label(header, text="Chordo-v2", style="Title.TLabel").pack(side="left")
    ttk.Label(header, text="Compact chord workshop", style="Sub.TLabel").pack(side="left", padx=(10, 0))

    notebook = ttk.Notebook(main)
    notebook.pack(fill="both", expand=True)

    # Shared state for chord builder
    root_var = tk.StringVar(value="C")
    octave_var = tk.IntVar(value=4)
    octave_shift_var = tk.IntVar(value=0)
    triad_var = tk.StringVar(value="Major")

    ext_vars = {name: tk.BooleanVar(value=False) for name in ["6", "7", "Maj7", "Dim7", "9", "11", "13"]}
    alt_vars = {name: tk.BooleanVar(value=False) for name in ALTERATIONS}

    key_root_var = tk.StringVar(value="C")
    key_mode_var = tk.StringVar(value="Major")
    display_mode_var = tk.StringVar(value="Note Names")

    voicing_var = tk.StringVar(value="Close")
    inversion_var = tk.IntVar(value=0)
    max_notes_var = tk.IntVar(value=6)
    tempo_var = tk.IntVar(value=DEFAULT_TEMPO_BPM)
    duration_var = tk.DoubleVar(value=2.0)
    velocity_var = tk.IntVar(value=90)
    arpeggio_var = tk.BooleanVar(value=False)

    extra_intervals = []
    extra_abs_notes = []

    def open_modifier_window(title, octave_var, octave_shift_var, inversion_var, voicing_var, max_notes_var, extra_intervals_list, extra_notes_list, on_change):
        win = tk.Toplevel(root)
        win.title(title)
        win.geometry("420x430")
        win.resizable(False, False)
        win.configure(bg=palette["bg"])

        layout = ttk.Frame(win, padding=10, style="Panel.TFrame")
        layout.pack(fill="both", expand=True)

        basic = ttk.LabelFrame(layout, text="Octaves & Voicing", padding=8)
        basic.pack(fill="x", pady=(0, 8))

        ttk.Label(basic, text="Octave").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(basic, from_=0, to=8, textvariable=octave_var, width=6).grid(row=0, column=1, sticky="w")

        ttk.Label(basic, text="Octave Shift").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(basic, from_=-2, to=2, textvariable=octave_shift_var, width=6).grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(basic, text="Inversion").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(basic, from_=0, to=4, textvariable=inversion_var, width=6).grid(row=2, column=1, sticky="w", pady=(6, 0))

        ttk.Label(basic, text="Voicing").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(basic, textvariable=voicing_var, values=["Close", "Open", "Drop 2", "Drop 3", "Spread"], state="readonly", width=10).grid(row=3, column=1, sticky="w", pady=(6, 0))

        ttk.Label(basic, text="Max Notes").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(basic, from_=1, to=8, textvariable=max_notes_var, width=6).grid(row=4, column=1, sticky="w", pady=(6, 0))

        extras = ttk.LabelFrame(layout, text="Extra Intervals (semitones)", padding=8)
        extras.pack(fill="x", pady=(0, 8))

        extra_list = tk.Listbox(extras, height=4, bg=palette["panel"], fg=palette["ink"], highlightthickness=1, highlightbackground=palette["accent2"])
        extra_list.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8))
        for val in extra_intervals_list:
            extra_list.insert("end", str(val))

        extra_entry = ttk.Entry(extras, width=8)
        extra_entry.grid(row=0, column=1, sticky="w")

        def add_extra():
            try:
                val = int(extra_entry.get())
            except ValueError:
                return
            if val < -24 or val > 36:
                return
            if val not in extra_intervals_list:
                extra_intervals_list.append(val)
                extra_intervals_list.sort()
                extra_list.insert("end", str(val))
                on_change()

        def remove_extra():
            sel = list(extra_list.curselection())
            if not sel:
                return
            for idx in reversed(sel):
                val = int(extra_list.get(idx))
                extra_list.delete(idx)
                if val in extra_intervals_list:
                    extra_intervals_list.remove(val)
            on_change()

        ttk.Button(extras, text="Add", command=add_extra).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Button(extras, text="Remove", command=remove_extra).grid(row=2, column=1, sticky="w", pady=(6, 0))

        quick = ttk.Frame(extras)
        quick.grid(row=0, column=2, rowspan=3, sticky="n", padx=(6, 0))

        def add_quick(val):
            if val not in extra_intervals_list:
                extra_intervals_list.append(val)
                extra_intervals_list.sort()
                extra_list.insert("end", str(val))
                on_change()

        ttk.Button(quick, text="+8ve", width=6, command=lambda: add_quick(12)).pack(pady=2)
        ttk.Button(quick, text="-8ve", width=6, command=lambda: add_quick(-12)).pack(pady=2)
        ttk.Button(quick, text="+15th", width=6, command=lambda: add_quick(24)).pack(pady=2)

        notes = ttk.LabelFrame(layout, text="Extra Notes (absolute)", padding=8)
        notes.pack(fill="x")

        notes_list = tk.Listbox(notes, height=4, bg=palette["panel"], fg=palette["ink"], highlightthickness=1, highlightbackground=palette["accent2"])
        notes_list.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8))
        for n in extra_notes_list:
            notes_list.insert("end", note_label_for_midi(n))

        note_name_var = tk.StringVar(value="C")
        note_octave_var = tk.IntVar(value=4)

        ttk.Combobox(notes, textvariable=note_name_var, values=NOTE_NAMES_SHARP, state="readonly", width=6).grid(row=0, column=1, sticky="w")
        ttk.Spinbox(notes, from_=0, to=8, textvariable=note_octave_var, width=6).grid(row=0, column=2, sticky="w", padx=(6, 0))

        def add_note():
            midi = midi_note_for(note_index(note_name_var.get()), note_octave_var.get())
            if midi not in extra_notes_list:
                extra_notes_list.append(midi)
                extra_notes_list.sort()
                notes_list.insert("end", note_label_for_midi(midi))
                on_change()

        def remove_note():
            sel = list(notes_list.curselection())
            if not sel:
                return
            for idx in reversed(sel):
                label = notes_list.get(idx)
                midi = parse_note_label(label)
                notes_list.delete(idx)
                if midi in extra_notes_list:
                    extra_notes_list.remove(midi)
            on_change()

        ttk.Button(notes, text="Add", command=add_note).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Button(notes, text="Remove", command=remove_note).grid(row=2, column=1, sticky="w", pady=(6, 0))

    def current_notes():
        root_index = NOTE_NAMES_SHARP.index(root_var.get())
        notes = build_chord(
            root_index,
            octave_var.get(),
            triad_var.get(),
            {k: v.get() for k, v in ext_vars.items()},
            {k: v.get() for k, v in alt_vars.items()},
            max_notes_var.get(),
            voicing_var.get(),
            inversion_var.get(),
            extra_intervals,
            octave_shift_var.get(),
            list(extra_abs_notes),
        )
        return root_index, notes

    def display_chord_name(root_index):
        if display_mode_var.get() == "Roman Numerals":
            key_root_index = note_index(key_root_var.get())
            return roman_chord_label(
                root_index,
                triad_var.get(),
                {k: v.get() for k, v in ext_vars.items()},
                {k: v.get() for k, v in alt_vars.items()},
                key_root_index,
                key_mode_var.get(),
                list(extra_intervals),
                list(extra_abs_notes),
            )
        return chord_label(
            root_index,
            triad_var.get(),
            {k: v.get() for k, v in ext_vars.items()},
            {k: v.get() for k, v in alt_vars.items()},
            list(extra_intervals),
            list(extra_abs_notes),
        )

    def refresh_display(*_):
        root_index, notes = current_notes()
        name = display_chord_name(root_index)
        note_names = [note_label_for_midi(n) for n in notes]
        chord_name_var.set(name)
        chord_notes_var.set(", ".join(note_names) if note_names else "")

    def preview_single():
        _, notes = current_notes()
        wav_bytes, sr = generate_wav(notes, duration=1.5, arpeggio=arpeggio_var.get())
        if wav_bytes:
            play_wav_bytes(wav_bytes, sr)

    def export_midi_single():
        root_index, notes = current_notes()
        name = chord_label(
            root_index,
            triad_var.get(),
            {k: v.get() for k, v in ext_vars.items()},
            {k: v.get() for k, v in alt_vars.items()},
            list(extra_intervals),
            list(extra_abs_notes),
        )
        path = filedialog.asksaveasfilename(
            defaultextension=".mid",
            filetypes=[("MIDI files", "*.mid")],
            initialfile=f"{name}.mid",
        )
        if not path:
            return
        key_signature = key_signature_info(key_root_var.get(), key_mode_var.get())
        write_midi(path, notes, tempo_var.get(), duration_var.get(), velocity_var.get(), key_signature)
        messagebox.showinfo("Export", f"Saved {os.path.basename(path)}")

    # Single chord tab
    single = ttk.Frame(notebook, padding=8, style="Panel.TFrame")
    notebook.add(single, text="Single Chord")

    left = ttk.Frame(single, style="Panel.TFrame")
    left.pack(side="left", fill="y")

    right = ttk.Frame(single, style="Panel.TFrame")
    right.pack(side="right", fill="both", expand=True)

    ttk.Label(left, text="Root").pack(anchor="w")
    root_menu = ttk.Combobox(left, textvariable=root_var, values=NOTE_NAMES_SHARP, state="readonly", width=6)
    root_menu.pack(anchor="w", pady=2)

    ttk.Label(left, text="Octave (C4 = middle C)").pack(anchor="w", pady=(10, 0))
    octave_spin = ttk.Spinbox(left, from_=0, to=8, textvariable=octave_var, width=6)
    octave_spin.pack(anchor="w", pady=2)

    ttk.Label(left, text="Chord Type").pack(anchor="w", pady=(10, 0))
    for name in TRIADS.keys():
        ttk.Radiobutton(left, text=name, value=name, variable=triad_var).pack(anchor="w")

    ttk.Label(left, text="Extensions").pack(anchor="w", pady=(10, 0))
    for name in ["6", "7", "Maj7", "Dim7", "9", "11", "13"]:
        ttk.Checkbutton(left, text=name, variable=ext_vars[name]).pack(anchor="w")

    ttk.Label(left, text="Alterations").pack(anchor="w", pady=(10, 0))
    for name in ALTERATIONS:
        ttk.Checkbutton(left, text=name, variable=alt_vars[name]).pack(anchor="w")

    # Voicing and notes
    options = ttk.LabelFrame(right, text="Voicing & Output", padding=8)
    options.pack(fill="x", pady=(0, 6))

    ttk.Label(options, text="Voicing").grid(row=0, column=0, sticky="w")
    ttk.Combobox(options, textvariable=voicing_var, values=["Close", "Open", "Drop 2", "Drop 3", "Spread"], state="readonly", width=10).grid(row=0, column=1, sticky="w")

    ttk.Label(options, text="Inversion").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Spinbox(options, from_=0, to=3, textvariable=inversion_var, width=8).grid(row=1, column=1, sticky="w", pady=(6, 0))

    ttk.Label(options, text="Max Notes").grid(row=2, column=0, sticky="w", pady=(6, 0))
    ttk.Spinbox(options, from_=1, to=8, textvariable=max_notes_var, width=8).grid(row=2, column=1, sticky="w", pady=(6, 0))

    ttk.Label(options, text="Tempo (BPM)").grid(row=3, column=0, sticky="w", pady=(6, 0))
    ttk.Spinbox(options, from_=40, to=240, textvariable=tempo_var, width=8).grid(row=3, column=1, sticky="w", pady=(6, 0))

    ttk.Label(options, text="Duration (beats)").grid(row=4, column=0, sticky="w", pady=(6, 0))
    ttk.Spinbox(options, from_=0.5, to=8.0, increment=0.5, textvariable=duration_var, width=8).grid(row=4, column=1, sticky="w", pady=(6, 0))

    ttk.Label(options, text="Velocity").grid(row=5, column=0, sticky="w", pady=(6, 0))
    ttk.Spinbox(options, from_=1, to=127, textvariable=velocity_var, width=8).grid(row=5, column=1, sticky="w", pady=(6, 0))

    ttk.Checkbutton(options, text="Arpeggio Preview", variable=arpeggio_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

    key_frame = ttk.LabelFrame(right, text="Key Signature & Display", padding=8)
    key_frame.pack(fill="x", pady=(0, 6))

    ttk.Label(key_frame, text="Key").grid(row=0, column=0, sticky="w")
    ttk.Combobox(key_frame, textvariable=key_root_var, values=NOTE_NAMES_SHARP + NOTE_NAMES_FLAT, state="readonly", width=6).grid(row=0, column=1, sticky="w")
    ttk.Combobox(key_frame, textvariable=key_mode_var, values=["Major", "Minor"], state="readonly", width=8).grid(row=0, column=2, sticky="w", padx=(6, 0))

    ttk.Label(key_frame, text="Display").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Combobox(key_frame, textvariable=display_mode_var, values=["Note Names", "Roman Numerals"], state="readonly", width=16).grid(row=1, column=1, columnspan=2, sticky="w", pady=(6, 0))

    # Extra intervals
    extras = ttk.LabelFrame(right, text="Extra Intervals (semitones)", padding=8)
    extras.pack(fill="x", pady=(0, 6))

    extra_list = tk.Listbox(extras, height=4, bg=palette["panel"], fg=palette["ink"], highlightthickness=1, highlightbackground=palette["accent2"])
    extra_list.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8))

    extra_entry = ttk.Entry(extras, width=8)
    extra_entry.grid(row=0, column=1, sticky="w")

    def refresh_extra_listbox():
        extra_list.delete(0, "end")
        for val in extra_intervals:
            extra_list.insert("end", str(val))

    def add_extra():
        try:
            val = int(extra_entry.get())
        except ValueError:
            return
        if val < -24 or val > 36:
            return
        if val not in extra_intervals:
            extra_intervals.append(val)
            extra_intervals.sort()
            refresh_extra_listbox()
            refresh_display()

    def remove_extra():
        sel = list(extra_list.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            val = int(extra_list.get(idx))
            extra_list.delete(idx)
            if val in extra_intervals:
                extra_intervals.remove(val)
        refresh_display()

    def open_single_modifier():
        open_modifier_window(
            "Chord Modifier",
            octave_var,
            octave_shift_var,
            inversion_var,
            voicing_var,
            max_notes_var,
            extra_intervals,
            extra_abs_notes,
            lambda: (refresh_extra_listbox(), refresh_display()),
        )

    ttk.Button(extras, text="Add", command=add_extra).grid(row=1, column=1, sticky="w", pady=(6, 0))
    ttk.Button(extras, text="Remove", command=remove_extra).grid(row=2, column=1, sticky="w", pady=(6, 0))

    # Output panel
    output = ttk.LabelFrame(right, text="Chord", padding=8)
    output.pack(fill="both", expand=True)

    chord_name_var = tk.StringVar(value="")
    chord_notes_var = tk.StringVar(value="")

    ttk.Label(output, text="Name:").pack(anchor="w")
    ttk.Label(output, textvariable=chord_name_var, font=("Georgia", 16, "bold")).pack(anchor="w", pady=(0, 8))

    ttk.Label(output, text="Notes:").pack(anchor="w")
    ttk.Label(output, textvariable=chord_notes_var, font=("Georgia", 12)).pack(anchor="w")

    # Actions
    actions = ttk.Frame(right)
    actions.pack(fill="x", pady=6)

    ttk.Button(actions, text="Preview", command=preview_single).pack(side="left", padx=4)
    ttk.Button(actions, text="Export MIDI", command=export_midi_single).pack(side="left", padx=4)
    ttk.Button(actions, text="Refresh", command=refresh_display).pack(side="left", padx=4)
    ttk.Button(actions, text="Chord Modifier...", command=open_single_modifier).pack(side="left", padx=4)

    # Scale helper
    scale_helper = ttk.LabelFrame(right, text="Scale Helper", padding=8)
    scale_helper.pack(fill="x", pady=6)

    scale_root_var = tk.StringVar(value="C")
    scale_type_var = tk.StringVar(value="Major (Ionian)")
    scale_use_sevenths = tk.BooleanVar(value=True)

    ttk.Label(scale_helper, text="Key").grid(row=0, column=0, sticky="w")
    ttk.Combobox(scale_helper, textvariable=scale_root_var, values=NOTE_NAMES_SHARP, state="readonly", width=6).grid(row=0, column=1, sticky="w")

    ttk.Label(scale_helper, text="Scale").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Combobox(scale_helper, textvariable=scale_type_var, values=list(SCALES.keys()), state="readonly", width=20).grid(row=1, column=1, sticky="w", pady=(6, 0))

    ttk.Checkbutton(scale_helper, text="Suggest 7ths", variable=scale_use_sevenths).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    scale_buttons = ttk.Frame(scale_helper)
    scale_buttons.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def clear_scale_buttons():
        for child in scale_buttons.winfo_children():
            child.destroy()

    def build_scale_suggestions(*_):
        clear_scale_buttons()
        root_idx = NOTE_NAMES_SHARP.index(scale_root_var.get())
        scale_intervals = SCALES[scale_type_var.get()]
        chords = build_scale_chords(scale_intervals)

        for i, (root_semi, triad, chord_intervals) in enumerate(chords):
            chord_root = (root_idx + root_semi) % 12
            triad_name = triad_quality(triad)

            def make_command(ch_root=chord_root, triad_name=triad_name, chord_intervals=chord_intervals):
                def cmd():
                    root_var.set(note_name(ch_root))
                    triad_var.set(triad_name)
                    # Reset flags
                    for v in ext_vars.values():
                        v.set(False)
                    for v in alt_vars.values():
                        v.set(False)
                    if scale_use_sevenths.get():
                        sev = sorted(chord_intervals)
                        if sev == [0, 4, 7, 11]:
                            ext_vars["Maj7"].set(True)
                        elif sev == [0, 3, 6, 9]:
                            ext_vars["Dim7"].set(True)
                        else:
                            ext_vars["7"].set(True)
                    refresh_display()

                return cmd

            label = note_name(chord_root) + ("m" if triad_name == "Minor" else "" if triad_name == "Major" else "dim" if triad_name == "Diminished" else "aug" if triad_name == "Augmented" else "")
            btn = ttk.Button(scale_buttons, text=label, width=6, command=make_command())
            btn.grid(row=0, column=i, padx=2, pady=2)

    build_scale_suggestions()

    scale_root_var.trace_add("write", build_scale_suggestions)
    scale_type_var.trace_add("write", build_scale_suggestions)
    scale_use_sevenths.trace_add("write", build_scale_suggestions)

    # Progression tab
    prog = ttk.Frame(notebook, padding=8, style="Panel.TFrame")
    notebook.add(prog, text="Progression")

    prog_left = ttk.Frame(prog, style="Panel.TFrame")
    prog_left.pack(side="left", fill="y")
    prog_right = ttk.Frame(prog, style="Panel.TFrame")
    prog_right.pack(side="right", fill="both", expand=True)

    ttk.Label(prog_left, text="Chord Builder").pack(anchor="w")

    prog_root_var = tk.StringVar(value="C")
    prog_octave_var = tk.IntVar(value=4)
    prog_octave_shift_var = tk.IntVar(value=0)
    prog_triad_var = tk.StringVar(value="Major")
    prog_ext_vars = {name: tk.BooleanVar(value=False) for name in ["6", "7", "Maj7", "Dim7", "9", "11", "13"]}
    prog_alt_vars = {name: tk.BooleanVar(value=False) for name in ALTERATIONS}
    prog_voicing_var = tk.StringVar(value="Close")
    prog_inversion_var = tk.IntVar(value=0)
    prog_max_notes_var = tk.IntVar(value=6)
    prog_extra_intervals = []
    prog_extra_abs_notes = []

    prog_builder = ttk.LabelFrame(prog_left, text="Build Chord", padding=6)
    prog_builder.pack(fill="x", pady=(4, 6))

    ttk.Label(prog_builder, text="Root").grid(row=0, column=0, sticky="w")
    ttk.Combobox(prog_builder, textvariable=prog_root_var, values=NOTE_NAMES_SHARP, state="readonly", width=6).grid(row=0, column=1, sticky="w")

    ttk.Label(prog_builder, text="Octave").grid(row=1, column=0, sticky="w", pady=(4, 0))
    ttk.Spinbox(prog_builder, from_=0, to=8, textvariable=prog_octave_var, width=6).grid(row=1, column=1, sticky="w", pady=(4, 0))

    ttk.Label(prog_builder, text="Type").grid(row=2, column=0, sticky="w", pady=(4, 0))
    ttk.Combobox(prog_builder, textvariable=prog_triad_var, values=list(TRIADS.keys()), state="readonly", width=10).grid(row=2, column=1, sticky="w", pady=(4, 0))

    ttk.Label(prog_builder, text="Ext").grid(row=3, column=0, sticky="w", pady=(4, 0))
    prog_ext_frame = ttk.Frame(prog_builder)
    prog_ext_frame.grid(row=3, column=1, sticky="w", pady=(6, 0))
    for idx, name in enumerate(["6", "7", "Maj7", "Dim7", "9", "11", "13"]):
        row = 0 if idx < 4 else 1
        col = idx if idx < 4 else idx - 4
        ttk.Checkbutton(prog_ext_frame, text=name, variable=prog_ext_vars[name]).grid(row=row, column=col, sticky="w")

    ttk.Label(prog_builder, text="Alt").grid(row=4, column=0, sticky="w", pady=(4, 0))
    prog_alt_frame = ttk.Frame(prog_builder)
    prog_alt_frame.grid(row=4, column=1, sticky="w", pady=(6, 0))
    for idx, name in enumerate(ALTERATIONS):
        row = 0 if idx < 3 else 1
        col = idx if idx < 3 else idx - 3
        ttk.Checkbutton(prog_alt_frame, text=name, variable=prog_alt_vars[name]).grid(row=row, column=col, sticky="w")

    ttk.Label(prog_builder, text="Voicing").grid(row=5, column=0, sticky="w", pady=(4, 0))
    ttk.Combobox(prog_builder, textvariable=prog_voicing_var, values=["Close", "Open", "Drop 2", "Drop 3", "Spread"], state="readonly", width=10).grid(row=5, column=1, sticky="w", pady=(4, 0))

    ttk.Label(prog_builder, text="Inversion").grid(row=6, column=0, sticky="w", pady=(4, 0))
    ttk.Spinbox(prog_builder, from_=0, to=3, textvariable=prog_inversion_var, width=6).grid(row=6, column=1, sticky="w", pady=(4, 0))

    ttk.Label(prog_builder, text="Max Notes").grid(row=7, column=0, sticky="w", pady=(4, 0))
    ttk.Spinbox(prog_builder, from_=1, to=8, textvariable=prog_max_notes_var, width=6).grid(row=7, column=1, sticky="w", pady=(4, 0))

    prog_extras = ttk.Frame(prog_builder)
    prog_extras.grid(row=8, column=0, columnspan=2, sticky="w", pady=(6, 0))
    ttk.Label(prog_extras, text="Extra (semitones)").grid(row=0, column=0, sticky="w")
    prog_extra_entry = ttk.Entry(prog_extras, width=6)
    prog_extra_entry.grid(row=0, column=1, sticky="w", padx=(6, 0))
    prog_extra_list = tk.Listbox(prog_extras, height=3, width=12, bg=palette["panel"], fg=palette["ink"], highlightthickness=1, highlightbackground=palette["accent2"])
    prog_extra_list.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def refresh_prog_extra_listbox():
        prog_extra_list.delete(0, "end")
        for val in prog_extra_intervals:
            prog_extra_list.insert("end", str(val))

    def prog_add_extra():
        try:
            val = int(prog_extra_entry.get())
        except ValueError:
            return
        if val < -24 or val > 36:
            return
        if val not in prog_extra_intervals:
            prog_extra_intervals.append(val)
            prog_extra_intervals.sort()
            refresh_prog_extra_listbox()

    def prog_remove_extra():
        sel = list(prog_extra_list.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            val = int(prog_extra_list.get(idx))
            prog_extra_list.delete(idx)
            if val in prog_extra_intervals:
                prog_extra_intervals.remove(val)

    def open_prog_modifier():
        open_modifier_window(
            "Chord Modifier",
            prog_octave_var,
            prog_octave_shift_var,
            prog_inversion_var,
            prog_voicing_var,
            prog_max_notes_var,
            prog_extra_intervals,
            prog_extra_abs_notes,
            refresh_prog_extra_listbox,
        )

    ttk.Button(prog_extras, text="Add", command=prog_add_extra).grid(row=0, column=2, padx=(6, 0))
    ttk.Button(prog_extras, text="Remove", command=prog_remove_extra).grid(row=1, column=2, padx=(6, 0))
    ttk.Button(prog_extras, text="Modifier...", command=open_prog_modifier).grid(row=0, column=3, rowspan=2, padx=(8, 0))

    ttk.Label(prog_left, text="Progression Settings").pack(anchor="w", pady=(6, 0))

    prog_tempo_var = tk.IntVar(value=DEFAULT_TEMPO_BPM)
    prog_duration_var = tk.DoubleVar(value=2.0)
    prog_velocity_var = tk.IntVar(value=90)
    prog_gap_var = tk.DoubleVar(value=0.0)
    prog_arpeggio_var = tk.BooleanVar(value=False)
    seq_enable_var = tk.BooleanVar(value=False)
    seq_step_vars = [tk.BooleanVar(value=False) for _ in range(16)]

    ttk.Label(prog_left, text="Tempo (BPM)").pack(anchor="w", pady=(4, 0))
    ttk.Spinbox(prog_left, from_=40, to=240, textvariable=prog_tempo_var, width=8).pack(anchor="w")

    ttk.Label(prog_left, text="Chord Duration (beats)").pack(anchor="w", pady=(4, 0))
    ttk.Spinbox(prog_left, from_=0.5, to=8.0, increment=0.5, textvariable=prog_duration_var, width=8).pack(anchor="w")

    ttk.Label(prog_left, text="Velocity").pack(anchor="w", pady=(4, 0))
    ttk.Spinbox(prog_left, from_=1, to=127, textvariable=prog_velocity_var, width=8).pack(anchor="w")

    ttk.Label(prog_left, text="Gap (beats)").pack(anchor="w", pady=(4, 0))
    ttk.Spinbox(prog_left, from_=0.0, to=4.0, increment=0.25, textvariable=prog_gap_var, width=8).pack(anchor="w")

    ttk.Checkbutton(prog_left, text="Arpeggio Preview", variable=prog_arpeggio_var).pack(anchor="w", pady=(4, 0))

    seq_frame = ttk.LabelFrame(prog_left, text="Rhythm (16-step)", padding=6)
    seq_frame.pack(fill="x", pady=(6, 0))

    ttk.Checkbutton(seq_frame, text="Enable Step Sequencer", variable=seq_enable_var).grid(row=0, column=0, columnspan=8, sticky="w")

    for idx in range(16):
        row = 1 + (idx // 8)
        col = idx % 8
        ttk.Checkbutton(seq_frame, text=str(idx + 1), variable=seq_step_vars[idx], width=3).grid(row=row, column=col, sticky="w")

    seq_actions = ttk.Frame(seq_frame)
    seq_actions.grid(row=3, column=0, columnspan=8, sticky="w", pady=(4, 0))

    def seq_set_pattern(pattern):
        for i, val in enumerate(pattern):
            seq_step_vars[i].set(val)

    ttk.Button(seq_actions, text="All", command=lambda: seq_set_pattern([True] * 16)).pack(side="left", padx=2)
    ttk.Button(seq_actions, text="Clear", command=lambda: seq_set_pattern([False] * 16)).pack(side="left", padx=2)
    ttk.Button(seq_actions, text="1/8", command=lambda: seq_set_pattern([(i % 2) == 0 for i in range(16)])).pack(side="left", padx=2)
    ttk.Button(seq_actions, text="1/4", command=lambda: seq_set_pattern([(i % 4) == 0 for i in range(16)])).pack(side="left", padx=2)

    prog_right_top = ttk.Frame(prog_right, style="Panel.TFrame")
    prog_right_top.pack(fill="x", pady=(0, 6))

    prog_key = ttk.LabelFrame(prog_right_top, text="Key Signature & Display", padding=6)
    prog_key.grid(row=0, column=0, sticky="w")

    ttk.Label(prog_key, text="Key").grid(row=0, column=0, sticky="w")
    ttk.Combobox(prog_key, textvariable=key_root_var, values=NOTE_NAMES_SHARP + NOTE_NAMES_FLAT, state="readonly", width=6).grid(row=0, column=1, sticky="w")
    ttk.Combobox(prog_key, textvariable=key_mode_var, values=["Major", "Minor"], state="readonly", width=8).grid(row=0, column=2, sticky="w", padx=(6, 0))

    ttk.Label(prog_key, text="Display").grid(row=1, column=0, sticky="w", pady=(4, 0))
    ttk.Combobox(prog_key, textvariable=display_mode_var, values=["Note Names", "Roman Numerals"], state="readonly", width=16).grid(row=1, column=1, columnspan=2, sticky="w", pady=(4, 0))

    prog_play = ttk.LabelFrame(prog_right_top, text="Playback", padding=6)
    prog_play.grid(row=0, column=1, sticky="e", padx=(10, 0))
    ttk.Button(prog_play, text="Preview", command=preview_progression).grid(row=0, column=0, sticky="ew", pady=2, padx=2)
    ttk.Button(prog_play, text="Preview Selected", command=preview_selected_chord).grid(row=1, column=0, sticky="ew", pady=2, padx=2)
    ttk.Button(prog_play, text="Export MIDI", command=export_progression).grid(row=2, column=0, sticky="ew", pady=2, padx=2)
    ttk.Button(prog_play, text="Load MIDI", command=load_progression_midi).grid(row=3, column=0, sticky="ew", pady=2, padx=2)

    prog_right_top.columnconfigure(0, weight=1)
    prog_right_top.columnconfigure(1, weight=0)

    prog_tree = ttk.Treeview(prog_right, columns=("name", "notes"), show="headings", height=10)
    prog_tree.heading("name", text="Chord")
    prog_tree.heading("notes", text="Notes")
    prog_tree.column("name", width=110, anchor="w")
    prog_tree.column("notes", width=380, anchor="w")
    prog_tree.pack(fill="both", expand=True)
    prog_tree.bind("<Double-1>", lambda _e: preview_selected_chord())

    progression = []

    def format_progression_row(item):
        if display_mode_var.get() == "Roman Numerals":
            key_root_index = note_index(key_root_var.get())
            name = roman_chord_label(
                item["root_index"],
                item["triad_name"],
                item["ext_flags"],
                item["alt_flags"],
                key_root_index,
                key_mode_var.get(),
                item.get("extra_intervals", []),
                item.get("extra_abs_notes", []),
            )
        else:
            name = chord_label(
                item["root_index"],
                item["triad_name"],
                item["ext_flags"],
                item["alt_flags"],
                item.get("extra_intervals", []),
                item.get("extra_abs_notes", []),
            )
        note_names = [note_label_for_midi(n) for n in item["notes"]]
        return name, ", ".join(note_names)

    def refresh_progression_display():
        for item in prog_tree.get_children():
            prog_tree.delete(item)
        for item in progression:
            name, notes = format_progression_row(item)
            prog_tree.insert("", "end", values=(name, notes))

    def prog_current_notes():
        root_index = NOTE_NAMES_SHARP.index(prog_root_var.get())
        notes = build_chord(
            root_index,
            prog_octave_var.get(),
            prog_triad_var.get(),
            {k: v.get() for k, v in prog_ext_vars.items()},
            {k: v.get() for k, v in prog_alt_vars.items()},
            prog_max_notes_var.get(),
            prog_voicing_var.get(),
            prog_inversion_var.get(),
            list(prog_extra_intervals),
            prog_octave_shift_var.get(),
            list(prog_extra_abs_notes),
        )
        return root_index, notes

    def add_to_progression():
        root_index, notes = prog_current_notes()
        item = {
            "root_index": root_index,
            "triad_name": prog_triad_var.get(),
            "ext_flags": {k: v.get() for k, v in prog_ext_vars.items()},
            "alt_flags": {k: v.get() for k, v in prog_alt_vars.items()},
            "extra_intervals": list(prog_extra_intervals),
            "extra_abs_notes": list(prog_extra_abs_notes),
            "notes": notes,
            "duration_beats": prog_duration_var.get(),
        }
        progression.append(item)
        name, notes_str = format_progression_row(item)
        prog_tree.insert("", "end", values=(name, notes_str))

    def update_selected():
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        root_index, notes = prog_current_notes()
        progression[idx] = {
            "root_index": root_index,
            "triad_name": prog_triad_var.get(),
            "ext_flags": {k: v.get() for k, v in prog_ext_vars.items()},
            "alt_flags": {k: v.get() for k, v in prog_alt_vars.items()},
            "extra_intervals": list(prog_extra_intervals),
            "extra_abs_notes": list(prog_extra_abs_notes),
            "notes": notes,
            "duration_beats": prog_duration_var.get(),
        }
        name, notes_str = format_progression_row(progression[idx])
        prog_tree.item(sel[0], values=(name, notes_str))

    def remove_selected():
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        prog_tree.delete(sel[0])
        progression.pop(idx)

    def move_selected(offset):
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        new_idx = idx + offset
        if new_idx < 0 or new_idx >= len(progression):
            return
        progression[idx], progression[new_idx] = progression[new_idx], progression[idx]
        prog_tree.move(sel[0], "", new_idx)

    def clear_progression():
        progression.clear()
        for item in prog_tree.get_children():
            prog_tree.delete(item)

    def build_chord_events():
        events = []
        seq_enabled = seq_enable_var.get()
        seq_pattern = [v.get() for v in seq_step_vars]
        base_step_beats = 0.25

        for item in progression:
            duration_beats = item.get("duration_beats", prog_duration_var.get())
            if seq_enabled:
                steps = max(1, int(round(duration_beats / base_step_beats)))
                step_duration = duration_beats / steps
                for idx in range(steps):
                    if seq_pattern[idx % 16]:
                        events.append((item["notes"], step_duration))
                    else:
                        events.append(([], step_duration))
            else:
                events.append((item["notes"], duration_beats))

            if prog_gap_var.get() > 0:
                events.append(([], prog_gap_var.get()))

        return events

    def preview_progression():
        if not progression:
            return
        bpm = prog_tempo_var.get()
        wav_all = bytearray()
        sr = 44100
        for notes, beats in build_chord_events():
            duration_seconds = 60.0 / bpm * beats
            if notes:
                wav_bytes, sr = generate_wav(notes, duration=duration_seconds, arpeggio=prog_arpeggio_var.get())
                wav_all.extend(wav_bytes)
            else:
                gap_samples = int(sr * duration_seconds)
                wav_all.extend(b"\x00\x00" * gap_samples)
        play_wav_bytes(bytes(wav_all), sr)

    def preview_selected_chord():
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        item = progression[idx]
        bpm = prog_tempo_var.get()
        duration_seconds = 60.0 / bpm * item.get("duration_beats", prog_duration_var.get())
        wav_bytes, sr = generate_wav(item["notes"], duration=duration_seconds, arpeggio=prog_arpeggio_var.get())
        if wav_bytes:
            play_wav_bytes(wav_bytes, sr)

    def export_progression():
        if not progression:
            return
        chord_events = build_chord_events()
        path = filedialog.asksaveasfilename(
            defaultextension=".mid",
            filetypes=[("MIDI files", "*.mid")],
            initialfile="progression.mid",
        )
        if not path:
            return
        key_signature = key_signature_info(key_root_var.get(), key_mode_var.get())
        write_midi_sequence(path, chord_events, prog_tempo_var.get(), prog_velocity_var.get(), key_signature)
        messagebox.showinfo("Export", f"Saved {os.path.basename(path)}")

    def load_progression_midi():
        path = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid *.midi")])
        if not path:
            return
        try:
            chord_events, ticks_per_beat, tempo_bpm, key_sig = parse_midi_file(path)
        except Exception as exc:
            messagebox.showerror("Load MIDI", f"Could not load MIDI: {exc}")
            return
        if not chord_events:
            messagebox.showwarning("Load MIDI", "No chord data found.")
            return

        clear_progression()
        durations = []
        for notes, duration_ticks in chord_events:
            if not notes:
                continue
            duration_beats = duration_ticks / ticks_per_beat if ticks_per_beat else prog_duration_var.get()
            if duration_beats <= 0:
                duration_beats = prog_duration_var.get()
            durations.append(duration_beats)

            root_index, triad_name, ext_flags, alt_flags, extra_intervals = analyze_chord_notes(notes)
            item = {
                "root_index": root_index,
                "triad_name": triad_name,
                "ext_flags": ext_flags,
                "alt_flags": alt_flags,
                "extra_intervals": extra_intervals,
                "extra_abs_notes": [],
                "notes": sorted(notes),
                "duration_beats": duration_beats,
            }
            progression.append(item)

        refresh_progression_display()

        if durations:
            avg_duration = sum(durations) / len(durations)
            prog_duration_var.set(round(avg_duration, 2))

        if tempo_bpm:
            prog_tempo_var.set(tempo_bpm)
        if key_sig:
            key = key_from_signature(key_sig[0], key_sig[1])
            if key:
                key_root_var.set(key[0])
                key_mode_var.set(key[1])

    prog_actions = ttk.Frame(prog_left)
    prog_actions.pack(fill="x", pady=6)

    ttk.Button(prog_actions, text="Add Current", command=add_to_progression).pack(fill="x", pady=2)
    ttk.Button(prog_actions, text="Update Selected", command=update_selected).pack(fill="x", pady=2)
    ttk.Button(prog_actions, text="Remove", command=remove_selected).pack(fill="x", pady=2)
    ttk.Button(prog_actions, text="Move Up", command=lambda: move_selected(-1)).pack(fill="x", pady=2)
    ttk.Button(prog_actions, text="Move Down", command=lambda: move_selected(1)).pack(fill="x", pady=2)
    ttk.Button(prog_actions, text="Clear", command=clear_progression).pack(fill="x", pady=2)


    # Auto-refresh on change
    for var in [root_var, octave_var, octave_shift_var, triad_var, voicing_var, inversion_var, max_notes_var, tempo_var, duration_var, velocity_var, arpeggio_var]:
        var.trace_add("write", refresh_display)
    for var in ext_vars.values():
        var.trace_add("write", refresh_display)
    for var in alt_vars.values():
        var.trace_add("write", refresh_display)
    for var in [key_root_var, key_mode_var, display_mode_var]:
        var.trace_add("write", refresh_display)
        var.trace_add("write", lambda *_: refresh_progression_display())

    refresh_display()


def main():
    root = tk.Tk()
    build_ui(root)
    root.mainloop()



# Compact layout override to fit 14" screens without fullscreen

def build_ui_compact(root):
    root.title("Chordo-v2 - Chord Builder")
    root.geometry("960x640")
    root.minsize(900, 620)

    palette = {
        "bg": "#f3efe6",
        "panel": "#fbf7ef",
        "accent": "#6a4b2b",
        "accent2": "#b08b5a",
        "muted": "#8b775a",
        "ink": "#2a1f16",
    }

    root.configure(bg=palette["bg"])

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TFrame", background=palette["bg"])
    style.configure("Panel.TFrame", background=palette["panel"])
    style.configure("TLabel", background=palette["panel"], foreground=palette["ink"])
    style.configure("Title.TLabel", background=palette["bg"], foreground=palette["accent"], font=("Georgia", 16, "bold"))
    style.configure("Sub.TLabel", background=palette["bg"], foreground=palette["muted"], font=("Georgia", 10))
    style.configure("TLabelframe", background=palette["panel"], foreground=palette["accent"])
    style.configure("TLabelframe.Label", background=palette["panel"], foreground=palette["accent"], font=("Georgia", 10, "bold"))
    style.configure("TButton", background=palette["panel"], foreground=palette["ink"], padding=(6, 3))
    style.map("TButton", background=[("active", palette["accent2"])], foreground=[("active", palette["ink"])])
    style.configure("TCheckbutton", background=palette["panel"], foreground=palette["ink"])
    style.configure("TRadiobutton", background=palette["panel"], foreground=palette["ink"])
    style.configure("TCombobox", fieldbackground=palette["panel"], background=palette["panel"], foreground=palette["ink"])
    style.configure("TSpinbox", fieldbackground=palette["panel"], background=palette["panel"], foreground=palette["ink"])
    style.configure("Treeview", background=palette["panel"], fieldbackground=palette["panel"], foreground=palette["ink"], rowheight=20)
    style.configure("Treeview.Heading", background=palette["accent2"], foreground=palette["ink"], font=("Georgia", 9, "bold"))
    style.configure("TNotebook", background=palette["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=palette["panel"], foreground=palette["ink"], padding=(10, 4))
    style.map("TNotebook.Tab", background=[("selected", palette["accent2"])], foreground=[("selected", palette["ink"])])

    main = ttk.Frame(root, padding=6, style="Panel.TFrame")
    main.pack(fill="both", expand=True)

    header = ttk.Frame(main, style="Panel.TFrame")
    header.pack(fill="x", pady=(0, 4))
    ttk.Label(header, text="Chordo-v2", style="Title.TLabel").pack(side="left")
    ttk.Label(header, text="Compact chord workshop", style="Sub.TLabel").pack(side="left", padx=(10, 0))

    notebook = ttk.Notebook(main)
    notebook.pack(fill="both", expand=True)

    # Shared state
    root_var = tk.StringVar(value="C")
    octave_var = tk.IntVar(value=4)
    octave_shift_var = tk.IntVar(value=0)
    triad_var = tk.StringVar(value="Major")
    ext_vars = {name: tk.BooleanVar(value=False) for name in ["6", "7", "Maj7", "Dim7", "9", "11", "13"]}
    alt_vars = {name: tk.BooleanVar(value=False) for name in ALTERATIONS}
    key_root_var = tk.StringVar(value="C")
    key_mode_var = tk.StringVar(value="Major")
    display_mode_var = tk.StringVar(value="Note Names")
    voicing_var = tk.StringVar(value="Close")
    inversion_var = tk.IntVar(value=0)
    max_notes_var = tk.IntVar(value=6)
    tempo_var = tk.IntVar(value=DEFAULT_TEMPO_BPM)
    duration_var = tk.DoubleVar(value=2.0)
    velocity_var = tk.IntVar(value=90)
    arpeggio_var = tk.BooleanVar(value=False)
    extra_intervals = []
    extra_abs_notes = []

    def current_notes():
        root_index = NOTE_NAMES_SHARP.index(root_var.get())
        notes = build_chord(
            root_index,
            octave_var.get(),
            triad_var.get(),
            {k: v.get() for k, v in ext_vars.items()},
            {k: v.get() for k, v in alt_vars.items()},
            max_notes_var.get(),
            voicing_var.get(),
            inversion_var.get(),
            extra_intervals,
            octave_shift_var.get(),
            list(extra_abs_notes),
        )
        return root_index, notes

    def display_chord_name(root_index):
        if display_mode_var.get() == "Roman Numerals":
            key_root_index = note_index(key_root_var.get())
            return roman_chord_label(
                root_index,
                triad_var.get(),
                {k: v.get() for k, v in ext_vars.items()},
                {k: v.get() for k, v in alt_vars.items()},
                key_root_index,
                key_mode_var.get(),
                list(extra_intervals),
                list(extra_abs_notes),
            )
        return chord_label(
            root_index,
            triad_var.get(),
            {k: v.get() for k, v in ext_vars.items()},
            {k: v.get() for k, v in alt_vars.items()},
            list(extra_intervals),
            list(extra_abs_notes),
        )

    def refresh_display(*_):
        root_index, notes = current_notes()
        name = display_chord_name(root_index)
        note_names = [note_label_for_midi(n) for n in notes]
        chord_name_var.set(name)
        chord_notes_var.set(", ".join(note_names) if note_names else "")

    def preview_single():
        _, notes = current_notes()
        wav_bytes, sr = generate_wav(notes, duration=1.5, arpeggio=arpeggio_var.get())
        if wav_bytes:
            play_wav_bytes(wav_bytes, sr)

    def export_midi_single():
        root_index, notes = current_notes()
        name = chord_label(
            root_index,
            triad_var.get(),
            {k: v.get() for k, v in ext_vars.items()},
            {k: v.get() for k, v in alt_vars.items()},
            list(extra_intervals),
            list(extra_abs_notes),
        )
        path = filedialog.asksaveasfilename(
            defaultextension=".mid",
            filetypes=[("MIDI files", "*.mid")],
            initialfile=f"{name}.mid",
        )
        if not path:
            return
        key_signature = key_signature_info(key_root_var.get(), key_mode_var.get())
        write_midi(path, notes, tempo_var.get(), duration_var.get(), velocity_var.get(), key_signature)
        messagebox.showinfo("Export", f"Saved {os.path.basename(path)}")

    # Single tab
    single = ttk.Frame(notebook, padding=6, style="Panel.TFrame")
    notebook.add(single, text="Single")
    single.columnconfigure(0, weight=1, uniform="single")
    single.columnconfigure(1, weight=1, uniform="single")
    single.rowconfigure(2, weight=1)

    builder = ttk.LabelFrame(single, text="Chord Builder", padding=6)
    builder.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))

    ttk.Label(builder, text="Root").grid(row=0, column=0, sticky="w")
    ttk.Combobox(builder, textvariable=root_var, values=NOTE_NAMES_SHARP, state="readonly", width=6).grid(row=0, column=1, sticky="w")
    ttk.Label(builder, text="Octave").grid(row=0, column=2, sticky="w", padx=(8, 0))
    ttk.Spinbox(builder, from_=0, to=8, textvariable=octave_var, width=5).grid(row=0, column=3, sticky="w")

    ttk.Label(builder, text="Type").grid(row=1, column=0, sticky="w", pady=(4, 0))
    triad_frame = ttk.Frame(builder)
    triad_frame.grid(row=1, column=1, columnspan=3, sticky="w", pady=(4, 0))
    for idx, name in enumerate(TRIADS.keys()):
        ttk.Radiobutton(triad_frame, text=name, value=name, variable=triad_var).grid(row=idx // 3, column=idx % 3, sticky="w", padx=2)

    ttk.Label(builder, text="Ext").grid(row=2, column=0, sticky="w", pady=(4, 0))
    ext_frame = ttk.Frame(builder)
    ext_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=(4, 0))
    for idx, name in enumerate(["6", "7", "Maj7", "Dim7", "9", "11", "13"]):
        ttk.Checkbutton(ext_frame, text=name, variable=ext_vars[name]).grid(row=idx // 4, column=idx % 4, sticky="w")

    ttk.Label(builder, text="Alt").grid(row=3, column=0, sticky="w", pady=(4, 0))
    alt_frame = ttk.Frame(builder)
    alt_frame.grid(row=3, column=1, columnspan=3, sticky="w", pady=(4, 0))
    for idx, name in enumerate(ALTERATIONS):
        ttk.Checkbutton(alt_frame, text=name, variable=alt_vars[name]).grid(row=idx // 3, column=idx % 3, sticky="w")

    extras = ttk.LabelFrame(single, text="Extra Intervals", padding=6)
    extras.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
    extra_list = tk.Listbox(extras, height=3, bg=palette["panel"], fg=palette["ink"], highlightthickness=1, highlightbackground=palette["accent2"])
    extra_list.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 6))
    extra_entry = ttk.Entry(extras, width=6)
    extra_entry.grid(row=0, column=1, sticky="w")

    def refresh_extra_listbox():
        extra_list.delete(0, "end")
        for val in extra_intervals:
            extra_list.insert("end", str(val))

    def add_extra():
        try:
            val = int(extra_entry.get())
        except ValueError:
            return
        if val < -24 or val > 36:
            return
        if val not in extra_intervals:
            extra_intervals.append(val)
            extra_intervals.sort()
            refresh_extra_listbox()
            refresh_display()

    def remove_extra():
        sel = list(extra_list.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            val = int(extra_list.get(idx))
            extra_list.delete(idx)
            if val in extra_intervals:
                extra_intervals.remove(val)
        refresh_display()

    def open_single_modifier():
        open_modifier_window(
            "Chord Modifier",
            octave_var,
            octave_shift_var,
            inversion_var,
            voicing_var,
            max_notes_var,
            extra_intervals,
            extra_abs_notes,
            lambda: (refresh_extra_listbox(), refresh_display()),
        )

    ttk.Button(extras, text="Add", command=add_extra).grid(row=0, column=2, padx=(6, 0))
    ttk.Button(extras, text="Remove", command=remove_extra).grid(row=1, column=2, padx=(6, 0))
    ttk.Button(extras, text="Modifier...", command=open_single_modifier).grid(row=0, column=3, rowspan=2, padx=(6, 0))

    output = ttk.LabelFrame(single, text="Output", padding=6)
    output.grid(row=0, column=1, rowspan=2, sticky="nsew", pady=(0, 4))
    output.columnconfigure(1, weight=1)

    ttk.Label(output, text="Voicing").grid(row=0, column=0, sticky="w")
    ttk.Combobox(output, textvariable=voicing_var, values=["Close", "Open", "Drop 2", "Drop 3", "Spread"], state="readonly", width=10).grid(row=0, column=1, sticky="w")
    ttk.Label(output, text="Inversion").grid(row=0, column=2, sticky="w", padx=(8, 0))
    ttk.Spinbox(output, from_=0, to=3, textvariable=inversion_var, width=5).grid(row=0, column=3, sticky="w")

    ttk.Label(output, text="Max").grid(row=1, column=0, sticky="w", pady=(4, 0))
    ttk.Spinbox(output, from_=1, to=8, textvariable=max_notes_var, width=5).grid(row=1, column=1, sticky="w", pady=(4, 0))
    ttk.Label(output, text="Tempo").grid(row=1, column=2, sticky="w", padx=(8, 0), pady=(4, 0))
    ttk.Spinbox(output, from_=40, to=240, textvariable=tempo_var, width=5).grid(row=1, column=3, sticky="w", pady=(4, 0))

    ttk.Label(output, text="Dur").grid(row=2, column=0, sticky="w", pady=(4, 0))
    ttk.Spinbox(output, from_=0.5, to=8.0, increment=0.5, textvariable=duration_var, width=5).grid(row=2, column=1, sticky="w", pady=(4, 0))
    ttk.Label(output, text="Vel").grid(row=2, column=2, sticky="w", padx=(8, 0), pady=(4, 0))
    ttk.Spinbox(output, from_=1, to=127, textvariable=velocity_var, width=5).grid(row=2, column=3, sticky="w", pady=(4, 0))
    ttk.Checkbutton(output, text="Arpeggio", variable=arpeggio_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

    key_frame = ttk.LabelFrame(output, text="Key/Display", padding=6)
    key_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(4, 0))
    ttk.Label(key_frame, text="Key").grid(row=0, column=0, sticky="w")
    ttk.Combobox(key_frame, textvariable=key_root_var, values=NOTE_NAMES_SHARP + NOTE_NAMES_FLAT, state="readonly", width=5).grid(row=0, column=1, sticky="w")
    ttk.Combobox(key_frame, textvariable=key_mode_var, values=["Major", "Minor"], state="readonly", width=7).grid(row=0, column=2, sticky="w", padx=(4, 0))
    ttk.Label(key_frame, text="Display").grid(row=0, column=3, sticky="w", padx=(8, 0))
    ttk.Combobox(key_frame, textvariable=display_mode_var, values=["Note Names", "Roman Numerals"], state="readonly", width=14).grid(row=0, column=4, sticky="w")

    chord_name_var = tk.StringVar(value="")
    chord_notes_var = tk.StringVar(value="")
    ttk.Label(output, text="Name:").grid(row=5, column=0, sticky="w", pady=(6, 0))
    ttk.Label(output, textvariable=chord_name_var, font=("Georgia", 14, "bold")).grid(row=5, column=1, columnspan=3, sticky="w", pady=(6, 0))
    ttk.Label(output, text="Notes:").grid(row=6, column=0, sticky="w")
    ttk.Label(output, textvariable=chord_notes_var, font=("Georgia", 11)).grid(row=6, column=1, columnspan=3, sticky="w")

    actions = ttk.Frame(output)
    actions.grid(row=7, column=0, columnspan=4, sticky="w", pady=(6, 0))
    ttk.Button(actions, text="Preview", command=preview_single).pack(side="left", padx=2)
    ttk.Button(actions, text="Export MIDI", command=export_midi_single).pack(side="left", padx=2)
    ttk.Button(actions, text="Refresh", command=refresh_display).pack(side="left", padx=2)

    scale_helper = ttk.LabelFrame(single, text="Scale Helper", padding=6)
    scale_helper.grid(row=2, column=0, columnspan=2, sticky="ew")
    scale_root_var = tk.StringVar(value="C")
    scale_type_var = tk.StringVar(value="Major (Ionian)")
    scale_use_sevenths = tk.BooleanVar(value=True)
    ttk.Label(scale_helper, text="Key").grid(row=0, column=0, sticky="w")
    ttk.Combobox(scale_helper, textvariable=scale_root_var, values=NOTE_NAMES_SHARP, state="readonly", width=5).grid(row=0, column=1, sticky="w")
    ttk.Label(scale_helper, text="Scale").grid(row=0, column=2, sticky="w", padx=(8, 0))
    ttk.Combobox(scale_helper, textvariable=scale_type_var, values=list(SCALES.keys()), state="readonly", width=18).grid(row=0, column=3, sticky="w")
    ttk.Checkbutton(scale_helper, text="Suggest 7ths", variable=scale_use_sevenths).grid(row=0, column=4, sticky="w", padx=(8, 0))
    scale_buttons = ttk.Frame(scale_helper)
    scale_buttons.grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 0))

    def clear_scale_buttons():
        for child in scale_buttons.winfo_children():
            child.destroy()

    def build_scale_suggestions(*_):
        clear_scale_buttons()
        root_idx = NOTE_NAMES_SHARP.index(scale_root_var.get())
        scale_intervals = SCALES[scale_type_var.get()]
        chords = build_scale_chords(scale_intervals)
        for i, (root_semi, triad, chord_intervals) in enumerate(chords):
            chord_root = (root_idx + root_semi) % 12
            triad_name = triad_quality(triad)

            def make_command(ch_root=chord_root, triad_name=triad_name, chord_intervals=chord_intervals):
                def cmd():
                    root_var.set(note_name(ch_root))
                    triad_var.set(triad_name)
                    for v in ext_vars.values():
                        v.set(False)
                    for v in alt_vars.values():
                        v.set(False)
                    if scale_use_sevenths.get():
                        sev = sorted(chord_intervals)
                        if sev == [0, 4, 7, 11]:
                            ext_vars["Maj7"].set(True)
                        elif sev == [0, 3, 6, 9]:
                            ext_vars["Dim7"].set(True)
                        else:
                            ext_vars["7"].set(True)
                    refresh_display()

                return cmd

            label = note_name(chord_root) + ("m" if triad_name == "Minor" else "" if triad_name == "Major" else "dim" if triad_name == "Diminished" else "aug" if triad_name == "Augmented" else "")
            btn = ttk.Button(scale_buttons, text=label, width=5, command=make_command())
            btn.grid(row=0, column=i, padx=2, pady=1)

    build_scale_suggestions()
    scale_root_var.trace_add("write", build_scale_suggestions)
    scale_type_var.trace_add("write", build_scale_suggestions)
    scale_use_sevenths.trace_add("write", build_scale_suggestions)

    # Progression tab
    prog = ttk.Frame(notebook, padding=6, style="Panel.TFrame")
    notebook.add(prog, text="Progression")
    prog.columnconfigure(0, weight=1)
    prog.rowconfigure(2, weight=1)

    prog_root_var = tk.StringVar(value="C")
    prog_octave_var = tk.IntVar(value=4)
    prog_octave_shift_var = tk.IntVar(value=0)
    prog_triad_var = tk.StringVar(value="Major")
    prog_ext_vars = {name: tk.BooleanVar(value=False) for name in ["6", "7", "Maj7", "Dim7", "9", "11", "13"]}
    prog_alt_vars = {name: tk.BooleanVar(value=False) for name in ALTERATIONS}
    prog_voicing_var = tk.StringVar(value="Close")
    prog_inversion_var = tk.IntVar(value=0)
    prog_max_notes_var = tk.IntVar(value=6)
    prog_extra_intervals = []
    prog_extra_abs_notes = []
    prog_tempo_var = tk.IntVar(value=DEFAULT_TEMPO_BPM)
    prog_duration_var = tk.DoubleVar(value=2.0)
    prog_velocity_var = tk.IntVar(value=90)
    prog_gap_var = tk.DoubleVar(value=0.0)
    prog_arpeggio_var = tk.BooleanVar(value=False)
    seq_enable_var = tk.BooleanVar(value=False)
    seq_step_vars = [tk.BooleanVar(value=False) for _ in range(16)]

    top = ttk.Frame(prog, style="Panel.TFrame")
    top.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    top.columnconfigure(0, weight=1)
    top.columnconfigure(1, weight=1)

    prog_builder = ttk.LabelFrame(top, text="Builder", padding=6)
    prog_builder.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

    ttk.Label(prog_builder, text="Root").grid(row=0, column=0, sticky="w")
    ttk.Combobox(prog_builder, textvariable=prog_root_var, values=NOTE_NAMES_SHARP, state="readonly", width=5).grid(row=0, column=1, sticky="w")
    ttk.Label(prog_builder, text="Oct").grid(row=0, column=2, sticky="w", padx=(6, 0))
    ttk.Spinbox(prog_builder, from_=0, to=8, textvariable=prog_octave_var, width=5).grid(row=0, column=3, sticky="w")
    ttk.Label(prog_builder, text="Type").grid(row=1, column=0, sticky="w", pady=(4, 0))
    ttk.Combobox(prog_builder, textvariable=prog_triad_var, values=list(TRIADS.keys()), state="readonly", width=10).grid(row=1, column=1, sticky="w", pady=(4, 0))
    ttk.Label(prog_builder, text="Voicing").grid(row=1, column=2, sticky="w", padx=(6, 0), pady=(4, 0))
    ttk.Combobox(prog_builder, textvariable=prog_voicing_var, values=["Close", "Open", "Drop 2", "Drop 3", "Spread"], state="readonly", width=9).grid(row=1, column=3, sticky="w", pady=(4, 0))

    ttk.Label(prog_builder, text="Ext").grid(row=2, column=0, sticky="w", pady=(4, 0))
    prog_ext_frame = ttk.Frame(prog_builder)
    prog_ext_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=(4, 0))
    for idx, name in enumerate(["6", "7", "Maj7", "Dim7", "9", "11", "13"]):
        ttk.Checkbutton(prog_ext_frame, text=name, variable=prog_ext_vars[name]).grid(row=idx // 4, column=idx % 4, sticky="w")

    ttk.Label(prog_builder, text="Alt").grid(row=3, column=0, sticky="w", pady=(4, 0))
    prog_alt_frame = ttk.Frame(prog_builder)
    prog_alt_frame.grid(row=3, column=1, columnspan=3, sticky="w", pady=(4, 0))
    for idx, name in enumerate(ALTERATIONS):
        ttk.Checkbutton(prog_alt_frame, text=name, variable=prog_alt_vars[name]).grid(row=idx // 3, column=idx % 3, sticky="w")

    ttk.Label(prog_builder, text="Inv").grid(row=4, column=0, sticky="w", pady=(4, 0))
    ttk.Spinbox(prog_builder, from_=0, to=3, textvariable=prog_inversion_var, width=5).grid(row=4, column=1, sticky="w", pady=(4, 0))
    ttk.Label(prog_builder, text="Max").grid(row=4, column=2, sticky="w", padx=(6, 0), pady=(4, 0))
    ttk.Spinbox(prog_builder, from_=1, to=8, textvariable=prog_max_notes_var, width=5).grid(row=4, column=3, sticky="w", pady=(4, 0))

    prog_extras = ttk.Frame(prog_builder)
    prog_extras.grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))
    ttk.Label(prog_extras, text="Extra").grid(row=0, column=0, sticky="w")
    prog_extra_entry = ttk.Entry(prog_extras, width=6)
    prog_extra_entry.grid(row=0, column=1, sticky="w", padx=(4, 0))
    prog_extra_list = tk.Listbox(prog_extras, height=2, width=10, bg=palette["panel"], fg=palette["ink"], highlightthickness=1, highlightbackground=palette["accent2"])
    prog_extra_list.grid(row=0, column=2, rowspan=2, sticky="w", padx=(6, 0))

    def refresh_prog_extra_listbox():
        prog_extra_list.delete(0, "end")
        for val in prog_extra_intervals:
            prog_extra_list.insert("end", str(val))

    def prog_add_extra():
        try:
            val = int(prog_extra_entry.get())
        except ValueError:
            return
        if val < -24 or val > 36:
            return
        if val not in prog_extra_intervals:
            prog_extra_intervals.append(val)
            prog_extra_intervals.sort()
            refresh_prog_extra_listbox()

    def prog_remove_extra():
        sel = list(prog_extra_list.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            val = int(prog_extra_list.get(idx))
            prog_extra_list.delete(idx)
            if val in prog_extra_intervals:
                prog_extra_intervals.remove(val)

    def open_prog_modifier():
        open_modifier_window(
            "Chord Modifier",
            prog_octave_var,
            prog_octave_shift_var,
            prog_inversion_var,
            prog_voicing_var,
            prog_max_notes_var,
            prog_extra_intervals,
            prog_extra_abs_notes,
            refresh_prog_extra_listbox,
        )

    ttk.Button(prog_extras, text="Add", command=prog_add_extra).grid(row=0, column=3, padx=(6, 0))
    ttk.Button(prog_extras, text="Remove", command=prog_remove_extra).grid(row=1, column=3, padx=(6, 0))
    ttk.Button(prog_extras, text="Modifier...", command=open_prog_modifier).grid(row=0, column=4, rowspan=2, padx=(6, 0))

    settings = ttk.LabelFrame(top, text="Settings", padding=6)
    settings.grid(row=0, column=1, sticky="nsew")
    ttk.Label(settings, text="Tempo").grid(row=0, column=0, sticky="w")
    ttk.Spinbox(settings, from_=40, to=240, textvariable=prog_tempo_var, width=6).grid(row=0, column=1, sticky="w")
    ttk.Label(settings, text="Dur").grid(row=0, column=2, sticky="w", padx=(6, 0))
    ttk.Spinbox(settings, from_=0.5, to=8.0, increment=0.5, textvariable=prog_duration_var, width=6).grid(row=0, column=3, sticky="w")
    ttk.Label(settings, text="Vel").grid(row=1, column=0, sticky="w", pady=(4, 0))
    ttk.Spinbox(settings, from_=1, to=127, textvariable=prog_velocity_var, width=6).grid(row=1, column=1, sticky="w", pady=(4, 0))
    ttk.Label(settings, text="Gap").grid(row=1, column=2, sticky="w", padx=(6, 0), pady=(4, 0))
    ttk.Spinbox(settings, from_=0.0, to=4.0, increment=0.25, textvariable=prog_gap_var, width=6).grid(row=1, column=3, sticky="w", pady=(4, 0))
    ttk.Checkbutton(settings, text="Arpeggio", variable=prog_arpeggio_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

    key_play = ttk.LabelFrame(settings, text="Key / Playback", padding=6)
    key_play.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(6, 0))
    ttk.Label(key_play, text="Key").grid(row=0, column=0, sticky="w")
    ttk.Combobox(key_play, textvariable=key_root_var, values=NOTE_NAMES_SHARP + NOTE_NAMES_FLAT, state="readonly", width=5).grid(row=0, column=1, sticky="w")
    ttk.Combobox(key_play, textvariable=key_mode_var, values=["Major", "Minor"], state="readonly", width=7).grid(row=0, column=2, sticky="w", padx=(4, 0))
    ttk.Label(key_play, text="Display").grid(row=0, column=3, sticky="w", padx=(6, 0))
    ttk.Combobox(key_play, textvariable=display_mode_var, values=["Note Names", "Roman Numerals"], state="readonly", width=13).grid(row=0, column=4, sticky="w")

    playback = ttk.Frame(key_play)
    playback.grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 0))

    rhythm = ttk.LabelFrame(prog, text="Rhythm (16-step)", padding=6)
    rhythm.grid(row=1, column=0, sticky="ew", pady=(0, 4))
    ttk.Checkbutton(rhythm, text="Enable", variable=seq_enable_var).grid(row=0, column=0, sticky="w")
    for idx in range(16):
        row = 1 + (idx // 8)
        col = idx % 8
        ttk.Checkbutton(rhythm, text=str(idx + 1), variable=seq_step_vars[idx], width=3).grid(row=row, column=col, sticky="w")
    seq_actions = ttk.Frame(rhythm)
    seq_actions.grid(row=3, column=0, columnspan=8, sticky="w", pady=(2, 0))

    def seq_set_pattern(pattern):
        for i, val in enumerate(pattern):
            seq_step_vars[i].set(val)

    ttk.Button(seq_actions, text="All", command=lambda: seq_set_pattern([True] * 16)).pack(side="left", padx=2)
    ttk.Button(seq_actions, text="Clear", command=lambda: seq_set_pattern([False] * 16)).pack(side="left", padx=2)
    ttk.Button(seq_actions, text="1/8", command=lambda: seq_set_pattern([(i % 2) == 0 for i in range(16)])).pack(side="left", padx=2)
    ttk.Button(seq_actions, text="1/4", command=lambda: seq_set_pattern([(i % 4) == 0 for i in range(16)])).pack(side="left", padx=2)

    prog_tree = ttk.Treeview(prog, columns=("name", "notes"), show="headings", height=9)
    prog_tree.heading("name", text="Chord")
    prog_tree.heading("notes", text="Notes")
    prog_tree.column("name", width=120, anchor="w")
    prog_tree.column("notes", width=520, anchor="w")
    prog_tree.grid(row=2, column=0, sticky="nsew")

    actions = ttk.Frame(prog, style="Panel.TFrame")
    actions.grid(row=3, column=0, sticky="ew", pady=(4, 0))

    progression = []

    def format_progression_row(item):
        if display_mode_var.get() == "Roman Numerals":
            key_root_index = note_index(key_root_var.get())
            name = roman_chord_label(
                item["root_index"],
                item["triad_name"],
                item["ext_flags"],
                item["alt_flags"],
                key_root_index,
                key_mode_var.get(),
                item.get("extra_intervals", []),
                item.get("extra_abs_notes", []),
            )
        else:
            name = chord_label(
                item["root_index"],
                item["triad_name"],
                item["ext_flags"],
                item["alt_flags"],
                item.get("extra_intervals", []),
                item.get("extra_abs_notes", []),
            )
        note_names = [note_label_for_midi(n) for n in item["notes"]]
        return name, ", ".join(note_names)

    def refresh_progression_display():
        for item in prog_tree.get_children():
            prog_tree.delete(item)
        for item in progression:
            name, notes = format_progression_row(item)
            prog_tree.insert("", "end", values=(name, notes))

    def prog_current_notes():
        root_index = NOTE_NAMES_SHARP.index(prog_root_var.get())
        notes = build_chord(
            root_index,
            prog_octave_var.get(),
            prog_triad_var.get(),
            {k: v.get() for k, v in prog_ext_vars.items()},
            {k: v.get() for k, v in prog_alt_vars.items()},
            prog_max_notes_var.get(),
            prog_voicing_var.get(),
            prog_inversion_var.get(),
            list(prog_extra_intervals),
            prog_octave_shift_var.get(),
            list(prog_extra_abs_notes),
        )
        return root_index, notes

    def add_to_progression():
        root_index, notes = prog_current_notes()
        item = {
            "root_index": root_index,
            "triad_name": prog_triad_var.get(),
            "ext_flags": {k: v.get() for k, v in prog_ext_vars.items()},
            "alt_flags": {k: v.get() for k, v in prog_alt_vars.items()},
            "extra_intervals": list(prog_extra_intervals),
            "extra_abs_notes": list(prog_extra_abs_notes),
            "notes": notes,
            "duration_beats": prog_duration_var.get(),
        }
        progression.append(item)
        name, notes_str = format_progression_row(item)
        prog_tree.insert("", "end", values=(name, notes_str))

    def update_selected():
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        root_index, notes = prog_current_notes()
        progression[idx] = {
            "root_index": root_index,
            "triad_name": prog_triad_var.get(),
            "ext_flags": {k: v.get() for k, v in prog_ext_vars.items()},
            "alt_flags": {k: v.get() for k, v in prog_alt_vars.items()},
            "extra_intervals": list(prog_extra_intervals),
            "extra_abs_notes": list(prog_extra_abs_notes),
            "notes": notes,
            "duration_beats": prog_duration_var.get(),
        }
        name, notes_str = format_progression_row(progression[idx])
        prog_tree.item(sel[0], values=(name, notes_str))

    def remove_selected():
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        prog_tree.delete(sel[0])
        progression.pop(idx)

    def move_selected(offset):
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        new_idx = idx + offset
        if new_idx < 0 or new_idx >= len(progression):
            return
        progression[idx], progression[new_idx] = progression[new_idx], progression[idx]
        prog_tree.move(sel[0], "", new_idx)

    def clear_progression():
        progression.clear()
        for item in prog_tree.get_children():
            prog_tree.delete(item)

    def build_chord_events():
        events = []
        seq_enabled = seq_enable_var.get()
        seq_pattern = [v.get() for v in seq_step_vars]
        base_step_beats = 0.25

        for item in progression:
            duration_beats = item.get("duration_beats", prog_duration_var.get())
            if seq_enabled:
                steps = max(1, int(round(duration_beats / base_step_beats)))
                step_duration = duration_beats / steps
                for idx in range(steps):
                    if seq_pattern[idx % 16]:
                        events.append((item["notes"], step_duration))
                    else:
                        events.append(([], step_duration))
            else:
                events.append((item["notes"], duration_beats))

            if prog_gap_var.get() > 0:
                events.append(([], prog_gap_var.get()))

        return events

    def preview_progression():
        if not progression:
            return
        bpm = prog_tempo_var.get()
        wav_all = bytearray()
        sr = 44100
        for notes, beats in build_chord_events():
            duration_seconds = 60.0 / bpm * beats
            if notes:
                wav_bytes, sr = generate_wav(notes, duration=duration_seconds, arpeggio=prog_arpeggio_var.get())
                wav_all.extend(wav_bytes)
            else:
                gap_samples = int(sr * duration_seconds)
                wav_all.extend(b"\x00\x00" * gap_samples)
        play_wav_bytes(bytes(wav_all), sr)

    def preview_selected_chord():
        sel = prog_tree.selection()
        if not sel:
            return
        idx = prog_tree.index(sel[0])
        item = progression[idx]
        bpm = prog_tempo_var.get()
        duration_seconds = 60.0 / bpm * item.get("duration_beats", prog_duration_var.get())
        wav_bytes, sr = generate_wav(item["notes"], duration=duration_seconds, arpeggio=prog_arpeggio_var.get())
        if wav_bytes:
            play_wav_bytes(wav_bytes, sr)

    def export_progression():
        if not progression:
            return
        chord_events = build_chord_events()
        path = filedialog.asksaveasfilename(
            defaultextension=".mid",
            filetypes=[("MIDI files", "*.mid")],
            initialfile="progression.mid",
        )
        if not path:
            return
        key_signature = key_signature_info(key_root_var.get(), key_mode_var.get())
        write_midi_sequence(path, chord_events, prog_tempo_var.get(), prog_velocity_var.get(), key_signature)
        messagebox.showinfo("Export", f"Saved {os.path.basename(path)}")

    def load_progression_midi():
        path = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid *.midi")])
        if not path:
            return
        try:
            chord_events, ticks_per_beat, tempo_bpm, key_sig = parse_midi_file(path)
        except Exception as exc:
            messagebox.showerror("Load MIDI", f"Could not load MIDI: {exc}")
            return
        if not chord_events:
            messagebox.showwarning("Load MIDI", "No chord data found.")
            return

        clear_progression()
        durations = []
        for notes, duration_ticks in chord_events:
            if not notes:
                continue
            duration_beats = duration_ticks / ticks_per_beat if ticks_per_beat else prog_duration_var.get()
            if duration_beats <= 0:
                duration_beats = prog_duration_var.get()
            durations.append(duration_beats)

            root_index, triad_name, ext_flags, alt_flags, extra_intervals = analyze_chord_notes(notes)
            item = {
                "root_index": root_index,
                "triad_name": triad_name,
                "ext_flags": ext_flags,
                "alt_flags": alt_flags,
                "extra_intervals": extra_intervals,
                "extra_abs_notes": [],
                "notes": sorted(notes),
                "duration_beats": duration_beats,
            }
            progression.append(item)

        refresh_progression_display()

        if durations:
            avg_duration = sum(durations) / len(durations)
            prog_duration_var.set(round(avg_duration, 2))

        if tempo_bpm:
            prog_tempo_var.set(tempo_bpm)
        if key_sig:
            key = key_from_signature(key_sig[0], key_sig[1])
            if key:
                key_root_var.set(key[0])
                key_mode_var.set(key[1])

    ttk.Button(actions, text="Add Current", command=add_to_progression).pack(side="left", padx=2)
    ttk.Button(actions, text="Update Selected", command=update_selected).pack(side="left", padx=2)
    ttk.Button(actions, text="Remove", command=remove_selected).pack(side="left", padx=2)
    ttk.Button(actions, text="Move Up", command=lambda: move_selected(-1)).pack(side="left", padx=2)
    ttk.Button(actions, text="Move Down", command=lambda: move_selected(1)).pack(side="left", padx=2)
    ttk.Button(actions, text="Clear", command=clear_progression).pack(side="left", padx=2)

    ttk.Button(playback, text="Preview", command=preview_progression).pack(side="left", padx=2)
    ttk.Button(playback, text="Preview Selected", command=preview_selected_chord).pack(side="left", padx=2)
    ttk.Button(playback, text="Export MIDI", command=export_progression).pack(side="left", padx=2)
    ttk.Button(playback, text="Load MIDI", command=load_progression_midi).pack(side="left", padx=2)

    prog_tree.bind("<Double-1>", lambda _e: preview_selected_chord())

    for var in [root_var, octave_var, octave_shift_var, triad_var, voicing_var, inversion_var, max_notes_var, tempo_var, duration_var, velocity_var, arpeggio_var]:
        var.trace_add("write", refresh_display)
    for var in ext_vars.values():
        var.trace_add("write", refresh_display)
    for var in alt_vars.values():
        var.trace_add("write", refresh_display)
    for var in [key_root_var, key_mode_var, display_mode_var]:
        var.trace_add("write", refresh_display)
        var.trace_add("write", lambda *_: refresh_progression_display())

    refresh_display()


# Override the legacy layout
build_ui = build_ui_compact

if __name__ == "__main__":
    main()
