import multiprocessing.process
import socket
import urllib.request
import tempfile
import threading
import time
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from desktop_host import DesktopAPI, configure_webview_debugging


class DesktopAPITests(unittest.TestCase):
    def test_webview_debug_port_is_explicit_and_validated(self):
        settings = {'REMOTE_DEBUGGING_PORT': None}
        configure_webview_debugging(settings, {})
        self.assertIsNone(settings['REMOTE_DEBUGGING_PORT'])
        configure_webview_debugging(settings, {'RELAYNEST_WEBVIEW_DEBUG_PORT': '19222'})
        self.assertEqual(settings['REMOTE_DEBUGGING_PORT'], 19222)
        with self.assertRaises(ValueError):
            configure_webview_debugging(settings, {'RELAYNEST_WEBVIEW_DEBUG_PORT': '65536'})

    def test_rejects_invalid_source_and_destination(self):
        api = DesktopAPI()
        self.assertFalse(api.start('receive', 'file:///tmp/', 'missing')['ok'])
        self.assertFalse(api.start('receive', 'http://localhost:8000/', 'missing')['ok'])
        self.assertFalse(api.start('send', 'missing', '8000')['ok'])

    def test_share_can_stop_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            api = DesktopAPI()
            url = 'http://127.0.0.1:%s/' % port
            try:
                for _ in range(2):
                    result = api.start('send', directory, str(port))
                    self.assertTrue(result['ok'], result)
                    self.assertFalse(api.start('send', directory, str(port))['ok'])
                    for _ in range(200):
                        try:
                            with urllib.request.urlopen(url, timeout=1):
                                break
                        except OSError:
                            time.sleep(.05)
                    else:
                        self.fail('Share did not start')
                    events = []
                    for _ in range(100):
                        events.extend(api.poll())
                        if any(e['type'] == 'peer_activity' and e['active'] == 0 for e in events) and any(e['type'] == 'share_ready' for e in events):
                            break
                        time.sleep(.05)
                    self.assertTrue(any(e['type'] == 'share_ready' and e['port'] == port for e in events), events)
                    self.assertTrue(any(e['type'] == 'peer_activity' and e['address'] == '127.0.0.1' for e in events), events)
                    api.stop()
                    for _ in range(200):
                        events.extend(api.poll())
                        if any(event['type'] == 'finished' for event in events):
                            break
                        time.sleep(.05)
                    self.assertTrue(any(event['type'] == 'finished' and event['stopped'] for event in events), events)
            finally:
                api.stop()

    def test_receive_process_reports_real_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            source.mkdir()
            target.mkdir()
            (source / 'example.txt').write_text('sample', encoding='utf-8')
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(source)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            api = DesktopAPI()
            try:
                result = api.start('receive', 'http://127.0.0.1:%s/' % server.server_port, str(target))
                self.assertTrue(result['ok'], result)
                self.assertIsInstance(api._process, multiprocessing.process.BaseProcess)
                events = []
                for _ in range(300):
                    events.extend(api.poll())
                    if any(event['type'] == 'finished' for event in events):
                        break
                    time.sleep(.05)
                self.assertTrue(any(event['type'] == 'receive_connected' for event in events), events)
                self.assertEqual((target / 'example.txt').read_text(), 'sample')
                self.assertTrue(any(event['type'] == 'output' and 'Completed:' in event['text'] for event in events))
                self.assertTrue(any(event['type'] == 'finished' and event['code'] == 0 for event in events), events)
            finally:
                api.stop()
                server.shutdown()
                server.server_close()
                thread.join()

if __name__ == '__main__':
    unittest.main()
