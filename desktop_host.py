"""Python desktop host for RelayNest's existing interface and transfer engine."""
import multiprocessing
import os
import traceback
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def configure_webview_debugging(settings, environ):
    """Enable a WebView2 debugging port only when explicitly requested for testing."""
    value = environ.get('RELAYNEST_WEBVIEW_DEBUG_PORT')
    if value is None:
        return
    try:
        port = int(value)
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise ValueError('RELAYNEST_WEBVIEW_DEBUG_PORT must be a port from 1 to 65535.')
    settings['REMOTE_DEBUGGING_PORT'] = port

class QueueWriter:
    """Stream worker output to the desktop without a separate executable."""
    encoding = 'utf-8'

    def __init__(self, output):
        self.output = output

    def write(self, text):
        if text:
            self.output.put(str(text))
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


def run_worker(mode, value, target, output):
    sys.stdout = QueueWriter(output)
    sys.stderr = sys.stdout
    try:
        import desktop_engine
        result = desktop_engine.main([mode, value, target])
        raise SystemExit(result)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


class DesktopAPI:
    def __init__(self):
        self._window = None
        self._process = None
        self._lock = threading.Lock()
        self._events = Queue()
        self._stopping = False

    def choose_folder(self):
        import webview
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None

    def start(self, mode, value, target):
        if not isinstance(value, str) or not isinstance(target, str):
            return {'ok': False, 'error': 'Invalid input.'}
        value, target = value.strip(), target.strip()
        if mode == 'receive':
            try:
                url = urlsplit(value)
                valid = (url.scheme in ('http', 'https') and url.hostname and
                         not url.username and not url.password and not url.query and not url.fragment)
                _ = url.port
            except ValueError:
                valid = False
            if not valid or not Path(target).is_dir() or not target:
                return {'ok': False, 'error': 'Enter a valid HTTP or HTTPS address and choose an existing destination folder.'}
        elif mode == 'send':
            if not value or not Path(value).is_dir():
                return {'ok': False, 'error': 'Choose an existing folder to share.'}
            try:
                port = int(target)
                if not 1 <= port <= 65535:
                    raise ValueError()
            except ValueError:
                return {'ok': False, 'error': 'Enter a valid port between 1 and 65535.'}
        else:
            return {'ok': False, 'error': 'Invalid operation.'}
        with self._lock:
            if self._process is not None:
                return {'ok': False, 'error': 'A session is already running.'}
            output = multiprocessing.get_context('spawn').Queue()
            process = multiprocessing.get_context('spawn').Process(
                target=run_worker, args=(mode, value, target, output), daemon=True
            )
            try:
                process.start()
            except (OSError, RuntimeError) as error:
                output.close()
                return {'ok': False, 'error': 'Unable to start the transfer engine: ' + str(error)}
            self._process = process
            self._stopping = False
            self._events.put({'type': 'started', 'mode': mode})
            threading.Thread(target=self._watch, args=(process, mode, output), daemon=True).start()
        return {'ok': True}

    def _watch(self, process, mode, output):
        while True:
            try:
                text = output.get(timeout=0.1)
                self._events.put({'type': 'output', 'text': text})
            except Empty:
                if not process.is_alive():
                    break
            except (EOFError, OSError, ValueError):
                break
        process.join()
        output.close()
        with self._lock:
            stopped = self._stopping
            self._process = None
            self._stopping = False
            self._events.put({'type': 'finished', 'mode': mode, 'code': process.exitcode, 'stopped': stopped})

    def stop(self):
        with self._lock:
            if self._process is not None:
                self._stopping = True
                self._process.terminate()
        return True

    def poll(self):
        events = []
        while len(events) < 100:
            try:
                events.append(self._events.get_nowait())
            except Empty:
                break
        return events


def main():
    try:
        import webview
    except ImportError:
        print('Install desktop dependencies: python -m pip install -r requirements-desktop.txt', file=sys.stderr)
        return 1
    configure_webview_debugging(webview.settings, os.environ)
    api = DesktopAPI()
    window = webview.create_window('RelayNest', (ROOT / 'desktop' / 'index.html').as_uri(), js_api=api, width=1280, height=850, min_size=(650, 580), background_color='#0d1217')
    api._window = window
    window.events.closed += api.stop
    webview.start()
    return 0


if __name__ == '__main__':
    multiprocessing.freeze_support()
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from package_self_test import run
        sys.exit(run(sys.argv[2]))
    sys.exit(main())
