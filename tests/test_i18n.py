"""Translation tests: python tests\\test_i18n.py   (glyph checks need `pip install fonttools`, otherwise skipped)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import i18n  # noqa: E402

failed = []
def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + (f"   {info}" if not cond and info else ""))
    if not cond:
        failed.append(name)

LANG_CODES = list(i18n.LANGS)
hangul = re.compile(r"[가-힣]")
kana = re.compile(r"[぀-ヿ]")
placeholders = lambda s: set(re.findall(r"\{(\w+)\}", s))

# ---- table integrity
check("four languages are listed", LANG_CODES == ["ko", "en", "ja", "zh"])
missing = [k for k in i18n.keys() if any(not i18n.raw(k)[c].strip() for c in LANG_CODES)]
check("no key has an empty translation", not missing, str(missing))
bad_ph = [k for k in i18n.keys() if len({frozenset(placeholders(v)) for v in i18n.raw(k).values()}) != 1]
check("{placeholders} are identical in every language", not bad_ph, str(bad_ph))
check("Korean strings contain Hangul (or are language-neutral)",
      all(hangul.search(i18n.raw(k)["ko"]) or not re.search(r"[A-Za-z가-힣]", i18n.raw(k)["ko"].replace("URL", "").replace("BPM", ""))
          for k in i18n.keys()))
leak = [k for k in i18n.keys() if any(hangul.search(i18n.raw(k)[c]) for c in ("en", "ja", "zh"))]
check("no Hangul leaks into en / ja / zh", not leak, str(leak))
not_ja = [k for k in i18n.keys() if not (kana.search(i18n.raw(k)["ja"]) or re.search(r"[一-鿿]", i18n.raw(k)["ja"])
                                          or i18n.raw(k)["ja"] in ("URL", "BPM"))]
check("Japanese strings contain Japanese script", not not_ja, str(not_ja))

# ---- every text in the code is in the table, and every table entry is used
src = "".join((ROOT / f).read_text(encoding="utf-8") for f in ("gui.py", "game.py"))
literals = set(re.findall(r'"([a-z_]+\.[a-z_]+)"', src))                       # every "group.name" literal
requested = set(re.findall(r'\btr\(\s*"([\w.]+)"', src))                         # keys handed to tr()/reg()/_say()...
requested |= set(re.findall(r'reg\([^\n]*?\),\s*"([\w.]+)"', src))
requested |= set(re.findall(r'\b(?:on_status|_say)\(\s*"([\w.]+)"', src))
requested |= set(re.findall(r'\bscale\(\d, \d, "([\w.]+)"', src))
requested = {k for k in requested if not k.endswith(".")}
dynamic = {f"diff.{d}" for d in ("easy", "normal", "hard", "insane")} | {f"vocal.{v}" for v in ("ignore", "mix", "only")}   # built as "diff." + name
used = (literals & set(i18n.keys())) | dynamic
unknown = sorted(k for k in requested if k not in i18n.keys())
check("every key used in the code exists in the table", not unknown, str(unknown))
unused = sorted(k for k in i18n.keys() if k not in used)
check("no unused keys in the table", not unused, str(unused))
leftover = [(f, n) for f in ("gui.py", "game.py", "theme.py") for n, line in enumerate((ROOT / f).read_text(encoding="utf-8").splitlines(), 1)
            if hangul.search(line) and not line.lstrip().startswith(("#", '"""'))]
check("no hard-coded Korean UI text left in gui.py / game.py / theme.py", not leftover, str(leftover[:5]))

# ---- formatting works for every key in every language
def sample(k):
    return {p: "X" for p in placeholders(i18n.raw(k)["en"])}
try:
    for code in LANG_CODES:
        i18n.set_lang(code)
        for k in i18n.keys():
            i18n.t(k, **sample(k))
    ok = True
except Exception as e:  # noqa: BLE001
    ok = False; print("   ", e)
check("t() formats every key in every language", ok)
i18n.set_lang("xx"); check("unknown language falls back to English", i18n.get_lang() == "en")
check("detect_lang returns a supported code", i18n.detect_lang() in i18n.LANGS)

# ---- glyph coverage of the bundled pixel fonts (optional)
try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("SKIP glyph coverage (fonttools not installed)")
else:
    cmaps = {n: TTFont(ROOT / "fonts" / n).getBestCmap() for n in ("Galmuri11.ttf", "ArkPixel12-zh_cn.ttf")}
    plan = {"ko": "Galmuri11.ttf", "en": "Galmuri11.ttf", "ja": "Galmuri11.ttf", "zh": "ArkPixel12-zh_cn.ttf"}
    for code, font in plan.items():
        chars = set("".join(i18n.raw(k)[code] for k in i18n.keys())) - set("{}\n ")
        miss = sorted(c for c in chars if ord(c) not in cmaps[font])
        check(f"{code}: every character exists in {font}", not miss, "".join(miss))

print(f"\n{'ALL PASSED' if not failed else 'FAILED: ' + str(failed)}")
sys.exit(1 if failed else 0)
