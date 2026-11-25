"""Run engine tests with the project's Python environment when available."""
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parent
venv_python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
python = str(venv_python) if venv_python.is_file() else sys.executable
sys.exit(subprocess.call([python, '-m', 'unittest', '-v', 'test_receive', 'test_desktop_engine', 'test_desktop_host'], cwd=str(root)))
