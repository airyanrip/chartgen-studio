"""Launcher exe: starts gui.py with the bundled venv (pythonw) and exits.

Self-contained on purpose (the frozen exe cannot import the app's own modules), so the error message
carries its own four translations and picks one from the Windows UI language.
"""
import ctypes
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
PYW = APP_DIR / ".venv" / "Scripts" / "pythonw.exe"
GUI = APP_DIR / "gui.py"

MESSAGES = {   # primary language id -> text
    0x12: "실행 환경을 찾을 수 없습니다.\n\n{pyw}\n{gui}\n\n이 exe는 프로젝트 폴더 안에 두어야 합니다.",
    0x11: "実行環境が見つかりません。\n\n{pyw}\n{gui}\n\nこの exe はプロジェクトフォルダ内に置いてください。",
    0x04: "找不到运行环境。\n\n{pyw}\n{gui}\n\n此 exe 必须放在项目文件夹内。",
}
ENGLISH = "Could not find the runtime environment.\n\n{pyw}\n{gui}\n\nKeep this exe inside the project folder."

if not (PYW.exists() and GUI.exists()):
    lang = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    ctypes.windll.user32.MessageBoxW(0, MESSAGES.get(lang, ENGLISH).format(pyw=PYW, gui=GUI), "ChartGen", 0x10)
    sys.exit(1)

# CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP: the venv launcher may spawn a console python.exe,
# which must not pop up its own terminal window (DETACHED_PROCESS would let it do that).
NO_WINDOW = 0x08000000 | 0x00000200
subprocess.Popen([str(PYW), str(GUI)], cwd=str(APP_DIR), creationflags=NO_WINDOW, close_fds=True)
