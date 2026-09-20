"""ChartGen: auto chart generator with a built-in rhythm-game test player.

Left  : make a chart (file / YouTube, chart options, library) - runs chartgen.py in the venv
Right : play the generated chart immediately (game.py)
"""
import codecs
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

import theme as T                            # noqa: E402
from game import GamePanel                   # noqa: E402

PYTHON = APP_DIR / ".venv" / "Scripts" / "python.exe"
SCRIPT = APP_DIR / "chartgen.py"
TOOLS = APP_DIR / "tools"
YT_DLP = TOOLS / "yt-dlp.exe"
DOWNLOADS = APP_DIR / "downloads"
CHARTS = APP_DIR / "charts"

DIFFICULTIES = [("easy", "쉬움"), ("normal", "보통"), ("hard", "어려움"), ("insane", "매우 어려움")]
VOCAL_MODES = [("ignore", "반주만 (보컬 무시)"), ("mix", "반주 + 보컬 함께"), ("only", "보컬만")]


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip() or "chart"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("채보 생성 스튜디오")
        self.geometry("1280x820")
        self.minsize(1120, 740)
        T.apply(self)

        self.proc = None
        self.job = None            # "chart" | "download"
        self.msgs = queue.Queue()
        self.result_path = None
        self.dl_file = None
        self.dl_title = None

        self.url = tk.StringVar()
        self.save_video = tk.BooleanVar(value=False)
        self.audio = tk.StringVar()
        self.out = tk.StringVar()
        self.title_v = tk.StringVar()
        self.artist = tk.StringVar(value="Unknown")
        self.creator = tk.StringVar(value="chartgen")
        self.keys = tk.IntVar(value=4)
        self.diff = {k: tk.BooleanVar(value=(k == "normal")) for k, _ in DIFFICULTIES}
        self.vocals = tk.StringVar(value="ignore")
        self.long_notes = tk.BooleanVar(value=True)
        self.ln_ratio = tk.DoubleVar(value=0.35)
        self.sustain = tk.DoubleVar(value=0.6)
        self.auto_bpm = tk.BooleanVar(value=True)
        self.bpm = tk.StringVar(value="120")
        self.seed = tk.IntVar(value=0)

        self._build()
        self._refresh_library()
        self.after(100, self._pump)

    # ------------------------------------------------------------ layout
    def _build(self):
        head = tk.Frame(self, bg=T.HEADER)
        head.pack(fill="x")
        tk.Frame(head, bg=T.TITLEBAR_ACCENT, width=4).pack(side="left", fill="y")
        ttk.Label(head, text="채보 생성 스튜디오", style="Title.TLabel").pack(side="left", padx=(12, 8), pady=8)
        ttk.Label(head, text="자동 채보 생성 · 테스트 플레이", style="Sub.TLabel").pack(side="left")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, width=470)
        left.grid(row=0, column=0, sticky="ns", padx=(8, 0), pady=8)
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        nb = ttk.Notebook(left)
        nb.grid(row=0, column=0, sticky="ew")
        nb.add(self._tab_song(nb), text="  곡  ")
        nb.add(self._tab_chart(nb), text="  채보  ")
        nb.add(self._tab_library(nb), text="  라이브러리  ")

        self.run_btn = ttk.Button(left, text="채보 생성", style="Accent.TButton", command=self._start)
        self.run_btn.grid(row=2, column=0, sticky="ew", pady=(10, 4))
        row = ttk.Frame(left)
        row.grid(row=3, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.stop_btn = ttk.Button(row, text="중지", command=self._stop, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=(0, 4))
        self.open_btn = ttk.Button(row, text="결과 폴더 열기", command=self._open_result, state="disabled")
        self.open_btn.grid(row=0, column=2)
        self.status = ttk.Label(row, text="대기 중", style="Muted.TLabel")
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

        self.game = GamePanel(body, APP_DIR / "settings.json", on_status=self._say)
        self.game.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self._sync()

    def _tab_song(self, nb):
        t = ttk.Frame(nb, padding=8)
        t.columnconfigure(0, weight=1)
        f = ttk.LabelFrame(t, text="음악 파일")
        f.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="입력").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(f, textvariable=self.audio).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(f, text="찾아보기", command=self._pick_audio).grid(row=0, column=2, padx=6)
        ttk.Label(f, text="저장").grid(row=1, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(f, textvariable=self.out).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(f, text="지정", command=self._pick_out).grid(row=1, column=2, padx=6)
        ttk.Label(f, text=f"비워 두면 {CHARTS} 에 저장", style="Muted.TLabel").grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(0, 4))

        y = ttk.LabelFrame(t, text="유튜브에서 가져오기")
        y.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        y.columnconfigure(1, weight=1)
        ttk.Label(y, text="URL").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(y, textvariable=self.url).grid(row=0, column=1, sticky="ew", pady=4)
        self.dl_btn = ttk.Button(y, text="가져오기", command=self._start_download)
        self.dl_btn.grid(row=0, column=2, padx=6)
        ttk.Checkbutton(y, text="영상(mp4)도 함께 저장", variable=self.save_video).grid(
            row=1, column=1, columnspan=2, sticky="w")
        ttk.Label(y, text=f"받은 파일: {DOWNLOADS}", style="Muted.TLabel").grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(0, 4))

        m = ttk.LabelFrame(t, text="곡 정보")
        m.grid(row=2, column=0, sticky="ew")
        m.columnconfigure(1, weight=1)
        for r, (label, var) in enumerate([("제목", self.title_v), ("아티스트", self.artist),
                                          ("제작자", self.creator)]):
            ttk.Label(m, text=label).grid(row=r, column=0, padx=6, pady=4, sticky="w")
            ttk.Entry(m, textvariable=var).grid(row=r, column=1, sticky="ew", padx=(0, 6), pady=4)
        return t

    def _tab_chart(self, nb):
        t = ttk.Frame(nb, padding=8)
        t.columnconfigure(0, weight=1)
        c = ttk.LabelFrame(t, text="채보 설정")
        c.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(c, text="키 개수").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Spinbox(c, from_=1, to=9, width=5, textvariable=self.keys).grid(row=0, column=1, sticky="w")
        ttk.Label(c, text="4키, 6키 등", style="Muted.TLabel").grid(row=0, column=2, sticky="w", padx=8)
        ttk.Label(c, text="난이도").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        df = ttk.Frame(c)
        df.grid(row=1, column=1, columnspan=3, sticky="w")
        for key, label in DIFFICULTIES:
            ttk.Checkbutton(df, text=label, variable=self.diff[key]).pack(side="left", padx=(0, 8))
        ttk.Label(c, text="보컬 처리").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        vf = ttk.Frame(c)
        vf.grid(row=2, column=1, columnspan=3, sticky="w")
        for key, label in VOCAL_MODES:
            ttk.Radiobutton(vf, text=label, value=key, variable=self.vocals).pack(anchor="w")

        ln = ttk.LabelFrame(t, text="롱노트")
        ln.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ln.columnconfigure(1, weight=1)
        ttk.Checkbutton(ln, text="롱노트 사용", variable=self.long_notes, command=self._sync).grid(
            row=0, column=0, columnspan=3, padx=6, pady=4, sticky="w")
        self.ratio_lbl = ttk.Label(ln, width=6, style="Muted.TLabel")
        self.sus_lbl = ttk.Label(ln, width=6, style="Muted.TLabel")
        self.ratio_scale = ttk.Scale(ln, from_=0.05, to=0.8, variable=self.ln_ratio,
                                     command=lambda _v: self._sync_labels())
        self.sus_scale = ttk.Scale(ln, from_=0.3, to=0.95, variable=self.sustain,
                                   command=lambda _v: self._sync_labels())
        ttk.Label(ln, text="비율 상한").grid(row=1, column=0, padx=6, sticky="w")
        self.ratio_scale.grid(row=1, column=1, sticky="ew")
        self.ratio_lbl.grid(row=1, column=2, padx=6)
        ttk.Label(ln, text="판정 기준").grid(row=2, column=0, padx=6, pady=(0, 6), sticky="w")
        self.sus_scale.grid(row=2, column=1, sticky="ew", pady=(0, 6))
        self.sus_lbl.grid(row=2, column=2, padx=6, pady=(0, 6))
        ttk.Label(ln, text="판정 기준을 낮추면 롱노트가 더 많이 생깁니다.", style="Muted.TLabel").grid(
            row=3, column=0, columnspan=3, padx=6, pady=(0, 4), sticky="w")

        a = ttk.LabelFrame(t, text="고급")
        a.grid(row=2, column=0, sticky="ew")
        ttk.Checkbutton(a, text="BPM 자동 감지", variable=self.auto_bpm, command=self._sync).grid(
            row=0, column=0, padx=6, pady=6)
        self.bpm_entry = ttk.Entry(a, textvariable=self.bpm, width=7)
        self.bpm_entry.grid(row=0, column=1)
        ttk.Label(a, text="BPM").grid(row=0, column=2, padx=(4, 16))
        ttk.Label(a, text="시드").grid(row=0, column=3)
        ttk.Spinbox(a, from_=0, to=99999, width=7, textvariable=self.seed).grid(row=0, column=4, padx=6)
        return t

    def _tab_library(self, nb):
        t = ttk.Frame(nb, padding=8)
        t.columnconfigure(0, weight=1)
        ttk.Label(t, text="만든 채보 (더블클릭하면 오른쪽 플레이어에 불러옵니다)", style="Muted.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self.lib = tk.Listbox(t, height=8, bg=T.PANEL, fg=T.TEXT, selectbackground=T.PINK,
                              selectforeground="white", relief="flat", highlightthickness=1,
                              highlightbackground=T.BORDER, activestyle="none", font=T.f(8))
        self.lib.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.lib.bind("<Double-Button-1>", lambda _e: self._load_selected())
        bar = ttk.Frame(t)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(bar, text="불러오기", command=self._load_selected).pack(side="left")
        ttk.Button(bar, text=".osz 열기...", command=self._open_osz).pack(side="left", padx=6)
        ttk.Button(bar, text="새로고침", command=self._refresh_library).pack(side="left")
        return t

    # ------------------------------------------------------------ helpers
    def _say(self, text):
        self.status.configure(text=text)

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
            title="음악 파일 선택",
            filetypes=[("오디오", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac"), ("모든 파일", "*.*")])
        if p:
            self.audio.set(p)
            if not self.title_v.get():
                self.title_v.set(Path(p).stem)

    def _pick_out(self):
        p = filedialog.asksaveasfilename(title="저장 위치", defaultextension=".osz",
                                         filetypes=[("osu! 비트맵", "*.osz")])
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
        p = filedialog.askopenfilename(title="채보(.osz) 열기", filetypes=[("osu! 비트맵", "*.osz")])
        if p:
            self.game.load_osz(p)

    # ------------------------------------------------------------ run
    def _command(self):
        audio = self.audio.get().strip().strip('"')
        if not audio or not Path(audio).is_file():
            raise ValueError("음악 파일을 선택해 주세요.")
        diffs = [k for k, _ in DIFFICULTIES if self.diff[k].get()]
        if not diffs:
            raise ValueError("난이도를 하나 이상 선택해 주세요.")
        if not (PYTHON.exists() and SCRIPT.exists()):
            raise ValueError(f"실행 환경을 찾을 수 없습니다.\n{PYTHON}\n{SCRIPT}")
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
                raise ValueError("BPM은 0보다 큰 숫자여야 합니다.")
            cmd += ["--bpm", str(bpm)]
        return cmd

    def _start(self):
        try:
            cmd = self._command()
        except ValueError as e:
            messagebox.showwarning("확인", str(e))
            return
        self.game.stop()
        self.result_path = None
        self.open_btn.configure(state="disabled")
        self._clear_log()
        self.status.configure(text="분석 중... (보컬 분리는 처음엔 오래 걸릴 수 있습니다)")
        self._begin("chart", [cmd])

    def _start_download(self):
        url = self.url.get().strip()
        if not re.match(r"https?://", url):
            messagebox.showwarning("확인", "유튜브 URL을 입력해 주세요. (https://... 형태)")
            return
        if not YT_DLP.exists() or not (TOOLS / "ffmpeg.exe").exists():
            messagebox.showwarning("확인", f"yt-dlp.exe / ffmpeg.exe 를 찾을 수 없습니다.\n{TOOLS}")
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
        self.status.configure(text="유튜브에서 가져오는 중...")
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
            self.msgs.put(("line", f"실행 실패: {e}"))
        self.msgs.put(("done", code))

    def _pump(self):
        try:
            while True:
                kind, val = self.msgs.get_nowait()
                if kind == "line":
                    self._on_line(val)
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
                self.status.configure(text=f"다운로드 중... {float(m.group(1)):.0f}%")
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
                self.status.configure(text=f"보컬 분리 중... {m.group(1)}%")
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
                self.status.configure(text="가져오기 완료! 이제 '채보 생성'을 누르세요.")
            else:
                self.status.configure(text="가져오기 실패 (URL이나 영상 공개 여부를 확인하세요)")
            return
        if code == 0 and self.result_path:
            self.open_btn.configure(state="normal")
            self._refresh_library()
            if self.game.load_osz(self.result_path):
                self.status.configure(text="완료! 오른쪽 플레이어에서 ▶ 시작을 눌러 테스트해 보세요.")
        else:
            self.status.configure(text="실패 또는 중지됨")

    def _stop(self):
        if self.proc:
            self.proc.terminate()
            self._append("중지했습니다.")

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
