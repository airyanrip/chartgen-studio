"""ChartGen: auto chart generator with a built-in rhythm-game test player.

Left  : make a chart (file / YouTube, chart options, library) - runs chartgen.py in the venv
Right : play the generated chart immediately (game.py)

The UI language (ko / en / ja / zh) is chosen in the header, saved in settings.json, and applied
live: every text is registered with reg() and re-applied by relabel().
"""
import codecs
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

if sys.stdout is None:                      # pythonw has no console
    sys.stdout = sys.stderr = open(os.devnull, "w")

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import i18n                                  # noqa: E402
import theme as T                            # noqa: E402
from game import GamePanel                   # noqa: E402
from i18n import LANGS, t as tr              # noqa: E402

PYTHON = APP_DIR / ".venv" / "Scripts" / "python.exe"
SCRIPT = APP_DIR / "chartgen.py"
TOOLS = APP_DIR / "tools"
YT_DLP = TOOLS / "yt-dlp.exe"
DOWNLOADS = APP_DIR / "downloads"
CHARTS = APP_DIR / "charts"
SETTINGS = APP_DIR / "settings.json"

DIFFICULTIES = ["easy", "normal", "hard", "insane"]
VOCAL_MODES = ["ignore", "mix", "only"]


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip() or "chart"


def saved_language():
    """Language from settings.json, else the Windows UI language."""
    try:
        code = json.loads(SETTINGS.read_text(encoding="utf-8")).get("lang")
    except (OSError, ValueError):
        code = None
    return code if code in LANGS else i18n.detect_lang()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        i18n.set_lang(saved_language())
        self.geometry("1280x820")
        self.minsize(1120, 740)
        T.apply(self, i18n.get_lang())

        self.proc = None
        self.job = None            # "chart" | "download"
        self.msgs = queue.Queue()
        self.result_path = None
        self.dl_file = None
        self.dl_title = None
        self._labels = []          # (widget, option, i18n key, format args)
        self._tabs = []            # (tab frame, i18n key)
        self._status = ("status.idle", {})

        self.url = tk.StringVar()
        self.save_video = tk.BooleanVar(value=False)
        self.audio = tk.StringVar()
        self.out = tk.StringVar()
        self.title_v = tk.StringVar()
        self.artist = tk.StringVar(value="Unknown")
        self.creator = tk.StringVar(value="chartgen")
        self.keys = tk.IntVar(value=4)
        self.diff = {k: tk.BooleanVar(value=(k == "normal")) for k in DIFFICULTIES}
        self.vocals = tk.StringVar(value="ignore")
        self.long_notes = tk.BooleanVar(value=True)
        self.ln_ratio = tk.DoubleVar(value=0.35)
        self.sustain = tk.DoubleVar(value=0.6)
        self.auto_bpm = tk.BooleanVar(value=True)
        self.bpm = tk.StringVar(value="120")
        self.seed = tk.IntVar(value=0)
        self.lang_var = tk.StringVar(value=LANGS[i18n.get_lang()])

        self._build()
        self._refresh_library()
        self.relabel()
        self.after(100, self._pump)

    # ------------------------------------------------------------ translation helpers
    def reg(self, widget, key, opt="text", **kw):
        """Register a widget text for the language system and return the widget."""
        self._labels.append((widget, opt, key, kw))
        return widget

    def relabel(self):
        self.title(tr("app.title"))
        for widget, opt, key, kw in self._labels:
            widget.configure(**{opt: tr(key, **kw)})
        for frame, key in self._tabs:
            self.nb.tab(frame, text="  " + tr(key) + "  ")
        self._render_status()

    def _say(self, key, **kw):
        self._status = (key, kw)
        self._render_status()

    def _render_status(self):
        key, kw = self._status
        self.status.configure(text=tr(key, **kw))

    def _on_language(self, _event=None):
        code = next(c for c, name in LANGS.items() if name == self.lang_var.get())
        if code == i18n.get_lang():
            return
        i18n.set_lang(code)
        T.apply(self, code)                                   # fonts differ per language
        for w in (self.log, self.lib):                        # classic tk widgets do not follow ttk styles
            w.configure(font=T.f(8))
        for box in (self.lang_box,):
            self.tk.call("destroy", f"{box}.popdown")
        self.relabel()
        self.game.relabel()
        self.game.cfg["lang"] = code
        self.game._save_cfg_later()

    # ------------------------------------------------------------ layout
    def _build(self):
        head = tk.Frame(self, bg=T.HEADER)
        head.pack(fill="x")
        tk.Frame(head, bg=T.TITLEBAR_ACCENT, width=4).pack(side="left", fill="y")
        self.reg(ttk.Label(head, style="Title.TLabel"), "app.title").pack(side="left", padx=(12, 8), pady=8)
        self.reg(ttk.Label(head, style="Sub.TLabel"), "app.subtitle").pack(side="left")
        self.lang_box = ttk.Combobox(head, textvariable=self.lang_var, values=list(LANGS.values()),
                                     state="readonly", width=10, takefocus=0)
        self.lang_box.pack(side="right", padx=10)
        self.lang_box.bind("<<ComboboxSelected>>", self._on_language)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, width=470)
        left.grid(row=0, column=0, sticky="ns", padx=(8, 0), pady=8)
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        self.nb = ttk.Notebook(left)
        self.nb.grid(row=0, column=0, sticky="ew")
        for frame, key in ((self._tab_song(self.nb), "tab.song"), (self._tab_chart(self.nb), "tab.chart"),
                           (self._tab_library(self.nb), "tab.library")):
            self.nb.add(frame, text=key)
            self._tabs.append((frame, key))

        self.run_btn = self.reg(ttk.Button(left, style="Accent.TButton", command=self._start), "btn.generate")
        self.run_btn.grid(row=2, column=0, sticky="ew", pady=(10, 4))
        row = ttk.Frame(left)
        row.grid(row=3, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.stop_btn = self.reg(ttk.Button(row, command=self._stop, state="disabled"), "btn.stop")
        self.stop_btn.grid(row=0, column=1, padx=(0, 4))
        self.open_btn = self.reg(ttk.Button(row, command=self._open_result, state="disabled"), "btn.open_folder")
        self.open_btn.grid(row=0, column=2)
        self.status = ttk.Label(row, style="Muted.TLabel")
        self.status.grid(row=0, column=0, sticky="w")
        self.bar = ttk.Progressbar(left, mode="determinate", value=0)
        self.bar.grid(row=4, column=0, sticky="ew", pady=6)
        lg = ttk.Frame(left)
        lg.grid(row=5, column=0, sticky="nsew")
        left.rowconfigure(5, weight=1)
        self.log = tk.Text(lg, height=7, state="disabled", wrap="word", font=T.f(8), bg=T.PANEL,
                           fg=T.MUTED, relief="flat", highlightthickness=1, highlightbackground=T.BORDER)
        sb = ttk.Scrollbar(lg, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.game = GamePanel(body, SETTINGS, on_status=self._say)
        self.game.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self._sync()

    def _tab_song(self, nb):
        t = ttk.Frame(nb, padding=8)
        t.columnconfigure(0, weight=1)
        f = self.reg(ttk.LabelFrame(t), "box.audio")
        f.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        f.columnconfigure(1, weight=1)
        self.reg(ttk.Label(f), "lbl.input").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(f, textvariable=self.audio).grid(row=0, column=1, sticky="ew", pady=4)
        self.reg(ttk.Button(f, command=self._pick_audio), "btn.browse").grid(row=0, column=2, padx=6)
        self.reg(ttk.Label(f), "lbl.save").grid(row=1, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(f, textvariable=self.out).grid(row=1, column=1, sticky="ew", pady=4)
        self.reg(ttk.Button(f, command=self._pick_out), "btn.pick").grid(row=1, column=2, padx=6)
        self.reg(ttk.Label(f, style="Muted.TLabel"), "hint.default_out", path=CHARTS).grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(0, 4))

        y = self.reg(ttk.LabelFrame(t), "box.youtube")
        y.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        y.columnconfigure(1, weight=1)
        self.reg(ttk.Label(y), "lbl.url").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(y, textvariable=self.url).grid(row=0, column=1, sticky="ew", pady=4)
        self.dl_btn = self.reg(ttk.Button(y, command=self._start_download), "btn.fetch")
        self.dl_btn.grid(row=0, column=2, padx=6)
        self.reg(ttk.Checkbutton(y, variable=self.save_video), "chk.save_video").grid(
            row=1, column=1, columnspan=2, sticky="w")
        self.reg(ttk.Label(y, style="Muted.TLabel"), "hint.dl_dir", path=DOWNLOADS).grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(0, 4))

        m = self.reg(ttk.LabelFrame(t), "box.info")
        m.grid(row=2, column=0, sticky="ew")
        m.columnconfigure(1, weight=1)
        for r, (key, var) in enumerate([("lbl.title", self.title_v), ("lbl.artist", self.artist),
                                        ("lbl.creator", self.creator)]):
            self.reg(ttk.Label(m), key).grid(row=r, column=0, padx=6, pady=4, sticky="w")
            ttk.Entry(m, textvariable=var).grid(row=r, column=1, sticky="ew", padx=(0, 6), pady=4)
        return t

    def _tab_chart(self, nb):
        t = ttk.Frame(nb, padding=8)
        t.columnconfigure(0, weight=1)
        c = self.reg(ttk.LabelFrame(t), "box.chartset")
        c.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.reg(ttk.Label(c), "lbl.keys").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Spinbox(c, from_=1, to=9, width=5, textvariable=self.keys).grid(row=0, column=1, sticky="w")
        self.reg(ttk.Label(c, style="Muted.TLabel"), "hint.keys").grid(row=0, column=2, sticky="w", padx=8)
        self.reg(ttk.Label(c), "lbl.difficulty").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        df = ttk.Frame(c)
        df.grid(row=1, column=1, columnspan=3, sticky="w")
        for key in DIFFICULTIES:
            self.reg(ttk.Checkbutton(df, variable=self.diff[key]), "diff." + key).pack(side="left", padx=(0, 8))
        self.reg(ttk.Label(c), "lbl.vocals").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        vf = ttk.Frame(c)
        vf.grid(row=2, column=1, columnspan=3, sticky="w")
        for key in VOCAL_MODES:
            self.reg(ttk.Radiobutton(vf, value=key, variable=self.vocals), "vocal." + key).pack(anchor="w")

        ln = self.reg(ttk.LabelFrame(t), "box.ln")
        ln.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ln.columnconfigure(1, weight=1)
        self.reg(ttk.Checkbutton(ln, variable=self.long_notes, command=self._sync), "chk.ln").grid(
            row=0, column=0, columnspan=3, padx=6, pady=4, sticky="w")
        self.ratio_lbl = ttk.Label(ln, width=6, style="Muted.TLabel")
        self.sus_lbl = ttk.Label(ln, width=6, style="Muted.TLabel")
        self.ratio_scale = ttk.Scale(ln, from_=0.05, to=0.8, variable=self.ln_ratio,
                                     command=lambda _v: self._sync_labels())
        self.sus_scale = ttk.Scale(ln, from_=0.3, to=0.95, variable=self.sustain,
                                   command=lambda _v: self._sync_labels())
        self.reg(ttk.Label(ln), "lbl.ln_ratio").grid(row=1, column=0, padx=6, sticky="w")
        self.ratio_scale.grid(row=1, column=1, sticky="ew")
        self.ratio_lbl.grid(row=1, column=2, padx=6)
        self.reg(ttk.Label(ln), "lbl.ln_sus").grid(row=2, column=0, padx=6, pady=(0, 6), sticky="w")
        self.sus_scale.grid(row=2, column=1, sticky="ew", pady=(0, 6))
        self.sus_lbl.grid(row=2, column=2, padx=6, pady=(0, 6))
        self.reg(ttk.Label(ln, style="Muted.TLabel", wraplength=420), "hint.ln").grid(
            row=3, column=0, columnspan=3, padx=6, pady=(0, 4), sticky="w")

        a = self.reg(ttk.LabelFrame(t), "box.adv")
        a.grid(row=2, column=0, sticky="ew")
        self.reg(ttk.Checkbutton(a, variable=self.auto_bpm, command=self._sync), "chk.auto_bpm").grid(
            row=0, column=0, padx=6, pady=6)
        self.bpm_entry = ttk.Entry(a, textvariable=self.bpm, width=7)
        self.bpm_entry.grid(row=0, column=1)
        self.reg(ttk.Label(a), "lbl.bpm").grid(row=0, column=2, padx=(4, 16))
        self.reg(ttk.Label(a), "lbl.seed").grid(row=0, column=3)
        ttk.Spinbox(a, from_=0, to=99999, width=7, textvariable=self.seed).grid(row=0, column=4, padx=6)
        return t

    def _tab_library(self, nb):
        t = ttk.Frame(nb, padding=8)
        t.columnconfigure(0, weight=1)
        self.reg(ttk.Label(t, style="Muted.TLabel", wraplength=430), "lib.hint").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self.lib = tk.Listbox(t, height=8, bg=T.PANEL, fg=T.TEXT, selectbackground=T.PINK,
                              selectforeground="white", relief="flat", highlightthickness=1,
                              highlightbackground=T.BORDER, activestyle="none", font=T.f(8))
        self.lib.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.lib.bind("<Double-Button-1>", lambda _e: self._load_selected())
        bar = ttk.Frame(t)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.reg(ttk.Button(bar, command=self._load_selected), "btn.load").pack(side="left")
        self.reg(ttk.Button(bar, command=self._open_osz), "btn.open_osz").pack(side="left", padx=6)
        self.reg(ttk.Button(bar, command=self._refresh_library), "btn.refresh").pack(side="left")
        return t

    # ------------------------------------------------------------ helpers
    def _sync(self):
        st = "normal" if self.long_notes.get() else "disabled"
        self.ratio_scale.configure(state=st)
        self.sus_scale.configure(state=st)
        self.bpm_entry.configure(state="disabled" if self.auto_bpm.get() else "normal")
        self._sync_labels()

    def _sync_labels(self):
        self.ratio_lbl.configure(text=f"{self.ln_ratio.get() * 100:.0f}%")
        self.sus_lbl.configure(text=f"{self.sustain.get():.2f}")

    def _pick_audio(self):
        p = filedialog.askopenfilename(
            title=tr("dlg.pick_audio"),
            filetypes=[(tr("ft.audio"), "*.mp3 *.wav *.ogg *.flac *.m4a *.aac"), (tr("ft.all"), "*.*")])
        if p:
            self.audio.set(p)
            if not self.title_v.get():
                self.title_v.set(Path(p).stem)

    def _pick_out(self):
        p = filedialog.asksaveasfilename(title=tr("dlg.save_as"), defaultextension=".osz",
                                         filetypes=[(tr("ft.osz"), "*.osz")])
        if p:
            self.out.set(p)

    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_running(self, running):
        self.run_btn.configure(state="disabled" if running else "normal")
        self.dl_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        if running:
            self.bar.configure(mode="indeterminate")
            self.bar.start(12)
        else:
            self.bar.stop()
            self.bar.configure(mode="determinate", value=0)

    # ------------------------------------------------------------ library
    def _refresh_library(self):
        CHARTS.mkdir(exist_ok=True)
        self.lib_paths = sorted(CHARTS.glob("*.osz"), key=lambda p: p.stat().st_mtime, reverse=True)
        self.lib.delete(0, "end")
        for p in self.lib_paths:
            self.lib.insert("end", "  " + p.stem)

    def _load_selected(self):
        sel = self.lib.curselection()
        if sel:
            self.game.load_osz(self.lib_paths[sel[0]])

    def _open_osz(self):
        p = filedialog.askopenfilename(title=tr("dlg.open_osz"), filetypes=[(tr("ft.osz"), "*.osz")])
        if p:
            self.game.load_osz(p)

    # ------------------------------------------------------------ run
    def _command(self):
        audio = self.audio.get().strip().strip('"')
        if not audio or not Path(audio).is_file():
            raise ValueError(tr("err.no_audio"))
        diffs = [k for k in DIFFICULTIES if self.diff[k].get()]
        if not diffs:
            raise ValueError(tr("err.no_diff"))
        if not (PYTHON.exists() and SCRIPT.exists()):
            raise ValueError(tr("err.no_env", python=PYTHON, script=SCRIPT))
        title = self.title_v.get().strip() or Path(audio).stem
        out = self.out.get().strip()
        if not out:
            CHARTS.mkdir(exist_ok=True)
            out = str(CHARTS / (safe_name(title) + ".osz"))
        cmd = [str(PYTHON), str(SCRIPT), audio, "--keys", str(self.keys.get()),
               "--difficulty", ",".join(diffs), "--vocals", self.vocals.get(),
               "--seed", str(self.seed.get()),
               "--max-ln-ratio", f"{self.ln_ratio.get():.2f}", "--sustain", f"{self.sustain.get():.2f}",
               "--title", title, "--artist", self.artist.get().strip() or "Unknown",
               "--creator", self.creator.get().strip() or "chartgen", "-o", out]
        if not self.long_notes.get():
            cmd.append("--no-long-notes")
        if not self.auto_bpm.get():
            try:
                bpm = float(self.bpm.get())
                if bpm <= 0:
                    raise ValueError
            except ValueError:
                raise ValueError(tr("err.bad_bpm"))
            cmd += ["--bpm", str(bpm)]
        return cmd

    def _start(self):
        try:
            cmd = self._command()
        except ValueError as e:
            messagebox.showwarning(tr("msg.check"), str(e))
            return
        self.game.stop()
        self.result_path = None
        self.open_btn.configure(state="disabled")
        self._clear_log()
        self._say("st.analyzing")
        self._begin("chart", [cmd])

    def _start_download(self):
        url = self.url.get().strip()
        if not re.match(r"https?://", url):
            messagebox.showwarning(tr("msg.check"), tr("err.bad_url"))
            return
        if not YT_DLP.exists() or not (TOOLS / "ffmpeg.exe").exists():
            messagebox.showwarning(tr("msg.check"), tr("err.no_tools", path=TOOLS))
            return
        base = [str(YT_DLP), "--no-playlist", "--encoding", "utf-8", "--windows-filenames", "--newline",
                "--ffmpeg-location", str(TOOLS)]
        out = str(DOWNLOADS / "%(title)s.%(ext)s")
        cmds = [base + ["-x", "--audio-format", "mp3", "--audio-quality", "0", "-o", out,
                        "--print", "before_dl:TITLE=%(title)s", "--print", "after_move:FILE=%(filepath)s", url]]
        if self.save_video.get():
            cmds.append(base + ["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b",
                                "--merge-output-format", "mp4", "-o", out, url])
        self.dl_file = self.dl_title = None
        self._clear_log()
        self._say("st.fetching")
        self._begin("download", cmds)

    def _begin(self, job, cmds):
        self.job = job
        self._set_running(True)
        threading.Thread(target=self._worker, args=(cmds,), daemon=True).start()

    def _worker(self, cmds):
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
                   HF_HOME=str(APP_DIR / "models"), TORCH_HOME=str(APP_DIR / "models"),
                   PATH=str(TOOLS) + os.pathsep + os.environ.get("PATH", ""))
        code = -1
        try:
            for cmd in cmds:
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                             cwd=str(APP_DIR), creationflags=subprocess.CREATE_NO_WINDOW)
                dec = codecs.getincrementaldecoder("utf-8")("replace")
                carry = ""
                while True:
                    chunk = self.proc.stdout.read1(4096)
                    if not chunk:
                        break
                    parts = re.split(r"[\r\n]+", carry + dec.decode(chunk))
                    carry = parts.pop()
                    for p in parts:
                        self.msgs.put(("line", p))
                if carry:
                    self.msgs.put(("line", carry))
                code = self.proc.wait()
                if code != 0:
                    break
        except Exception as e:  # noqa: BLE001 - surface any launch failure in the UI
            self.msgs.put(("launch_fail", str(e)))
        self.msgs.put(("done", code))

    def _pump(self):
        try:
            while True:
                kind, val = self.msgs.get_nowait()
                if kind == "line":
                    self._on_line(val)
                elif kind == "launch_fail":
                    self._append(tr("log.launch_fail", err=val))
                else:
                    self._on_done(val)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def _on_line(self, line):
        line = line.strip()
        if not line:
            return
        if self.job == "download":
            m = re.match(r"\[download\]\s+(\d+(?:\.\d+)?)%", line)
            if m:
                self._say("st.dl_pct", pct=f"{float(m.group(1)):.0f}")
                return
            if line.startswith("TITLE="):
                self.dl_title = line[6:]
            elif line.startswith("FILE=") and line.lower().endswith(".mp3"):
                self.dl_file = line[5:]
            self._append(line)
            return
        if "%|" in line:  # tqdm progress: show in status only
            m = re.match(r"\s*(\d+)%", line)
            if m:
                self._say("st.sep_pct", pct=m.group(1))
            return
        if line.startswith("wrote "):
            self.result_path = line[6:].strip()
        self._append(line)

    def _on_done(self, code):
        self._set_running(False)
        self.proc = None
        if self.job == "download":
            if code == 0 and self.dl_file and Path(self.dl_file).exists():
                self.audio.set(self.dl_file)
                self.title_v.set(self.dl_title or Path(self.dl_file).stem)
                self._say("st.dl_done")
            else:
                self._say("st.dl_fail")
            return
        if code == 0 and self.result_path:
            self.open_btn.configure(state="normal")
            self._refresh_library()
            if self.game.load_osz(self.result_path):
                self._say("st.gen_done")
        else:
            self._say("st.gen_fail")

    def _stop(self):
        if self.proc:
            self.proc.terminate()
            self._append(tr("log.stopped"))

    def _open_result(self):
        if self.result_path and Path(self.result_path).exists():
            subprocess.Popen(["explorer", "/select,", str(Path(self.result_path))])


def main():
    try:
        App().mainloop()
    except Exception:  # noqa: BLE001 - pythonw hides tracebacks, so keep a log next to the app
        (APP_DIR / "gui_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
