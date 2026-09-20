"""ChartGen.exe: tiny launcher. Starts gui.py with the bundled venv (pythonw) and exits."""
import ctypes
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
PYW = APP_DIR / ".venv" / "Scripts" / "pythonw.exe"
GUI = APP_DIR / "gui.py"

if not (PYW.exists() and GUI.exists()):
    ctypes.windll.user32.MessageBoxW(
        0, f"실행 환경을 찾을 수 없습니다.\n\n{PYW}\n{GUI}\n\nChartGen.exe를 chartgen 폴더 안에 두어야 합니다.",
        "ChartGen", 0x10)
    sys.exit(1)

# CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP: the venv launcher may spawn a console python.exe,
# which must not pop up its own terminal window (DETACHED_PROCESS would let it do that).
NO_WINDOW = 0x08000000 | 0x00000200
subprocess.Popen([str(PYW), str(GUI)], cwd=str(APP_DIR), creationflags=NO_WINDOW, close_fds=True)
