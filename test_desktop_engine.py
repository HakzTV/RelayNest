import subprocess
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import desktop_engine

ROOT = Path(__file__).resolve().parent


class DesktopEngineTests(unittest.TestCase):
    def test_local_addresses_filter_loopback_and_prioritize_route(self):
        entries = [(None, None, None, None, ('127.0.0.1', 0)),
                   (None, None, None, None, ('10.0.0.2', 0)),
                   (None, None, None, None, ('192.168.1.7', 0))]
        class Probe:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def connect(self, address): pass
            def getsockname(self): return ('192.168.1.7', 1234)
        with patch('desktop_engine.socket.getaddrinfo', return_value=entries), patch('desktop_engine.socket.socket', return_value=Probe()):
            self.assertEqual(desktop_engine.local_ipv4_addresses(), ['192.168.1.7', '10.0.0.2'])

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
                self.assertIn('Data transferred: 3 B', first.stdout)
                self.assertRegex(first.stdout, r'Transfer duration: \d+\.\d{2} s')
                second = subprocess.run(command, capture_output=True, text=True, timeout=20)
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                self.assertIn('Skipped; local file is up to date', second.stdout)
                self.assertIn('Data transferred: 0 B', second.stdout)
                import os
                item.write_text('new', encoding='utf-8')
                new_time = (destination / 'note.txt').stat().st_mtime + 5
                os.utime(item, (new_time, new_time))
                third = subprocess.run(command, capture_output=True, text=True, timeout=20)
                self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
                self.assertEqual((destination / 'note.txt').read_text(), 'new')
                self.assertIn('Data transferred: 3 B', third.stdout)
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
