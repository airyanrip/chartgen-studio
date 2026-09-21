# Chart Generation Studio

[한국어](README.md) | **English** | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

Automatically generates rhythm-game charts from a music file (or a YouTube URL) and lets you play them right inside the app.
The output is an **osu!mania `.osz`** with tap notes and **long notes**.

## Features

- **Automatic charting**: finds the song's BPM and beat grid, then turns the points where sounds begin into notes snapped to that grid. Sustained sounds become long notes.
- **Key count**: 1-9 keys (default 4). Four difficulties (Easy / Normal / Hard / Insane) can be generated at once.
- **Vocal handling**: vocals (lyrics) and backing are separated with demucs, and you choose one of three modes:
  - `ignore` chart the backing only (vocals are ignored)
  - `mix` backing + vocals together
  - `only` vocals only
  - The time ranges where vocals are present are saved to `<name>.vocals.json`, so lyrics (for example from Whisper) can be aligned later.
- **YouTube import**: downloads the audio (optionally the 1080p video) from a URL using yt-dlp + ffmpeg.
- **Test player**: play the generated chart in the panel on the right of the window. PERFECT / GREAT / GOOD / MISS judgments, FEVER gauge, ring / rectangle notes, ripple / burst hit effects, adjustable note speed, sync and judgment width, key bindings, pause (ESC) and restart (R).
- **Multilingual UI**: 한국어 / English / 日本語 / 简体中文. Pick one at the top right of the window; it switches instantly and is remembered for the next launch. The first launch follows your Windows display language. (Game terms such as PERFECT / GREAT / GOOD / MISS stay in English in every language.)
- Pixel-style fonts: [Galmuri](https://github.com/quiple/galmuri) (Korean, English, Japanese) and [Ark Pixel](https://github.com/TakWolf/ark-pixel-font) (Chinese). Both are SIL OFL 1.1; the licenses are in `fonts/`.

## Requirements

- Windows 10/11
- Python 3.11 ([uv](https://docs.astral.sh/uv/) recommended)
- An NVIDIA GPU is recommended (vocal separation is much faster; it also works with CPU-only PyTorch, just slower)

## Installation

```powershell
git clone <this repository URL> chartgen
cd chartgen

uv venv --python 3.11 .venv

# 1) Install PyTorch first. (GPU: CUDA 12.6 build / CPU only: plain `torch` without --index-url)
uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu126

# 2) The remaining packages
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

Put three executables in the `tools\` folder. (They are large, so they are not part of the repository.)

```powershell
mkdir tools
# yt-dlp
curl.exe -L -o tools\yt-dlp.exe https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
# deno (the JavaScript runtime yt-dlp uses to read YouTube)
curl.exe -L -o deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip
Expand-Archive deno.zip tools ; del deno.zip
# ffmpeg: download it from https://www.gyan.dev/ffmpeg/builds/ and copy ffmpeg.exe into tools\
#         (or run `winget install Gyan.FFmpeg` and copy the installed ffmpeg.exe)
```

The demucs model (about 80 MB) is downloaded into `models\` automatically the first time vocals are separated.

## Running

GUI:

```powershell
.venv\Scripts\pythonw.exe gui.py
```

You can also bundle it into an exe. The exe is a tiny launcher (about 8 MB) that simply runs the command above, so it must stay inside the project folder.

```powershell
uv pip install --python .venv\Scripts\python.exe pyinstaller
.venv\Scripts\pyinstaller.exe --onefile --noconsole --name ChartGen launcher.py   # dist\ChartGen.exe
```

Command line:

```powershell
run.bat "song.mp3" --keys 4 --difficulty normal,hard --vocals mix
```

| Option | Description | Default |
|---|---|---|
| `--keys N` | Number of lanes (1-9) | 4 |
| `--difficulty` | `easy,normal,hard,insane` (comma-separated) | normal |
| `--vocals` | `ignore` / `mix` / `only` | ignore |
| `--no-long-notes` | Turn long notes off | |
| `--max-ln-ratio` | Maximum share of long notes | 0.35 |
| `--sustain` | Long-note threshold (lower means more long notes) | 0.6 |
| `--ln-min-beats` / `--ln-max-beats` | Minimum / maximum long-note length (beats) | 1 / 4 |
| `--bpm` | Force a BPM | auto-detect |
| `--seed` | The same value gives the same chart | 0 |
| `--title` `--artist` `--creator` | Metadata | |
| `-o` | Output `.osz` path | next to the music |

Double-click the resulting `.osz` to open it in osu!.

## Project layout

| File | Role |
|---|---|
| `chartgen.py` | Chart generation (analysis → beat grid → onsets / long notes → lane assignment → `.osz`) |
| `game.py` | Test player. The scoring logic (`Session`) is separate from the GUI and audio |
| `gui.py` | Main window (Song / Chart / Library tabs + player) |
| `theme.py` | Colors, per-language font loading, ttk styles |
| `i18n.py` | Translation table for the four languages (`t("key")`). Edit this to fix a wording or add a language |
| `launcher.py` | exe launcher |
| `tests/test_session.py` | Scoring tests (`.venv\Scripts\python.exe tests\test_session.py`) |
| `tests/test_i18n.py` | Translation tests: missing keys, matching `{placeholders}`, characters missing from the fonts (the character check needs `pip install fonttools`) |

To change a translation, edit just that line in `i18n.py`. When you add a new text, fill in all four languages or `tests/test_i18n.py` will fail.

## Good to know

- The whole song is treated as a **single BPM**. Songs whose tempo changes may drift out of sync later on.
- The test player is built on Tk, so key-press timing is not precise. Use it to check a chart; if the sound feels late, adjust Sync (ms). While an IME is in Korean/Japanese/Chinese input mode, keys may arrive differently, so play in English input mode.
- The same song, options and `--seed` give the same chart, even when vocal separation is used. (demucs is run with `--shifts=0`.)
- Downloading YouTube videos may conflict with copyright and YouTube's terms. Use it for personal practice only, and check the rights to the original song before sharing a chart.

## Third-party

demucs (MIT), librosa (ISC), PyTorch (BSD), pygame (LGPL), yt-dlp (Unlicense), FFmpeg (LGPL/GPL depending on the build), Deno (MIT), Galmuri font (SIL OFL 1.1), Ark Pixel font (SIL OFL 1.1).
