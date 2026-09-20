"""Colours and ttk styling shared by the GUI and the game panel.

Palette: dark plum surfaces, hot-pink accent, lavender / light-pink highlights.
"""
import ctypes
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

BG = "#120D14"
PANEL = "#1E1622"
PANEL2 = "#251B2A"
BORDER = "#483042"
HEADER = "#18111A"
TEXT = "#EEE2EC"
MUTED = "#B296AC"
DIM = "#786470"
PINK = "#FF2D8A"
PINK_HOT = "#FF5FB4"
PINK_DEEP = "#5E1E44"
LPINK = "#FFB4D2"
LAV = "#BE8CE6"
GREEN = "#78DC8C"
RED = "#FF5050"
CYAN = "#12FFFF"
TITLEBAR_ACCENT = "#D6305A"

# Galmuri11 (pixel font, SIL OFL 1.1 - see fonts/LICENSE.txt). Loaded for this process only,
# nothing is installed system-wide. Falls back to Malgun Gothic if the files are missing.
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT = FONT_BOLD = "Malgun Gothic"
PIXEL = False


def load_fonts(root):
    """Register the bundled pixel font (call once a Tk root exists)."""
    global FONT, FONT_BOLD, PIXEL
    try:
        for name in ("Galmuri11.ttf", "Galmuri11-Bold.ttf"):
            ctypes.windll.gdi32.AddFontResourceExW(str(FONT_DIR / name), 0x10, 0)   # FR_PRIVATE
        fams = set(tkfont.families(root))
    except (OSError, AttributeError):
        return
    if "Galmuri11 Regular" in fams and "Galmuri11 Bold" in fams:
        FONT, FONT_BOLD, PIXEL = "Galmuri11 Regular", "Galmuri11 Bold", True


def f(size, bold=False):
    """Font tuple. Pixel fonts are sharpest at whole multiples of 8pt (=11px): 8, 16, 24, 32, 48."""
    if PIXEL:
        return (FONT_BOLD if bold else FONT, size)
    return (FONT, size, "bold") if bold else (FONT, size)


def apply(root):
    load_fonts(root)
    root.configure(bg=BG)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL2, bordercolor=BORDER,
                 lightcolor=BORDER, darkcolor=BORDER, troughcolor=PANEL2, focuscolor=BG,
                 insertcolor=TEXT, font=f(8))
    st.configure("TFrame", background=BG)
    st.configure("Panel.TFrame", background=PANEL)
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("Panel.TLabel", background=PANEL)
    st.configure("Muted.TLabel", foreground=MUTED)
    st.configure("Title.TLabel", background=HEADER, foreground=LPINK, font=f(16, True))
    st.configure("Sub.TLabel", background=HEADER, foreground=MUTED)
    st.configure("Song.TLabel", foreground=LPINK, font=f(11, True))
    st.configure("TLabelframe", background=BG, bordercolor=BORDER, relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=BG, foreground=LPINK, font=f(8, True))

    st.configure("TButton", background=PANEL2, foreground=TEXT, padding=(10, 5), borderwidth=1, relief="flat")
    st.map("TButton", background=[("disabled", PANEL), ("active", BORDER)],
           foreground=[("disabled", DIM)])
    st.configure("Accent.TButton", background=PINK, foreground="white", font=f(11, True),
                 padding=(10, 8), bordercolor=PINK, lightcolor=PINK, darkcolor=PINK)
    st.map("Accent.TButton", background=[("disabled", PINK_DEEP), ("active", PINK_HOT)],
           foreground=[("disabled", DIM)])

    for w in ("TCheckbutton", "TRadiobutton"):
        st.configure(w, background=BG, foreground=TEXT, indicatorcolor=PANEL2, indicatorbackground=PANEL2)
        st.map(w, indicatorcolor=[("selected", PINK)], background=[("active", BG)],
               foreground=[("disabled", DIM)])

    st.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    st.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(16, 7), borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", LPINK)],
           lightcolor=[("selected", PINK)])

    st.configure("Horizontal.TScale", background=BG, troughcolor=PANEL2)
    st.configure("Horizontal.TProgressbar", background=PINK, troughcolor=PANEL2, borderwidth=0)
    for w in ("TEntry", "TSpinbox", "TCombobox"):
        st.configure(w, fieldbackground=PANEL2, foreground=TEXT, insertcolor=TEXT, padding=3)
    st.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", PANEL2)], selectforeground=[("readonly", TEXT)])
    st.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=BG, arrowcolor=MUTED)

    root.option_add("*TCombobox*Listbox.background", PANEL2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", PINK)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*Font", f(8))
