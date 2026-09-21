"""Rhythm-game test player embedded in the ChartGen window.

Loads an osu!mania .osz produced by chartgen.py and lets you play it right away.
DJMAX-style rules: PERFECT / GREAT / GOOD / MISS judgments,
FEVER gauge (46 hits per level, up to 5, reset by a miss), ring / classic notes,
ripple / burst hit effects, ESC = pause, R = restart.

`Session` holds all scoring logic with no GUI or audio, so it can be tested alone.
"""
import json
import math
import os
import shutil
import tempfile
import time
import tkinter as tk
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

import theme as T
from i18n import t as tr          # `t` is a time variable throughout this module

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

BASE_WINDOWS = (0.045, 0.090, 0.135)          # PERFECT / GREAT / GOOD, seconds
JUDGES = (("PERFECT", T.CYAN, 1.0), ("GREAT", "#FF8CEB", 0.75), ("GOOD", T.GREEN, 0.4))
MISS_COLOR = T.RED
FEVER_HITS = 46
FEVER_MAX = 5
TAIL_LEEWAY = 0.12                            # releasing this early before a hold ends still counts

DEFAULT_KEYS = {                              # Windows virtual-key codes per lane count
    1: [32],
    2: [70, 74],
    3: [70, 32, 74],
    4: [65, 83, 186, 222],                    # A S ; '   (the mod's default)
    5: [65, 83, 32, 186, 222],
    6: [83, 68, 70, 74, 75, 76],
    7: [83, 68, 70, 32, 74, 75, 76],
    8: [65, 83, 68, 70, 74, 75, 76, 186],
    9: [65, 83, 68, 70, 32, 74, 75, 76, 186],
}
KEY_NAMES = {32: "SPACE", 186: ";", 187: "=", 188: ",", 189: "-", 190: ".", 191: "/", 192: "`",
             219: "[", 220: "\\", 221: "]", 222: "'", 13: "ENTER", 16: "SHIFT"}

DEFAULT_CFG = dict(speed=1.0, offset_ms=0, volume=70, note_style="ring", effect="ripple",
                   judge_scale=1.0, countdown=3, auto=False, keys={}, lang=None)


def key_label(code):
    if code in KEY_NAMES:
        return KEY_NAMES[code]
    if 96 <= code <= 105:
        return f"NUM{code - 96}"
    if 48 <= code <= 90:
        return chr(code)
    return f"#{code}"


# ------------------------------------------------------------------ chart

@dataclass
class Note:
    lane: int
    t: float
    end: float = 0.0
    state: str = "wait"       # wait | hold | done | miss

    @property
    def is_ln(self):
        return self.end > self.t


@dataclass
class Chart:
    version: str
    keys: int
    title: str
    artist: str
    notes: list


def parse_osu(text):
    section, meta, keys, raw = "", {}, 4, []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line
        elif section == "[Difficulty]" and line.startswith("CircleSize:"):
            keys = int(float(line.split(":", 1)[1]))
        elif section == "[Metadata]" and ":" in line:
            k, v = line.split(":", 1)
            meta[k] = v
        elif section == "[HitObjects]" and line:
            p = line.split(",")
            x, t, typ = int(p[0]), int(p[2]) / 1000, int(p[3])
            end = int(p[5].split(":")[0]) / 1000 if typ & 128 else 0.0
            raw.append((x, t, end))
    notes = [Note(min(keys - 1, x * keys // 512), t, end) for x, t, end in raw]
    notes.sort(key=lambda n: (n.t, n.lane))
    return Chart(meta.get("Version", "?"), keys, meta.get("Title", ""), meta.get("Artist", ""), notes)


# ------------------------------------------------------------------ scoring core

@dataclass
class Event:
    kind: str                 # 'judge' | 'fever'
    lane: int = 0
    name: str = ""
    level: int = 0


class Session:
    """Judgment, combo, score and FEVER gauge. Times are song seconds."""

    def __init__(self, notes, keys, judge_scale=1.0, auto=False):
        self.notes = [Note(n.lane, n.t, n.end) for n in notes]
        self.keys = keys
        self.auto = auto
        self.win = tuple(w * judge_scale for w in BASE_WINDOWS)
        self.lanes = [[n for n in self.notes if n.lane == i] for i in range(keys)]
        self.ptr = [0] * keys
        self.hold = [None] * keys
        self.counts = {"PERFECT": 0, "GREAT": 0, "GOOD": 0, "MISS": 0}
        self.units = sum(2 if n.is_ln else 1 for n in self.notes)
        self.points = 0.0
        self.judged = 0
        self.combo = self.max_combo = 0
        self.fever = 0
        self.chain = 0             # hits since the last FEVER level-up (integer: no float drift)
        self.gauge = 0.0
        self.events = []
        self.end_time = max((max(n.t, n.end) for n in self.notes), default=0.0)

    # -- internals
    def _judge(self, name, lane):
        self.counts[name] += 1
        self.judged += 1
        if name == "MISS":
            self.combo = 0
            self.fever = 0
            self.chain = 0
            self.gauge = 0.0
        else:
            self.points += next(w for j, _, w in JUDGES if j == name)
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.chain += 1
            if self.chain >= FEVER_HITS:
                self.chain = 0
                if self.fever < FEVER_MAX:
                    self.fever += 1
                    self.events.append(Event("fever", level=self.fever))
            self.gauge = self.chain / FEVER_HITS
        self.events.append(Event("judge", lane, name))

    def _next(self, lane):
        arr = self.lanes[lane]
        while self.ptr[lane] < len(arr) and arr[self.ptr[lane]].state != "wait":
            self.ptr[lane] += 1
        return arr[self.ptr[lane]] if self.ptr[lane] < len(arr) else None

    def _grade(self, dt):
        for (name, _, _), w in zip(JUDGES, self.win):
            if dt <= w:
                return name
        return None

    # -- input
    def press(self, lane, t):
        n = self._next(lane)
        if n is None:
            return
        dt = t - n.t
        if dt < -self.win[2]:
            return                                  # too early: ignored
        name = self._grade(abs(dt))
        if name is None:
            return
        self._judge(name, lane)
        if n.is_ln:
            n.state = "hold"
            self.hold[lane] = n
        else:
            n.state = "done"

    def release(self, lane, t):
        n = self.hold[lane]
        if n is None:
            return
        self._judge("PERFECT" if t >= n.end - TAIL_LEEWAY else "MISS", lane)
        n.state = "done"
        self.hold[lane] = None

    def update(self, t):
        for lane in range(self.keys):
            if self.auto:
                while True:
                    h = self.hold[lane]
                    if h is not None and t >= h.end:
                        self.release(lane, h.end)
                        continue
                    n = self._next(lane) if h is None else None
                    if n is None or t < n.t:
                        break
                    self.press(lane, n.t)
                continue
            n = self._next(lane)
            while n is not None and t - n.t > self.win[2]:
                n.state = "miss"
                for _ in range(2 if n.is_ln else 1):
                    self._judge("MISS", lane)
                n = self._next(lane)
            h = self.hold[lane]
            if h is not None and t >= h.end:        # held all the way through
                self.release(lane, t)

    # -- results
    def finished(self, t):
        return (all(n.state in ("done", "miss") for n in self.notes)
                and all(h is None for h in self.hold)) or t > self.end_time + 1.5

    def accuracy(self):
        """Over the notes judged so far (score uses the whole chart)."""
        return 100.0 * self.points / self.judged if self.judged else 100.0

    def score(self):
        return int(round(1_000_000 * self.points / self.units)) if self.units else 1_000_000

    def grade(self):
        c = self.counts
        if c["MISS"] == 0 and c["GREAT"] == 0 and c["GOOD"] == 0:
            return "PERFECT PLAY"
        if c["MISS"] == 0:
            return "FULL COMBO"
        return "CLEAR"


# ------------------------------------------------------------------ widget

class GamePanel(ttk.Frame):
    def __init__(self, master, cfg_path, on_status=None):
        super().__init__(master)
        self.cfg_path = Path(cfg_path)
        self.on_status = on_status or (lambda key, **kw: None)     # on_status(text_key, **format_args)
        self._labels = []          # (widget, option, i18n key) re-applied by relabel()
        self.cfg = self._load_cfg()
        self.charts, self.chart, self.tmp = [], None, None
        self.audio_path = None
        self.sess = None
        self.state = "idle"        # idle | countdown | playing | paused | result
        self.t0 = self.pause_at = 0.0
        self.music_on = False
        self.pressed = set()
        self.effects = []          # (wall_time, lane, name, kind)
        self.last_judge = None     # (name, wall_time)
        self.banner = None         # (text, wall_time)
        self.cw = self.ch = 1
        self.pg = None
        self._save_job = None
        self._build()
        self.winfo_toplevel().bind_all("<KeyPress>", self._key_down, add="+")
        self.winfo_toplevel().bind_all("<KeyRelease>", self._key_up, add="+")
        self.bind("<Destroy>", self._on_destroy)
        self._tick()

    # ---------------------------------------------------------- settings
    def _load_cfg(self):
        cfg = dict(DEFAULT_CFG)
        try:
            cfg.update(json.loads(self.cfg_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        return cfg

    def _save_cfg_later(self):
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(500, self._save_cfg)

    def _save_cfg(self):
        self._save_job = None
        try:
            self.cfg_path.write_text(json.dumps(self.cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _keys_for(self, n):
        saved = self.cfg.get("keys", {}).get(str(n))
        if saved and len(saved) == n:
            return saved
        return DEFAULT_KEYS.get(n) or [65 + i for i in range(n)]

    # ---------------------------------------------------------- layout
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        top.columnconfigure(0, weight=1)
        def reg(widget, key, opt="text"):
            self._labels.append((widget, opt, key))
            return widget

        self.song_lbl = ttk.Label(top, style="Song.TLabel")
        self.song_lbl.grid(row=0, column=0, sticky="w")
        self.diff_var = tk.StringVar()
        self.diff_box = ttk.Combobox(top, textvariable=self.diff_var, state="readonly", width=22, takefocus=0)
        self.diff_box.grid(row=0, column=1, padx=6)
        self.diff_box.bind("<<ComboboxSelected>>", lambda _e: self._select_chart(self.diff_box.current()))
        self.start_btn = ttk.Button(top, width=10, command=self.start, takefocus=0)
        self.start_btn.grid(row=0, column=2)
        self.pause_btn = ttk.Button(top, text="II", width=4, command=self.toggle_pause, takefocus=0)
        self.pause_btn.grid(row=0, column=3, padx=4)
        self.stop_btn = ttk.Button(top, text="■", width=4, command=self.stop, takefocus=0)
        self.stop_btn.grid(row=0, column=4)

        self.canvas = tk.Canvas(self, bg=T.BG, highlightthickness=1, highlightbackground=T.BORDER,
                                takefocus=1)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", lambda _e: self.canvas.focus_set())

        s = ttk.Frame(self)
        s.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
        for c in (1, 4, 7):
            s.columnconfigure(c, weight=1)
        self.v_speed = tk.DoubleVar(value=self.cfg["speed"])
        self.v_vol = tk.DoubleVar(value=self.cfg["volume"])
        self.v_judge = tk.DoubleVar(value=self.cfg["judge_scale"])
        self.v_offset = tk.IntVar(value=self.cfg["offset_ms"])
        self.v_count = tk.IntVar(value=self.cfg["countdown"])
        self.v_auto = tk.BooleanVar(value=self.cfg["auto"])
        self.v_note = tk.StringVar()
        self.v_fx = tk.StringVar()

        def scale(row, col, label_key, var, lo, hi, key, fmt):
            reg(ttk.Label(s), label_key).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=2)
            lbl = ttk.Label(s, width=6, style="Muted.TLabel")
            sc = ttk.Scale(s, from_=lo, to=hi, variable=var, takefocus=0,
                           command=lambda _v, k=key, v=var, l=lbl, f=fmt: self._scale_changed(k, v, l, f))
            sc.grid(row=row, column=col + 1, sticky="ew", padx=4)
            lbl.grid(row=row, column=col + 2, padx=(0, 12))
            self._scale_changed(key, var, lbl, fmt, save=False)

        scale(0, 0, "game.speed", self.v_speed, 0.5, 3.0, "speed", lambda v: f"x{v:.2f}")
        scale(0, 3, "game.volume", self.v_vol, 0, 100, "volume", lambda v: f"{v:.0f}%")
        scale(0, 6, "game.judge", self.v_judge, 1.5, 0.6, "judge_scale", lambda v: f"x{v:.2f}")

        reg(ttk.Label(s), "game.sync").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(s, from_=-300, to=300, increment=5, width=6, textvariable=self.v_offset, takefocus=0,
                    command=self._spin_changed).grid(row=1, column=1, sticky="w", padx=4)
        reg(ttk.Label(s), "game.countdown").grid(row=1, column=3, sticky="w")
        ttk.Spinbox(s, from_=0, to=5, width=4, textvariable=self.v_count, takefocus=0,
                    command=self._spin_changed).grid(row=1, column=4, sticky="w", padx=4)
        reg(ttk.Checkbutton(s, variable=self.v_auto, takefocus=0, command=self._spin_changed),
            "game.auto").grid(row=1, column=6, sticky="w")

        reg(ttk.Label(s), "game.note_shape").grid(row=2, column=0, sticky="w", pady=2)
        self.note_box = ttk.Combobox(s, textvariable=self.v_note, state="readonly", width=12, takefocus=0)
        self.note_box.grid(row=2, column=1, sticky="w", padx=4)
        self.note_box.bind("<<ComboboxSelected>>", lambda _e: self._spin_changed())
        reg(ttk.Label(s), "game.effect").grid(row=2, column=3, sticky="w")
        self.fx_box = ttk.Combobox(s, textvariable=self.v_fx, state="readonly", width=14, takefocus=0)
        self.fx_box.grid(row=2, column=4, sticky="w", padx=4)
        self.fx_box.bind("<<ComboboxSelected>>", lambda _e: self._spin_changed())
        reg(ttk.Button(s, command=self._rebind, takefocus=0), "game.keyset").grid(row=2, column=6, sticky="w")
        self.key_lbl = ttk.Label(s, text="", style="Muted.TLabel")
        self.key_lbl.grid(row=2, column=7, columnspan=2, sticky="w", padx=6)
        reg(ttk.Label(s, style="Muted.TLabel"), "game.hint").grid(
            row=3, column=0, columnspan=9, sticky="w", pady=(4, 0))
        self.relabel()

    def relabel(self):
        """Apply the current language to every text in the panel (also called when it changes)."""
        for widget, opt, key in self._labels:
            widget.configure(**{opt: tr(key)})
        self.note_box.configure(values=[tr("note.ring"), tr("note.classic")])
        self.v_note.set(tr("note.ring") if self.cfg["note_style"] == "ring" else tr("note.classic"))
        self.fx_box.configure(values=[tr("fx.ripple"), tr("fx.burst")])
        self.v_fx.set(tr("fx.ripple") if self.cfg["effect"] == "ripple" else tr("fx.burst"))
        if self.chart is None:
            self.song_lbl.configure(text=tr("game.placeholder"))
        else:
            cur = self.diff_box.current()
            self.diff_box.configure(values=[tr("game.diff_item", version=c.version, n=len(c.notes))
                                            for c in self.charts])
            if cur >= 0:
                self.diff_box.current(cur)
        for box in (self.diff_box, self.note_box, self.fx_box):     # popdown lists keep the old font otherwise
            self.tk.call("destroy", f"{box}.popdown")
        self._refresh_buttons()
        self._dirty()

    def _scale_changed(self, key, var, lbl, fmt, save=True):
        v = var.get()
        lbl.configure(text=fmt(v))
        self.cfg[key] = round(v, 3)
        if key == "volume" and self.pg is not None:
            self.pg.mixer.music.set_volume(v / 100)
        if save:
            self._save_cfg_later()
            self._dirty()

    def _spin_changed(self):
        try:
            self.cfg["offset_ms"] = int(self.v_offset.get())
            self.cfg["countdown"] = max(0, int(self.v_count.get()))
        except (tk.TclError, ValueError):
            pass
        self.cfg["auto"] = bool(self.v_auto.get())
        self.cfg["note_style"] = "ring" if self.note_box.current() == 0 else "classic"
        self.cfg["effect"] = "ripple" if self.fx_box.current() == 0 else "burst"
        self._save_cfg_later()
        self._dirty()

    def _refresh_buttons(self):
        have = self.chart is not None
        self.start_btn.configure(state="normal" if have else "disabled",
                                 text=tr("game.again") if self.state != "idle" else tr("game.start"))
        self.pause_btn.configure(state="normal" if self.state in ("playing", "countdown", "paused") else "disabled")
        self.stop_btn.configure(state="normal" if self.state != "idle" else "disabled")
        if have:
            keys = self._keys_for(self.chart.keys)
            self.key_lbl.configure(text=tr("game.keys", keys=" ".join(key_label(k) for k in keys)))

    # ---------------------------------------------------------- chart loading
    def load_osz(self, path):
        path = Path(path)
        try:
            with zipfile.ZipFile(path) as z:
                osus = sorted(n for n in z.namelist() if n.lower().endswith(".osu"))
                audio = next((n for n in z.namelist() if n.lower().endswith((".mp3", ".ogg", ".wav"))), None)
                if not osus or audio is None:
                    raise ValueError(tr("game.err_osz"))
                charts = sorted((parse_osu(z.read(n).decode("utf-8", "replace")) for n in osus),
                                key=lambda c: len(c.notes))          # easiest first
                self._drop_tmp()
                self.tmp = tempfile.mkdtemp(prefix="chartgen_")
                self.audio_path = str(Path(self.tmp) / ("audio" + Path(audio).suffix.lower()))
                with z.open(audio) as src, open(self.audio_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            self.on_status("game.st_load_fail", err=e)
            return False
        self.stop()
        self.charts = charts
        self.diff_box.configure(values=[tr("game.diff_item", version=c.version, n=len(c.notes)) for c in charts])
        self.diff_box.current(0)
        self._select_chart(0)
        self.on_status("game.st_loaded", name=path.name)
        return True

    def _select_chart(self, i):
        self.stop()
        self.chart = self.charts[i]
        title = self.chart.title or "?"
        self.song_lbl.configure(text=f"{title}  ·  {self.chart.artist}")
        self._refresh_buttons()
        self._dirty()

    def _drop_tmp(self):
        if self.pg is not None:
            try:
                self.pg.mixer.music.unload()
            except Exception:  # noqa: BLE001
                pass
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None

    def _on_destroy(self, e):
        if e.widget is self:
            self._drop_tmp()
            if self.pg is not None:
                self.pg.mixer.quit()

    # ---------------------------------------------------------- audio
    def _audio(self):
        if self.pg is None:
            try:
                import pygame
                pygame.mixer.init(frequency=44100)
                self.pg = pygame
            except Exception as e:  # noqa: BLE001 - missing pygame / no output device
                self.on_status("game.st_audio_fail", err=e)
                return None
        return self.pg

    # ---------------------------------------------------------- game flow
    def start(self):
        if self.chart is None:
            return
        pg = self._audio()
        if pg is None:
            return
        try:
            pg.mixer.music.load(self.audio_path)
        except Exception as e:  # noqa: BLE001
            self.on_status("game.st_play_fail", err=e)
            return
        pg.mixer.music.set_volume(self.cfg["volume"] / 100)
        pg.mixer.music.stop()
        self.sess = Session(self.chart.notes, self.chart.keys, self.cfg["judge_scale"], self.cfg["auto"])
        self.pressed.clear()
        self.effects.clear()
        self.last_judge = self.banner = None
        self.music_on = False
        self.t0 = time.perf_counter() + self.cfg["countdown"]
        self.state = "countdown"
        self._refresh_buttons()
        self.canvas.focus_set()

    def stop(self):
        if self.pg is not None:
            self.pg.mixer.music.stop()
        self.state = "idle"
        self.sess = None
        self.pressed.clear()
        self._refresh_buttons()
        self._dirty()

    def toggle_pause(self):
        if self.state in ("playing", "countdown"):
            self.pause_at = time.perf_counter()
            if self.music_on:
                self.pg.mixer.music.pause()
            self._paused_from = self.state
            self.state = "paused"
        elif self.state == "paused":
            self.t0 += time.perf_counter() - self.pause_at
            if self.music_on:
                self.pg.mixer.music.unpause()
            self.state = self._paused_from
            self.canvas.focus_set()
        self._refresh_buttons()

    def _finish(self):
        if self.pg is not None:
            self.pg.mixer.music.fadeout(400)
        self.state = "result"
        self._refresh_buttons()

    def _song_time(self):
        now = self.pause_at if self.state == "paused" else time.perf_counter()
        return now - self.t0 - self.cfg["offset_ms"] / 1000

    # ---------------------------------------------------------- input
    def _lane_of(self, code):
        if self.chart is None:
            return None
        keys = self._keys_for(self.chart.keys)
        return keys.index(code) if code in keys else None

    def _key_down(self, e):
        if self.state == "idle":
            return
        if e.keysym == "Escape":
            if self.state in ("playing", "countdown", "paused"):
                self.toggle_pause()
            return
        if e.keysym in ("r", "R") and self.state in ("playing", "countdown", "paused", "result"):
            self.start()
            return
        if self.state == "paused":
            if e.keysym == "Return":
                self.toggle_pause()
            elif e.keysym in ("q", "Q"):
                self.stop()
            return
        lane = self._lane_of(e.keycode)
        if lane is None or lane in self.pressed:
            return
        self.pressed.add(lane)
        if self.state == "playing" and not self.sess.auto:
            self.sess.press(lane, self._song_time())

    def _key_up(self, e):
        lane = self._lane_of(e.keycode)
        if lane is None:
            return
        self.pressed.discard(lane)
        if self.state == "playing" and self.sess is not None and not self.sess.auto:
            self.sess.release(lane, self._song_time())

    def _rebind(self):
        if self.chart is None:
            self.on_status("game.st_need_chart")
            return
        self.stop()
        n = self.chart.keys
        new = []
        dlg = tk.Toplevel(self)
        dlg.title(tr("keydlg.title"))
        dlg.configure(bg=T.BG)
        dlg.transient(self.winfo_toplevel())
        dlg.geometry("340x130")
        msg = ttk.Label(dlg, style="Song.TLabel")
        msg.pack(pady=(24, 4))
        ttk.Label(dlg, text=tr("keydlg.cancel"), style="Muted.TLabel").pack()

        def prompt():
            msg.configure(text=tr("keydlg.prompt", i=len(new) + 1, n=n))

        def on_key(ev):
            if ev.keysym == "Escape":
                dlg.destroy()
                return
            if ev.keycode in new:
                return
            new.append(ev.keycode)
            if len(new) == n:
                self.cfg.setdefault("keys", {})[str(n)] = new
                self._save_cfg_later()
                dlg.destroy()
                self._refresh_buttons()
                self._dirty()
            else:
                prompt()

        prompt()
        dlg.bind("<KeyPress>", on_key)
        dlg.grab_set()
        dlg.focus_force()

    # ---------------------------------------------------------- frame loop
    def _dirty(self):
        self._needs_draw = True

    _needs_draw = True

    def _tick(self):
        try:
            if self.state in ("countdown", "playing"):
                self._advance()
            if self.state != "idle" or self._needs_draw:
                self._draw()
                self._needs_draw = False
        except tk.TclError:
            return
        self.after(10, self._tick)

    def _advance(self):
        t = self._song_time() + self.cfg["offset_ms"] / 1000   # raw clock for the countdown
        if self.state == "countdown":
            if t < 0:
                return
            self.pg.mixer.music.play()
            self.music_on = True
            self.t0 = time.perf_counter()
            self.state = "playing"
        song_t = self._song_time()
        self.sess.update(song_t)
        now = time.perf_counter()
        for ev in self.sess.events:
            if ev.kind == "judge":
                self.last_judge = (ev.name, now)
                if ev.name != "MISS":
                    self.effects.append((now, ev.lane, ev.name, self.cfg["effect"]))
            else:
                self.banner = (f"FEVER  x{ev.level}", now)
        self.sess.events.clear()
        if self.sess.finished(song_t):
            self._finish()

    # ---------------------------------------------------------- drawing
    def _on_resize(self, e):
        self.cw, self.ch = e.width, e.height
        self._dirty()

    def _geometry(self):
        keys = self.chart.keys if self.chart else 4
        lane_w = max(30, min(92, (self.cw * 0.72) / keys))
        fw = lane_w * keys
        return keys, lane_w, (self.cw - fw) / 2, fw, self.ch - 120, 78

    def _lane_color(self, i, keys):
        if keys % 2 == 1 and i == keys // 2:
            return T.LPINK
        return T.PINK if (min(i, keys - 1 - i) % 2 == 0) else T.LAV

    def _draw(self):
        c = self.canvas
        c.delete("all")
        w, h = self.cw, self.ch
        keys, lw, x0, fw, jy, top = self._geometry()
        c.create_rectangle(0, 0, w, h, fill=T.BG, outline="")
        c.create_rectangle(x0, 0, x0 + fw, h, fill="#160F19", outline="")
        for i in range(keys + 1):
            c.create_line(x0 + i * lw, 0, x0 + i * lw, h, fill="#342030")
        c.create_line(x0, 0, x0, h, fill=T.PINK_DEEP, width=2)
        c.create_line(x0 + fw, 0, x0 + fw, h, fill=T.PINK_DEEP, width=2)
        c.create_rectangle(x0, jy, x0 + fw, h, fill="#100B12", outline="")
        c.create_line(x0, jy, x0 + fw, jy, fill=T.PINK, width=3)

        if self.chart is None:
            c.create_text(w / 2, h / 2, text=tr("cv.load_hint"), fill=T.MUTED,
                          font=T.f(11))
            return
        klist = self._keys_for(keys)
        for i in range(keys):
            lx = x0 + i * lw
            col = self._lane_color(i, keys)
            down = i in self.pressed
            if down:
                c.create_rectangle(lx, jy - 110, lx + lw, jy, fill=col, stipple="gray25", outline="")
            c.create_rectangle(lx + 4, jy + 12, lx + lw - 4, jy + 44, fill=col if down else T.PANEL2,
                               outline=col, width=2)
            c.create_text(lx + lw / 2, jy + 28, text=key_label(klist[i]), fill="white" if down else T.MUTED,
                          font=T.f(8, True))

        if self.sess is None:
            c.create_text(w / 2, top + 60, text=f"{self.chart.keys}K  ·  {self.chart.version}", fill=T.LPINK,
                          font=T.f(16, True))
            c.create_text(w / 2, top + 92, text=tr("cv.press_start"), fill=T.MUTED, font=T.f(11))
            return

        t = self._song_time()
        pps = (jy - top) / (1.6 / max(self.cfg["speed"], 0.1))
        ring = self.cfg["note_style"] == "ring"
        for n in self.sess.notes:
            if n.state == "done" and not n.is_ln:
                continue
            y = jy - (n.t - t) * pps
            ytail = jy - (n.end - t) * pps if n.is_ln else y
            if n.state == "done" or ytail > h + 30 or y < top - 40 and ytail < top - 40:
                continue
            if y > h + 30 and n.state != "hold":
                continue
            lx = x0 + n.lane * lw
            col = self._lane_color(n.lane, keys)
            if n.state == "miss":
                col = T.BORDER
            if n.is_ln:
                head = jy if n.state == "hold" else y
                c.create_rectangle(lx + 8, ytail, lx + lw - 8, head, fill=col, stipple="gray50", outline=col)
                c.create_rectangle(lx + 4, ytail - 5, lx + lw - 4, ytail + 3, fill=col, outline="")
                y = head
            if n.state == "hold" and not n.is_ln:
                continue
            if ring:
                c.create_oval(lx + 4, y - 11, lx + lw - 4, y + 11, outline=col, width=3, fill="#160F19")
                c.create_oval(lx + lw / 2 - 4, y - 4, lx + lw / 2 + 4, y + 4, fill=col, outline="")
            else:
                c.create_rectangle(lx + 3, y - 8, lx + lw - 3, y + 8, fill=col, outline="white" if n.state != "miss" else col)

        now = time.perf_counter()
        self.effects = [e for e in self.effects if now - e[0] < 0.45]
        for t0, lane, name, kind in self.effects:
            a = (now - t0) / 0.45
            cx, col = x0 + lane * lw + lw / 2, next(cc for j, cc, _ in JUDGES if j == name)
            if kind == "ripple":
                r = 12 + a * lw * 0.9
                c.create_oval(cx - r, jy - r * 0.6, cx + r, jy + r * 0.6, outline=col, width=max(1, int(4 * (1 - a))))
            else:
                for k in range(8):
                    ang = k * math.pi / 4 + a
                    r1, r2 = 8 + a * 34, 16 + a * 50
                    c.create_line(cx + math.cos(ang) * r1, jy + math.sin(ang) * r1, cx + math.cos(ang) * r2,
                                  jy + math.sin(ang) * r2, fill=col, width=2)

        # HUD (a band over the field so notes emerge from below it)
        c.create_rectangle(x0, 0, x0 + fw, top - 8, fill="#160F19", outline="")
        c.create_line(x0, top - 8, x0 + fw, top - 8, fill=T.BORDER)
        c.create_rectangle(0, 0, w, 3, fill=T.PANEL2, outline="")
        if self.sess.end_time > 0:
            c.create_rectangle(0, 0, w * min(max(t / (self.sess.end_time + 1), 0), 1), 3, fill=T.PINK, outline="")
        c.create_text(x0 + fw, 18, anchor="e", text=f"{self.sess.score():07d}", fill="white",
                      font=T.f(16, True))
        c.create_text(x0 + fw, 44, anchor="e", text=f"{self.sess.accuracy():.2f}%", fill=T.MUTED,
                      font=T.f(8))
        gx, gy = x0, 14
        c.create_rectangle(gx, gy, gx + fw * 0.45, gy + 10, fill=T.PANEL2, outline=T.BORDER)
        c.create_rectangle(gx, gy, gx + fw * 0.45 * self.sess.gauge, gy + 10, fill=T.LAV, outline="")
        c.create_text(gx, gy + 24, anchor="w", fill=T.LPINK if self.sess.fever else T.DIM,
                      text=f"FEVER  {'★' * self.sess.fever}{'☆' * (FEVER_MAX - self.sess.fever)}",
                      font=T.f(8, True))
        if self.sess.combo > 1:
            c.create_text(w / 2, jy - 210, text=str(self.sess.combo), fill="white", font=T.f(24, True))
            c.create_text(w / 2, jy - 172, text="COMBO", fill=T.MUTED, font=T.f(8, True))
        if self.last_judge and now - self.last_judge[1] < 0.6:
            name = self.last_judge[0]
            col = MISS_COLOR if name == "MISS" else next(cc for j, cc, _ in JUDGES if j == name)
            c.create_text(w / 2, jy - 140, text=name, fill=col, font=T.f(16, True))
        if self.banner and now - self.banner[1] < 1.2:
            c.create_text(w / 2, top + 70, text=self.banner[0], fill=T.PINK_HOT, font=T.f(24, True))

        if self.state == "countdown":
            c.create_text(w / 2, h / 2 - 40, text=str(max(1, math.ceil(-t))), fill=T.LPINK,
                          font=T.f(48, True))
        elif self.state == "paused":
            c.create_rectangle(x0, 0, x0 + fw, h, fill=T.BG, stipple="gray50", outline="")
            c.create_text(w / 2, h / 2 - 30, text=tr("cv.paused"), fill="white", font=T.f(24, True))
            c.create_text(w / 2, h / 2 + 10, text=tr("cv.pause_keys"), fill=T.LPINK,
                          font=T.f(8))
        elif self.state == "result":
            s = self.sess
            c.create_rectangle(x0, 0, x0 + fw, h, fill=T.BG, stipple="gray75", outline="")
            cx = w / 2
            c.create_text(cx, 90, text=s.grade(), fill=T.PINK_HOT, font=T.f(24, True))
            c.create_text(cx, 150, text=f"{s.score():07d}", fill="white", font=T.f(32, True))
            c.create_text(cx, 194, text=tr("cv.accuracy", acc=f"{s.accuracy():.2f}", combo=s.max_combo), fill=T.LPINK,
                          font=T.f(11))
            for i, (name, col, _) in enumerate(JUDGES):
                c.create_text(cx - 70, 240 + i * 26, anchor="w", text=name, fill=col, font=T.f(11, True))
                c.create_text(cx + 70, 240 + i * 26, anchor="e", text=str(s.counts[name]), fill="white",
                              font=T.f(11))
            c.create_text(cx - 70, 240 + 3 * 26, anchor="w", text="MISS", fill=MISS_COLOR, font=T.f(11, True))
            c.create_text(cx + 70, 240 + 3 * 26, anchor="e", text=str(s.counts["MISS"]), fill="white",
                          font=T.f(11))
            c.create_text(cx, 240 + 4 * 26 + 20, text=tr("cv.result_keys"), fill=T.MUTED, font=T.f(8))
