"""End-to-end transfer check invoked explicitly by the packaged app."""
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import traceback
import urllib.request
from desktop_host import DesktopAPI


def wait_for_session(api, timeout=60):
    events = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events.extend(api.poll())
        finished = [item for item in events if item['type'] == 'finished']
        if finished:
            if finished[-1]['code'] != 0:
                raise RuntimeError('Transfer failed: ' + ''.join(item.get('text', '') for item in events))
            return ''.join(item.get('text', '') for item in events)
        time.sleep(.05)
    api.stop()
    raise RuntimeError('Transfer timed out.')


def run(result_path):
    sender = DesktopAPI()
    receiver = DesktopAPI()
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'destination'
            source.mkdir()
            target.mkdir()
            (source / 'nested').mkdir()
            item = source / 'nested' / 'example.txt'
            item.write_text('first', encoding='utf-8')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            result = sender.start('send', str(source), str(port))
            if not result['ok']:
                raise RuntimeError(result['error'])
            url = 'http://127.0.0.1:%s/' % port
            deadline = time.monotonic() + 30
            while True:
                if time.monotonic() > deadline:
                    raise RuntimeError('Packaged sender did not start.')
                try:
                    with urllib.request.urlopen(url, timeout=1):
                        break
                except OSError:
                    if any(e['type'] == 'finished' for e in sender.poll()):
                        raise RuntimeError('Sender exited before it was ready.')
                    time.sleep(.1)
            def receive():
                started = receiver.start('receive', url, str(target))
                if not started['ok']:
                    raise RuntimeError(started['error'])
                return wait_for_session(receiver)
            receive()
            copied = target / 'nested' / 'example.txt'
            if copied.read_text(encoding='utf-8') != 'first':
                raise RuntimeError('Initial copy did not match.')
            if 'Skipped; local file is up to date' not in receive():
                raise RuntimeError('Repeat transfer did not report a skip.')
            item.write_text('newer', encoding='utf-8')
            newer = copied.stat().st_mtime + 5
            os.utime(item, (newer, newer))
            receive()
            if copied.read_text(encoding='utf-8') != 'newer':
                raise RuntimeError('Newer source was not copied.')
            status = {'ok': True, 'message': 'Sender and receiver passed: copy, repeat skip, newer source update.'}
    except Exception:
        status = {'ok': False, 'message': traceback.format_exc()}
    finally:
        sender.stop()
        receiver.stop()
    Path(result_path).write_text(json.dumps(status), encoding='utf-8')
    return 0 if status['ok'] else 1
