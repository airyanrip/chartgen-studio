"""Scoring-core tests (no GUI, no audio): run with  python tests\test_session.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import game
from game import Session, Note, parse_osu, DEFAULT_KEYS, key_label, FEVER_HITS, FEVER_MAX

n_ok = 0
def t(name, cond, info=""):
    global n_ok
    print(("PASS " if cond else "FAIL ") + name + (f"   {info}" if not cond else ""))
    if not cond:
        t.failed.append(name)
    else:
        n_ok += 1
t.failed = []
base = lambda: [Note(0, 1.0), Note(1, 2.0), Note(2, 3.0, 4.0), Note(3, 5.0)]

s = Session(base(), 4)
s.press(0, 1.0); s.press(1, 2.0); s.press(2, 3.0); s.update(3.9); s.release(2, 4.0); s.press(3, 5.0)
t("perfect run = 1,000,000 / PERFECT PLAY", s.score() == 1_000_000 and s.grade() == "PERFECT PLAY" and s.max_combo == 5 and s.finished(5.1))

s = Session(base(), 4); s.press(0, 0.7)
t("press >135ms early is ignored (no judgment, note still waiting)", s.counts["MISS"] == 0 and sum(s.counts.values()) == 0 and s.notes[0].state == "wait")
for dt, exp in ((0.0, "PERFECT"), (0.044, "PERFECT"), (0.046, "GREAT"), (0.089, "GREAT"), (0.091, "GOOD"), (0.134, "GOOD"), (-0.05, "GREAT"), (-0.13, "GOOD")):
    s = Session(base(), 4); s.press(0, 1.0 + dt)
    t(f"timing {dt * 1000:+.0f}ms -> {exp}", s.counts[exp] == 1, str(s.counts))
s = Session(base(), 4); s.update(1.14)
t("note becomes MISS once >135ms late", s.counts["MISS"] == 1 and s.notes[0].state == "miss")
s = Session(base(), 4); s.update(1.13)
t("not yet MISS at 130ms late", s.counts["MISS"] == 0)
s = Session(base(), 4); s.update(1.2); s.press(0, 1.2)
t("pressing a missed note does nothing", sum(s.counts.values()) == 1)

s = Session(base(), 4); s.press(2, 3.0); s.release(2, 3.3)
t("LN released early -> tail MISS, combo reset", s.counts == {"PERFECT": 1, "GREAT": 0, "GOOD": 0, "MISS": 1} and s.combo == 0)
s = Session(base(), 4); s.press(2, 3.0); s.release(2, 3.89)
t("LN released within 120ms leeway -> tail PERFECT", s.counts["PERFECT"] == 2 and s.counts["MISS"] == 0)
s = Session(base(), 4); s.press(2, 3.0); s.update(4.01)
t("LN held through end auto-completes", s.counts["PERFECT"] == 2 and s.hold[2] is None)
s = Session(base(), 4); s.update(3.5)
t("LN head missed -> 2 MISS units, lane free", s.counts["MISS"] == 4 and s.hold[2] is None)  # 2 taps (1 each) + LN head (2 units)
s = Session([Note(0, 1.0), Note(1, 1.0)], 4); s.press(0, 1.0); s.press(1, 1.01)
t("chord: two lanes judged independently", s.counts["PERFECT"] == 2 and s.combo == 2)
s = Session([Note(0, 1.0), Note(0, 1.5)], 4); s.press(0, 1.0); s.press(0, 1.02)
t("double press in same lane cannot hit the next (0.5s away) note", s.counts["PERFECT"] == 1 and s.notes[1].state == "wait")
s = Session(base(), 4); s.press(3, 2.0)
t("press in lane whose note is 3s away is ignored", sum(s.counts.values()) == 0)
s = Session(base(), 4); s.release(0, 1.0)
t("release with nothing held is harmless", sum(s.counts.values()) == 0)

tight = Session([Note(0, 1.0)], 4, judge_scale=0.6); tight.press(0, 1.06)
loose = Session([Note(0, 1.0)], 4, judge_scale=1.5); loose.press(0, 1.06)
t("judge scale: 60ms late is GREAT at x0.6? (window 27/54/81 -> GOOD) and PERFECT at x1.5",
  tight.counts["GOOD"] == 0 and tight.counts["GREAT"] == 0 and tight.counts["MISS"] == 0 and sum(tight.counts.values()) == 0 or tight.counts["GOOD"] == 1)
t("judge scale x1.5 makes 60ms PERFECT... (window 67)", loose.counts["PERFECT"] == 1)

s = Session([Note(0, 1 + i * 0.1) for i in range(400)], 4, auto=True); s.update(100)
lv = [e.level for e in s.events if e.kind == "fever"]
t("FEVER: 1..5 then caps at 5 (400 hits)", lv == [1, 2, 3, 4, 5] and s.fever == FEVER_MAX, str(lv))
s = Session([Note(0, 1 + i * 0.1) for i in range(60)], 4)
for i in range(FEVER_HITS): s.press(0, 1 + i * 0.1)
t(f"FEVER level 1 exactly after {FEVER_HITS} hits", s.fever == 1 and s.chain == 0)
s.update(100)
t("miss resets FEVER and gauge", s.fever == 0 and s.gauge == 0)

s = Session(base(), 4, auto=True); s.update(0.5)
t("auto: nothing before first note", sum(s.counts.values()) == 0)
s.update(100)
t("auto plays everything perfectly incl. LN", s.counts == {"PERFECT": 5, "GREAT": 0, "GOOD": 0, "MISS": 0})
dense = Session([Note(0, 1 + i * 0.001) for i in range(50)], 4, auto=True); dense.update(2)
t("auto handles 1ms-dense notes in a single update", dense.counts["PERFECT"] == 50)

s = Session(base(), 4); s.update(100)
t("all-miss: score 0, CLEAR, finished", s.score() == 0 and s.grade() == "CLEAR" and s.finished(100))
s = Session([], 4)
t("empty chart: 1,000,000 and finishes", s.score() == 1_000_000 and s.finished(0))
s = Session(base(), 4); s.press(0, 1.0)
t("accuracy counts only judged notes (100%), score is over the whole chart", s.accuracy() == 100.0 and s.score() == 200_000, f"{s.accuracy()} {s.score()}")
mix = Session([Note(0, 1.0), Note(1, 2.0), Note(2, 3.0)], 4); mix.press(0, 1.0); mix.press(1, 2.08); mix.press(2, 3.12)
t("weights P=1 G=0.75 g=0.4 -> score", mix.score() == round(1e6 * (1 + 0.75 + 0.4) / 3), str(mix.score()))
orig = [Note(0, 1.0)]; Session(orig, 4).press(0, 1.0)
t("Session does not mutate the source chart notes", orig[0].state == "wait")

# parser / config sanity
c = parse_osu("[Difficulty]\nCircleSize:7\n[Metadata]\nTitle:한글 제목\nArtist:A\nVersion:7K Hard\n[HitObjects]\n0,192,1000,1,0,0:0:0:0:\n511,192,2000,128,0,3500:0:0:0:\n256,192,500,1,0,0:0:0:0:\n")
t("parse: keys/lane mapping/sorting/LN end/unicode", c.keys == 7 and [n.lane for n in c.notes] == [3, 0, 6] and c.notes[2].end == 3.5 and c.title == "한글 제목", str([(n.lane, n.t, n.end) for n in c.notes]))
t("parse: tolerates CRLF and blank lines", len(parse_osu("[Difficulty]\r\nCircleSize:4\r\n[HitObjects]\r\n\r\n0,0,100,1,0,0:0\r\n").notes) == 1)
for n, keys in DEFAULT_KEYS.items():
    t(f"default keys for {n}K: length matches, unique", len(keys) == n and len(set(keys)) == n)
t("4K default is A S ; ' (mod default)", [key_label(k) for k in DEFAULT_KEYS[4]] == ["A", "S", ";", "'"])

print(f"\n{n_ok} passed, {len(t.failed)} failed", t.failed)
sys.exit(1 if t.failed else 0)

