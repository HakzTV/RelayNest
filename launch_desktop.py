"""Launch with the project virtual environment when it exists."""
from pathlib import Path
import multiprocessing
import os
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    venv_python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if venv_python.is_file() and Path(sys.executable).resolve() != venv_python.resolve():
        return subprocess.call([str(venv_python), str(root / 'desktop_host.py')], cwd=str(root))
    from desktop_host import main as desktop_main
    return desktop_main()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
