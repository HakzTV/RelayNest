import subprocess
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class DesktopEngineTests(unittest.TestCase):
    def test_receive_then_skip_then_update(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, destination = root / 'source', root / 'destination'
            source.mkdir()
            item = source / 'note.txt'
            item.write_text('old', encoding='utf-8')
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(source)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = 'http://127.0.0.1:%s/' % server.server_port
                command = [sys.executable, str(ROOT / 'desktop_engine.py'), 'receive', url, str(destination)]
                first = subprocess.run(command, capture_output=True, text=True, timeout=20)
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                self.assertEqual((destination / 'note.txt').read_text(), 'old')
                second = subprocess.run(command, capture_output=True, text=True, timeout=20)
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                self.assertIn('Skipped; local file is up to date', second.stdout)
                import os
                item.write_text('new', encoding='utf-8')
                new_time = (destination / 'note.txt').stat().st_mtime + 5
                os.utime(item, (new_time, new_time))
                third = subprocess.run(command, capture_output=True, text=True, timeout=20)
                self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
                self.assertEqual((destination / 'note.txt').read_text(), 'new')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_invalid_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, str(ROOT / 'desktop_engine.py'), 'receive', 'file:///tmp/', folder], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)

if __name__ == '__main__':
    unittest.main()
