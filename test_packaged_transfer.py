"""Exercise the actual packaged executable's sender and receiver over loopback."""
import json
from pathlib import Path
import subprocess
import tempfile

APP = Path(__file__).resolve().parent / 'dist' / 'RelayNest.exe'


def main():
    if not APP.is_file():
        raise RuntimeError('Build the Windows executable first.')
    with tempfile.TemporaryDirectory() as directory:
        result_path = Path(directory) / 'result.json'
        result = subprocess.run([str(APP), '--self-test', str(result_path)], timeout=120)
        if not result_path.is_file():
            raise RuntimeError('Packaged app did not write a self-test result; exit code: %s' % result.returncode)
        data = json.loads(result_path.read_text(encoding='utf-8'))
        if result.returncode != 0 or not data.get('ok'):
            raise RuntimeError(data.get('message', 'Packaged self-test failed'))
        print(data['message'])


if __name__ == '__main__':
    main()
