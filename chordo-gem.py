import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, pygame, time, json
import numpy as np

# Initialize Pygame Mixer safely (macOS can fail if no device is ready)
def init_audio():
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        return True
    except Exception as exc:
        messagebox.showerror(
            "Audio Error",
            f"Unable to initialize audio output.\n\n{exc}\n\n"
            "Check that an output device is available and try again.",
        )
        return False

NOTES_MIDI = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

SCALES = {
    "Major (Ionian)": ([0, 2, 4, 5, 7, 9, 11], ["Major", "Minor", "Minor", "Major", "Major", "Minor", "m7b5"], 0),
    "Natural Minor": ([0, 2, 3, 5, 7, 8, 10], ["Minor", "m7b5", "Major", "Minor", "Minor", "Major", "Major"], 9),
    "Dorian": ([0, 2, 3, 5, 7, 9, 10], ["Minor", "Minor", "Major", "Major", "Minor", "m7b5", "Major"], 2),
    "Phrygian": ([0, 1, 3, 5, 7, 8, 10], ["Minor", "Major", "Major", "Minor", "m7b5", "Major", "Minor"], 4),
    "Lydian": ([0, 2, 4, 6, 7, 9, 11], ["Major", "Major", "Minor", "m7b5", "Major", "Minor", "Minor"], 5),
    "Mixolydian": ([0, 2, 4, 5, 7, 9, 10], ["Major", "Minor", "m7b5", "Major", "Minor", "Minor", "Major"], 7),
    "Locrian": ([0, 1, 3, 5, 6, 8, 10], ["m7b5", "Major", "Minor", "Minor", "Major", "Major", "Minor"], 11),
    "Harmonic Minor": ([0, 2, 3, 5, 7, 8, 11], ["Minor", "m7b5", "Aug", "Minor", "Major", "Major", "dim7"], 9),
    "Melodic Minor": ([0, 2, 3, 5, 7, 9, 11], ["Minor", "Minor", "Aug", "Major", "Major", "m7b5", "m7b5"], 9),
    "Phrygian Dominant": ([0, 1, 4, 5, 7, 8, 10], ["Major", "Major", "m7b5", "Minor", "m7b5", "Major", "Minor"], 4),
    "Major Pentatonic": ([0, 2, 4, 7, 9], ["Major", "Minor", "Minor", "Major", "Major"], 0),
    "Minor Pentatonic": ([0, 3, 5, 7, 10], ["Minor", "Major", "Minor", "Minor", "Major"], 9),
    "Blues Scale": ([0, 3, 5, 6, 7, 10], ["Minor", "Major", "dim", "Major", "Minor", "Major"], 9),
    "Lydian Dominant": ([0, 2, 4, 6, 7, 9, 10], ["Major", "Major", "m7b5", "m7b5", "Minor", "Minor", "Major"], 5),
    "Altered Scale": ([0, 1, 3, 4, 6, 8, 10], ["dim", "Minor", "Minor", "Major", "Major", "Major", "Major"], 1),
    "Whole Tone": ([0, 2, 4, 6, 8, 10], ["Aug", "Aug", "Aug", "Aug", "Aug", "Aug"], 0)
}

CHORD_FORMULAS = {
    "Major": [0, 4, 7], "Minor": [0, 3, 7], "Dim": [0, 3, 6], "Aug": [0, 4, 8],
    "Maj7": [0, 4, 7, 11], "Min7": [0, 3, 7, 10], "Dom7": [0, 4, 7, 10],
    "m7b5": [0, 3, 6, 10], "dim7": [0, 3, 6, 9], "Maj9": [0, 4, 7, 11, 14],
    "add9": [0, 4, 7, 14], "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9],
    "11": [0, 4, 7, 10, 14, 17], "m11": [0, 3, 7, 10, 14, 17],
    "Sus2": [0, 2, 7], "Sus4": [0, 5, 7], "Power": [0, 7, 12],
    "7b9": [0, 4, 7, 10, 13], "7#9": [0, 4, 7, 10, 15], "Maj7#11": [0, 4, 7, 11, 18]
}

def get_smart_note(midi_name, key_context):
    flat_map = {'C#': 'Db', 'D#': 'Eb', 'F#': 'Gb', 'G#': 'Ab', 'A#': 'Bb'}
    if any(k in key_context for k in ["F", "Bb", "Eb", "Ab", "Db", "Gb", "b"]):
        return flat_map.get(midi_name, midi_name)
    return midi_name

def midi_to_hz(midi_note): return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))

def generate_sine_wave(hz, duration=0.4, volume=0.15):
    sample_rate = 44100
    n_samples = int(sample_rate * max(duration, 0.02))
    t = np.linspace(0, duration, n_samples, False)
    fade = np.linspace(1.0, 0.0, n_samples)
    wave = (np.sin(2 * np.pi * hz * t) * volume * fade * 32767).astype(np.int16)
    stereo = np.vstack((wave, wave)).T.copy(order='C')
    return pygame.sndarray.make_sound(stereo)

class ChordEditor(tk.Toplevel):
    def __init__(self, parent, chord_data, index, callback, play_fn, key_context):
        super().__init__(parent)
        self.title(f"Editor: Slot {index+1}"); self.chord_data = chord_data
        self.callback = callback; self.play_fn = play_fn; self.key_context = key_context
        self.geometry("640x950"); self.configure(bg="#1a1a1a")

        header = tk.Frame(self, bg="#111", pady=15); header.pack(fill="x")
        self.chord_display_var = tk.StringVar()
        tk.Label(header, textvariable=self.chord_display_var, bg="#111", fg="#44ff44", font=("Arial", 16, "bold")).pack()
        tk.Button(header, text="🔊 AUDITION", highlightbackground="#3388FF", command=lambda: self.play_fn(self.chord_data)).pack(pady=5)

        bf = tk.Frame(self, bg="#1a1a1a", pady=10); bf.pack(fill="x", padx=20)
        tk.Label(bf, text="Octave:", bg="#1a1a1a", fg="white").pack(side="left")
        self.oct_var = tk.IntVar(value=self.chord_data.get('octave', 4))
        tk.Spinbox(bf, from_=1, to=7, textvariable=self.oct_var, width=5, command=self.force_update).pack(side="left", padx=10)
        
        tk.Label(bf, text="Slash Bass:", bg="#1a1a1a", fg="white").pack(side="left", padx=(20, 0))
        self.slash_var = tk.StringVar(value=self.chord_data.get('slash_bass', "None"))
        opts = ["None"] + [get_smart_note(n, self.key_context) for n in NOTES_MIDI]
        cb = ttk.Combobox(bf, textvariable=self.slash_var, values=opts, width=8, state="readonly")
        cb.pack(side="left", padx=10); cb.bind("<<ComboboxSelected>>", lambda e: self.force_update())

        rf = tk.LabelFrame(self, text="Root Note", bg="#1a1a1a", fg="white", pady=5); rf.pack(fill="x", padx=15, pady=5)
        self.root_btns = {}
        for i, raw_n in enumerate(NOTES_MIDI):
            n = get_smart_note(raw_n, self.key_context)
            b = tk.Button(rf, text=n, width=6, highlightbackground="white", command=lambda note=n: self.update_root(note))
            b.grid(row=i//6, column=i%6, padx=2, pady=2); self.root_btns[n] = b

        mf = tk.LabelFrame(self, text="Interval Matrix", bg="#1a1a1a", fg="white", pady=5); mf.pack(fill="x", padx=15, pady=5)
        self.m_vars = []; self.m_btns = []
        for i in range(24):
            v = tk.BooleanVar(value=(i in self.chord_data['custom_intervals']))
            self.m_vars.append(v)
            c = tk.Checkbutton(mf, text=str(i), variable=v, command=self.on_matrix_click, indicatoron=0, width=4, height=2)
            c.grid(row=i//6, column=i%6, padx=1, pady=1); self.m_btns.append(c)

        qf = tk.LabelFrame(self, text="Chord Library", bg="#1a1a1a", fg="white", pady=10); qf.pack(fill="x", padx=15, pady=5)
        for i, f in enumerate(CHORD_FORMULAS.keys()):
            tk.Button(qf, text=f, font=("Arial", 8), width=10, highlightbackground="white", command=lambda form=f: self.apply_preset(form)).grid(row=i//4, column=i%4, padx=2, pady=2)

        self.refresh(); tk.Button(self, text="CLOSE & SAVE", highlightbackground="#44ff44", command=self.destroy).pack(pady=20)

    def update_root(self, n): self.chord_data['root'] = n; self.force_update()
    def apply_preset(self, form):
        self.chord_data['custom_intervals'] = CHORD_FORMULAS[form].copy(); self.chord_data['formula_name'] = form
        for i in range(24): self.m_vars[i].set(i in self.chord_data['custom_intervals'])
        self.force_update()
    def on_matrix_click(self): self.chord_data['formula_name'] = "Custom"; self.force_update()
    def force_update(self):
        self.chord_data['octave'] = self.oct_var.get(); self.chord_data['slash_bass'] = self.slash_var.get()
        self.chord_data['custom_intervals'] = [i for i, v in enumerate(self.m_vars) if v.get()]
        self.refresh(); self.callback()
    def refresh(self):
        root = self.chord_data['root']; formula = self.chord_data.get('formula_name', 'Custom'); slash = self.chord_data.get('slash_bass', 'None')
        mapping = {'Db':'C#','Eb':'D#','Gb':'F#','Ab':'G#','Bb':'A#'}
        r_idx = NOTES_MIDI.index(mapping.get(root, root))
        note_names = [get_smart_note(NOTES_MIDI[(r_idx + i) % 12], self.key_context) for i in sorted(self.chord_data['custom_intervals'])]
        display_text = f"{root} {formula}"
        if slash != "None": display_text += f"/{slash}"
        display_text += f"\n({', '.join(note_names)})"
        self.chord_display_var.set(display_text)
        for n, b in self.root_btns.items(): b.config(highlightbackground="#44ff44" if self.chord_data['root'] == n else "white")

class ProChordSequencer:
    def __init__(self, root):
        self.root = root; self.root.title("Chord Architect Ultra 9.9"); self.root.configure(bg="#1a1a1a")
        self.root.tk.call("tk", "scaling", 1.25)
        self.selected_idx = 0; self.bpm = tk.IntVar(value=120); self.is_playing = False
        self.current_key = tk.StringVar(value="C"); self.current_scale = tk.StringVar(value="Major (Ionian)")
        self.lock_key_var = tk.BooleanVar(value=True); self.prev_scale_offset = 0 
        
        roots = ['C', 'D', 'E', 'F', 'G', 'A', 'B', 'C']
        quals = ['Major', 'Minor', 'Minor', 'Major', 'Major', 'Minor', 'm7b5', 'Major']
        self.chord_bank = [{'root': roots[i], 'octave': 4, 'formula_name': quals[i], 'custom_intervals': CHORD_FORMULAS.get(quals[i], [0,4,7]).copy(), 'color': c, 'slash_bass': 'None'} for i, c in enumerate(["#FF5733", "#33FF57", "#3357FF", "#F333FF", "#FF33A1", "#33FFF3", "#F3FF33", "#FFA500"])]
        
        self.steps = [None] * 16
        self.step_rhythms = [1.0] * 16 
        
        self.setup_ui(); self.render_sequencer(); self.render_bank()

    def setup_ui(self):
        ctrl = tk.Frame(self.root, bg="#111", pady=10); ctrl.pack(fill="x")
        ttk.Combobox(ctrl, textvariable=self.current_key, values=NOTES_MIDI, width=4).pack(side="left", padx=10)
        self.scale_cb = ttk.Combobox(ctrl, textvariable=self.current_scale, values=list(SCALES.keys()), width=18)
        self.scale_cb.pack(side="left"); self.scale_cb.bind("<<ComboboxSelected>>", self.on_scale_change)
        
        tk.Checkbutton(ctrl, text="Lock Key", variable=self.lock_key_var, bg="#111", fg="white", selectcolor="black").pack(side="left", padx=5)

        tk.Label(ctrl, text="BPM", bg="#111", fg="#44ff44", font=("Arial", 9, "bold")).pack(side="left", padx=(10,0))
        tk.Spinbox(ctrl, from_=40, to=240, textvariable=self.bpm, width=4, bg="black", fg="white").pack(side="left", padx=5)
        tk.Button(ctrl, text="SAVE", command=self.save_p, highlightbackground="#0044CC", width=5).pack(side="left", padx=2)
        tk.Button(ctrl, text="LOAD", command=self.load_p, highlightbackground="#CC8800", width=5).pack(side="left", padx=2)
        tk.Button(ctrl, text="CLEAR", command=self.clear_s, highlightbackground="#AA0000", width=5).pack(side="left", padx=2)
        self.play_btn = tk.Button(ctrl, text="PLAY", command=self.toggle_p, highlightbackground="#22CC22", width=8); self.play_btn.pack(side="right", padx=15)

        self.indicator_var = tk.StringVar(value="Brush: Chord 1"); tk.Label(self.root, textvariable=self.indicator_var, bg="#1a1a1a", fg="#44ff44", font=("Arial", 10, "bold")).pack(pady=5)
        self.bank_frame = tk.Frame(self.root, bg="#1a1a1a", pady=10); self.bank_frame.pack(fill="x")
        self.seq_frame = tk.Frame(self.root, bg="#1a1a1a", pady=20); self.seq_frame.pack()

    def on_scale_change(self, event):
        if not self.lock_key_var.get(): 
            self.prev_scale_offset = SCALES[self.current_scale.get()][2]
            return
        mapping = {'Db':'C#','Eb':'D#','Gb':'F#','Ab':'G#','Bb':'A#'}
        curr_k = mapping.get(self.current_key.get(), self.current_key.get())
        curr_idx = NOTES_MIDI.index(curr_k)
        parent_major_idx = (curr_idx - self.prev_scale_offset) % 12
        new_offset = SCALES[self.current_scale.get()][2]
        new_root_idx = (parent_major_idx + new_offset) % 12
        self.current_key.set(get_smart_note(NOTES_MIDI[new_root_idx], self.current_key.get()))
        self.prev_scale_offset = new_offset; self.render_bank()

    def select_c(self, i): self.selected_idx = i; self.indicator_var.set(f"Brush: Chord {i+1} ({self.chord_bank[i]['root']})"); self.render_bank()

    def render_bank(self):
        for w in self.bank_frame.winfo_children(): w.destroy()
        for i, c in enumerate(self.chord_bank):
            active = self.selected_idx == i
            f = tk.Frame(self.bank_frame, bg="white" if active else "#1a1a1a", padx=2, pady=2); f.pack(side="left", padx=2)
            name = c['root'] if c['slash_bass'] == "None" else f"{c['root']}/{c['slash_bass']}"
            tk.Button(f, text=f"{name}\n{c['formula_name']}", highlightbackground=c['color'], width=7, height=3, command=lambda idx=i: self.select_c(idx)).pack()
            tk.Button(f, text="EDIT", font=("Arial", 8), command=lambda idx=i: self.open_edit(idx)).pack(fill="x")

    def paint(self, i): self.steps[i] = self.selected_idx if self.steps[i] != self.selected_idx else None; self.render_sequencer()

    def update_rhythm(self, i, val): self.step_rhythms[i] = float(val); self.render_sequencer()

    def render_sequencer(self):
        for w in self.seq_frame.winfo_children(): w.destroy()
        for c in range(8): self.seq_frame.grid_columnconfigure(c, weight=1, minsize=80)
        skip_count = 0
        for i in range(16):
            if skip_count > 0: skip_count -= 1; continue
            dur = self.step_rhythms[i]; c_span = max(1, int(dur))
            if i % 8 + c_span > 8: c_span = 8 - (i % 8)
            f = tk.Frame(self.seq_frame, bg="#1a1a1a"); f.grid(row=i//8, column=i%8, columnspan=c_span, sticky="nsew", padx=1, pady=5)
            c_idx = self.steps[i]; color = self.chord_bank[c_idx]['color'] if c_idx is not None else "#333333"
            btn = tk.Label(f, bg=color, relief="raised", bd=2, height=3); btn.pack(fill="both", expand=True)
            btn.bind("<Button-1>", lambda e, idx=i: self.paint(idx))
            dur_cb = ttk.Combobox(f, values=["0.5", "1.0", "2.0", "4.0"], width=4, state="readonly"); dur_cb.set(str(dur)); dur_cb.pack()
            dur_cb.bind("<<ComboboxSelected>>", lambda e, idx=i, cb=dur_cb: self.update_rhythm(idx, cb.get()))
            skip_count = c_span - 1

    def open_edit(self, i): ChordEditor(self.root, self.chord_bank[i], i, self.render_bank, self.play_c, self.current_key.get())
    def clear_s(self): self.steps = [None] * 16; self.render_sequencer()
    def save_p(self):
        p = filedialog.asksaveasfilename(defaultextension=".json")
        if p: json.dump({"bank":self.chord_bank, "steps":self.steps, "rhythms":self.step_rhythms, "key":self.current_key.get(), "scale":self.current_scale.get(), "bpm":self.bpm.get()}, open(p, 'w'))
    def load_p(self):
        p = filedialog.askopenfilename()
        if p: 
            d = json.load(open(p, 'r'))
            self.chord_bank=d['bank']; self.steps=d['steps']; self.step_rhythms=d.get('rhythms', [1.0]*16)
            self.current_key.set(d.get('key','C')); self.current_scale.set(d.get('scale','Major (Ionian)'))
            self.bpm.set(d.get('bpm', 120)); self.render_bank(); self.render_sequencer()
    
    def toggle_p(self):
        self.is_playing = not self.is_playing; self.play_btn.config(text="STOP" if self.is_playing else "PLAY")
        if self.is_playing: threading.Thread(target=self.loop, daemon=True).start()
        
    def loop(self):
        idx = 0
        next_note_time = time.perf_counter() # High-precision start time
        while self.is_playing:
            current_step = idx % 16
            ci = self.steps[current_step]
            dur_mult = self.step_rhythms[current_step]
            
            # BPM MATH AUDIT:
            # Beat duration = 60 / BPM. 
            # 120 BPM = 0.5s per Quarter Note (1.0).
            # 120 BPM = 2.0s per Whole Note (4.0).
            beat_duration = 60.0 / max(self.bpm.get(), 1)
            actual_time = beat_duration * dur_mult

            if ci is not None: 
                threading.Thread(target=self.play_c, args=(self.chord_bank[ci], actual_time), daemon=True).start()
            
            # PRECISION CLOCK: Calculate when the next beat SHOULD happen
            next_note_time += actual_time
            
            # Sleep only for the remaining time to prevent drift
            sleep_time = next_note_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            idx += int(max(1, dur_mult)) if dur_mult >= 1 else 1

    def play_c(self, chord, duration=0.4):
        if not pygame.mixer.get_init():
            return
        mapping = {'Db':'C#','Eb':'D#','Gb':'F#','Ab':'G#','Bb':'A#'}
        root_idx = NOTES_MIDI.index(mapping.get(chord['root'], chord['root'])) + (chord['octave']*12)
        notes = [root_idx + iv for iv in chord['custom_intervals']]
        if chord['slash_bass'] != "None": notes.append(NOTES_MIDI.index(mapping.get(chord['slash_bass'], chord['slash_bass'])) + (chord['octave']-1)*12)
        for n in notes: generate_sine_wave(midi_to_hz(n), duration=duration).play()

if __name__ == "__main__":
    root = tk.Tk()
    if init_audio():
        app = ProChordSequencer(root)
        root.mainloop()
