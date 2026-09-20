#!/usr/bin/env python3
"""Auto rhythm-chart generator: audio -> osu!mania .osz (tap notes + long notes).

Pipeline
  1. (optional) split vocals / accompaniment
  2. fit a constant-BPM beat grid
  3. detect onsets, snap them to the grid, thin them to the difficulty's density
  4. turn sustained sounds into long notes
  5. assign lanes, write .osu and pack .osz

Vocals are configurable with --vocals:
  ignore : chart follows the accompaniment only (vocals are ignored)
  mix    : vocal onsets/sustains also become notes (sustained vocals -> long notes)
  only   : chart follows the vocals only
The detected vocal segments are always written to <name>.vocals.json when a vocal
stem is available, so lyrics (e.g. from Whisper) can be aligned separately later.
"""
import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np

SR = 22050
HOP = 512
# librosa's onset/beat frames come out about one hop (23 ms) after the real attack. Measured with a
# synthetic track of known onsets (+25 ms) and against drum-only onsets of a real song (+20..28 ms).
ONSET_LAG = HOP / SR

# divisor: grid slots per beat (2 = 1/8 notes, 4 = 1/16 notes)
PRESETS = {
    "easy":   dict(divisor=2, density=1.5, chord=0.00, max_chord=1, od=6),
    "normal": dict(divisor=2, density=2.5, chord=0.05, max_chord=2, od=7),
    "hard":   dict(divisor=4, density=4.0, chord=0.15, max_chord=2, od=8),
    "insane": dict(divisor=4, density=6.0, chord=0.30, max_chord=3, od=9),
}


# ---------------------------------------------------------------- audio / stems

def frame_time(f):
    return f * HOP / SR


def time_frame(t):
    return int(t * SR / HOP)


def normalize(x):
    p = np.percentile(x, 95)
    return x / p if p > 0 else x


def simple_separate(stereo):
    """Crude vocal split: mid channel, harmonic part, 150-4000 Hz. Use demucs for quality."""
    mix = stereo.mean(0)
    mid = (stereo[0] + stereo[1]) / 2
    H, _ = librosa.decompose.hpss(librosa.stft(mid))
    freqs = librosa.fft_frequencies(sr=SR)
    band = ((freqs >= 150) & (freqs <= 4000))[:, None]
    voc = librosa.istft(H * band, length=len(mix))
    return voc, mix - voc


def demucs_separate(path):
    with tempfile.TemporaryDirectory() as tmp:
        # --shifts=0: demucs' default random shift makes every run differ slightly; without it the
        # separation is byte-identical run to run, so the same --seed gives the same chart
        subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "--shifts=0", "-o", tmp, str(path)],
                       check=True)
        out = next(Path(tmp).glob("*/*"))
        voc, _ = librosa.load(out / "vocals.wav", sr=SR, mono=True)
        acc, _ = librosa.load(out / "no_vocals.wav", sr=SR, mono=True)
    return voc, acc


def load_stems(path, separator, need_vocals):
    stereo, _ = librosa.load(path, sr=SR, mono=False)
    if stereo.ndim == 1:
        stereo = np.stack([stereo, stereo])
    mix = stereo.mean(0)
    if not need_vocals and separator != "demucs":
        return mix, mix, None
    has_demucs = importlib.util.find_spec("demucs") is not None
    if separator == "demucs" or (separator == "auto" and has_demucs):
        print("separating vocals with demucs ...")
        voc, acc = demucs_separate(path)
    else:
        print("separating vocals with the simple fallback (install demucs for better results)")
        voc, acc = simple_separate(stereo)
    return mix, acc, voc


# ---------------------------------------------------------------- analysis

@dataclass
class Grid:
    period: float   # seconds per beat
    offset: float   # time of a beat, in [0, period)

    @property
    def bpm(self):
        return 60.0 / self.period


def fit_grid(env, forced_bpm=None):
    tempo, beats = librosa.beat.beat_track(onset_envelope=env, sr=SR, hop_length=HOP, units="time")
    beats = beats - ONSET_LAG
    if forced_bpm:
        period = 60.0 / forced_bpm
        times = np.arange(len(env)) * HOP / SR - ONSET_LAG
        best, best_phase = -1, 0.0
        for phase in np.linspace(0, period, 96, endpoint=False):
            grid = np.arange(phase, times[-1], period)
            score = np.interp(grid, times, env).sum()
            if score > best:
                best, best_phase = score, phase
        return Grid(period, best_phase)
    if len(beats) < 4:
        raise SystemExit("beat tracking failed (too few beats); try --bpm")
    # index beats by accumulating per-interval rounding, so quantization error never builds up
    idx = np.concatenate([[0], np.cumsum(np.maximum(1, np.round(np.diff(beats) / np.median(np.diff(beats)))))])
    period, icpt = np.polyfit(idx, beats, 1)  # robust to skipped beats
    return Grid(period, icpt % period)


@dataclass
class Cand:
    slot: int
    strength: float
    src: str          # 'acc' | 'voc'
    cent: float
    t: float = 0.0
    end: float = 0.0  # > t when it is a long note
    sustain: float = 0.0


def find_candidates(y, src, weight, grid, divisor):
    env = normalize(librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP))
    rms = normalize(librosa.feature.rms(y=y, hop_length=HOP)[0])
    cent = librosa.feature.spectral_centroid(y=y, sr=SR, hop_length=HOP)[0]
    step = grid.period / divisor
    out = []
    for f in librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP):
        slot = int(round((frame_time(f) - ONSET_LAG - grid.offset) / step))
        pos = slot % divisor
        pos_w = 1.0 if pos == 0 else (0.85 if pos * 2 == divisor else 0.7)
        out.append(Cand(slot, float(env[f]) * weight * pos_w, src, float(cent[min(f, len(cent) - 1)])))
    return out, rms


def vocal_segments(rms, thresh=0.15, min_len=0.2):
    on = np.convolve(rms, np.ones(5) / 5, mode="same") > thresh
    segs, start = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if frame_time(i - start) >= min_len:
                segs.append([round(frame_time(start), 3), round(frame_time(i), 3)])
            start = None
    return segs


# ---------------------------------------------------------------- chart building

def select(cands, grid, cfg, duration):
    """One candidate per slot, then keep the strongest N per 4-second window."""
    best = {}
    for c in cands:
        if c.slot not in best or c.strength > best[c.slot].strength:
            best[c.slot] = c
    step = grid.period / cfg["divisor"]
    windows = {}
    for c in best.values():
        c.t = grid.offset + c.slot * step
        if 0 <= c.t < duration:
            windows.setdefault(int(c.t // 4), []).append(c)
    keep_n = max(1, round(cfg["density"] * 4))
    picked = []
    for group in windows.values():
        group.sort(key=lambda c: -c.strength)
        picked += group[:keep_n]
    picked.sort(key=lambda c: c.t)
    return picked


def make_long_notes(notes, rms_by_src, grid, cfg, args):
    step = grid.period / cfg["divisor"]
    min_len = args.ln_min_beats * grid.period
    for n in notes:
        # a hold may span notes in other lanes (lane assignment keeps its own lane free)
        limit = n.t + args.ln_max_beats * grid.period
        # n.t is now the true attack time; the sustain analysis was tuned on the frame-lagged
        # position, so keep looking at the same place in the envelope
        f0, f1 = time_frame(n.t + ONSET_LAG), time_frame(limit + ONSET_LAG)
        rms = rms_by_src[n.src]
        f1 = min(f1, len(rms))
        if f1 - f0 < 16:
            continue
        # reference level is taken after the attack transient (~90-190 ms), not at the onset peak
        peak = rms[f0 + 4:f0 + 12].max()
        seg = np.convolve(rms[f0:f1], np.ones(5) / 5, mode="same")
        below = np.nonzero(seg[8:] < args.sustain * peak)[0]
        end_f = f1 if len(below) == 0 else f0 + 8 + below[0]
        end = min(frame_time(end_f), limit)
        end = grid.offset + np.floor((end - grid.offset) / step + 1e-6) * step
        if end - n.t >= min_len:
            n.end, n.sustain = end, (end - n.t) * float(np.mean(seg) / max(peak, 1e-9))
    # cap the long-note share, keep the most convincing ones
    lns = sorted((n for n in notes if n.end > n.t), key=lambda n: -n.sustain)
    for n in lns[int(len(notes) * args.max_ln_ratio):]:
        n.end = 0.0


def cap_long_notes(hits, ratio):
    """Enforce the long-note share on the final objects (lane assignment can drop notes, which
    would push the share above the cap). The shortest holds turn back into taps first."""
    lns = sorted((i for i, h in enumerate(hits) if h[2] > h[1]), key=lambda i: hits[i][2] - hits[i][1])
    for i in lns[:max(0, len(lns) - int(len(hits) * ratio))]:
        hits[i] = (hits[i][0], hits[i][1], 0.0)
    return hits


def assign_lanes(notes, keys, cfg, rng, ln_gap=0.0):
    """Returns [(lane, time, end)]. Low sounds lean to the left lanes, high to the right.

    ln_gap: a lane stays busy this long after a long note ends, so the player has time to
    release before the next note in that lane.
    """
    if not notes:
        return []
    cents = np.array([n.cent for n in notes])
    q = cents.argsort().argsort() / max(len(notes) - 1, 1)
    busy = np.full(keys, -1.0)
    last, out = [], []
    max_simul = max(2, keys // 2 + 1)
    smax = max(n.strength for n in notes)
    for n, quant in zip(notes, q):
        free = [l for l in range(keys) if busy[l] < n.t - 1e-3]
        if not free:
            continue
        holding = int((busy > n.t).sum())
        count = 1
        if (len(free) >= 2 and n.end <= n.t and holding + 2 <= max_simul and cfg["max_chord"] >= 2
                and rng.random() < cfg["chord"] * (0.5 + n.strength / smax)):
            count = 2 if rng.random() < 0.85 or cfg["max_chord"] < 3 else 3
            count = min(count, len(free), max_simul - holding)
        pref = quant * (keys - 1)
        cost = {l: abs(l - pref) * 0.6 + rng.random() * 1.2 + (2.5 if l in last else 0.0) for l in free}
        chosen = sorted(free, key=cost.get)[:count]
        for l in chosen:
            busy[l] = n.end + ln_gap if n.end > n.t else n.t
            out.append((l, n.t, n.end))
        last = chosen
    return out


# ---------------------------------------------------------------- output

def safe(s):
    return re.sub(r'[\\/:*?"<>|]', "_", s)


def osu_text(hits, keys, grid, meta, audio_name, version, od):
    lines = [
        "osu file format v14", "",
        "[General]", f"AudioFilename: {audio_name}", "AudioLeadIn: 0", "PreviewTime: -1",
        "Countdown: 0", "SampleSet: Soft", "StackLeniency: 0.7", "Mode: 3", "LetterboxInBreaks: 0",
        "SpecialStyle: 0", "WidescreenStoryboard: 0", "",
        "[Editor]", "DistanceSpacing: 1", "BeatDivisor: 4", "GridSize: 8", "TimelineZoom: 1", "",
        "[Metadata]", f"Title:{meta['title']}", f"TitleUnicode:{meta['title']}",
        f"Artist:{meta['artist']}", f"ArtistUnicode:{meta['artist']}", f"Creator:{meta['creator']}",
        f"Version:{version}", "Source:", "Tags:autochart", "BeatmapID:0", "BeatmapSetID:-1", "",
        "[Difficulty]", "HPDrainRate:8", f"CircleSize:{keys}", f"OverallDifficulty:{od}",
        "ApproachRate:5", "SliderMultiplier:1.4", "SliderTickRate:1", "",
        "[Events]", "//Background and Video events", "",
        "[TimingPoints]", f"{round(grid.offset * 1000)},{grid.period * 1000:.6f},4,2,0,60,1,0", "",
        "[HitObjects]",
    ]
    for lane, t, end in sorted(hits, key=lambda h: (h[1], h[0])):
        x = int((lane + 0.5) * 512 / keys)
        ms = round(t * 1000)
        if end > t:
            lines.append(f"{x},192,{ms},128,0,{round(end * 1000)}:0:0:0:0:")
        else:
            lines.append(f"{x},192,{ms},1,0,0:0:0:0:")
    return "\n".join(lines) + "\n"


def find_ffmpeg():
    """Prefer the copy bundled in tools/, so nothing depends on the system PATH."""
    local = Path(__file__).resolve().parent / "tools" / "ffmpeg.exe"
    return str(local) if local.exists() else (shutil.which("ffmpeg") or "ffmpeg")


def prepare_audio(path, tmp):
    if path.suffix.lower() in (".mp3", ".ogg"):
        return path
    out = Path(tmp) / "audio.mp3"
    subprocess.run([find_ffmpeg(), "-y", "-loglevel", "error", "-i", str(path), "-q:a", "2", str(out)], check=True)
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio")
    ap.add_argument("-o", "--out", help="output .osz (default: next to the audio)")
    ap.add_argument("--keys", type=int, default=4, help="lane count, 1-9 (default 4)")
    ap.add_argument("--difficulty", default="normal",
                    help="comma list of easy,normal,hard,insane (default normal)")
    ap.add_argument("--vocals", choices=["ignore", "mix", "only"], default="ignore",
                    help="how vocals affect the chart (default ignore)")
    ap.add_argument("--separator", choices=["auto", "demucs", "simple"], default="auto")
    ap.add_argument("--bpm", type=float, help="force a BPM instead of detecting it")
    ap.add_argument("--no-long-notes", action="store_true")
    ap.add_argument("--sustain", type=float, default=0.6,
                    help="loudness fraction a sound must hold to become a long note (default 0.6)")
    ap.add_argument("--ln-min-beats", type=float, default=1.0, help="min long-note length in beats")
    ap.add_argument("--ln-max-beats", type=float, default=4.0, help="max long-note length in beats")
    ap.add_argument("--max-ln-ratio", type=float, default=0.35, help="max share of long notes")
    ap.add_argument("--voc-weight", type=float, default=1.0, help="vocal onset weight in mix mode")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--title")
    ap.add_argument("--artist", default="Unknown")
    ap.add_argument("--creator", default="chartgen")
    args = ap.parse_args()

    if not 1 <= args.keys <= 9:
        ap.error("--keys must be 1-9")
    diffs = [d.strip() for d in args.difficulty.split(",")]
    for d in diffs:
        if d not in PRESETS:
            ap.error(f"unknown difficulty {d!r}")

    path = Path(args.audio)
    meta = dict(title=args.title or path.stem, artist=args.artist, creator=args.creator)
    mix, acc, voc = load_stems(path, args.separator, args.vocals != "ignore")
    duration = len(mix) / SR

    # tempo from the accompaniment (cleaner beat than with vocals) unless vocals-only
    beat_src = voc if (args.vocals == "only" and voc is not None) else acc
    grid = fit_grid(normalize(librosa.onset.onset_strength(y=beat_src, sr=SR, hop_length=HOP)), args.bpm)
    print(f"BPM {grid.bpm:.2f}, offset {grid.offset * 1000:.0f} ms, length {duration:.1f}s")

    if voc is not None:
        voc_rms = normalize(librosa.feature.rms(y=voc, hop_length=HOP)[0])
        segs = vocal_segments(voc_rms)
    else:
        segs = None

    with tempfile.TemporaryDirectory() as tmp:
        audio_file = prepare_audio(path, tmp)
        out_osz = Path(args.out) if args.out else path.with_suffix(".osz")
        with zipfile.ZipFile(out_osz, "w", zipfile.ZIP_DEFLATED) as z:
            audio_name = "audio" + audio_file.suffix.lower()
            z.write(audio_file, audio_name)
            for d in diffs:
                cfg = PRESETS[d]
                cands, rms_by_src = [], {}
                if args.vocals != "only":
                    c, rms_by_src["acc"] = find_candidates(acc, "acc", 1.0, grid, cfg["divisor"])
                    cands += c
                if args.vocals != "ignore":
                    c, rms_by_src["voc"] = find_candidates(voc, "voc", args.voc_weight, grid, cfg["divisor"])
                    cands += c
                notes = select(cands, grid, cfg, duration)
                if not args.no_long_notes:
                    make_long_notes(notes, rms_by_src, grid, cfg, args)
                rng = np.random.default_rng(args.seed)
                hits = assign_lanes(notes, args.keys, cfg, rng, ln_gap=grid.period / cfg["divisor"])
                hits = cap_long_notes(hits, args.max_ln_ratio)
                n_ln = sum(1 for h in hits if h[2] > h[1])
                print(f"[{d}] {len(hits)} objects ({n_ln} long notes), {len(hits) / duration:.2f}/s")
                version = f"{args.keys}K {d.capitalize()}"
                osu = osu_text(hits, args.keys, grid, meta, audio_name, version, cfg["od"])
                name = safe(f"{meta['artist']} - {meta['title']} ({meta['creator']}) [{version}].osu")
                z.writestr(name, osu)

    if segs is not None:
        side = out_osz.with_suffix(".vocals.json")
        side.write_text(json.dumps({"vocal_segments": segs}, indent=1), encoding="utf-8")
        print(f"vocal segments -> {side}")
    print(f"wrote {out_osz}")


if __name__ == "__main__":
    main()
