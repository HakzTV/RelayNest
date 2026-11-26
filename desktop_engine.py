"""Command-line boundary used by the desktop application."""
import argparse
import ipaddress
import socket
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import sys

import receive


def local_ipv4_addresses():
    """Discover candidate local IPv4 addresses without sending network traffic."""
    addresses = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(item[4][0])
    except OSError:
        pass
    # UDP connect selects a route locally; no packet is sent.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 9))
            preferred = probe.getsockname()[0]
            addresses.add(preferred)
    except OSError:
        preferred = None
    usable = []
    for address in addresses:
        try:
            ip = ipaddress.IPv4Address(address)
        except ValueError:
            continue
        if not ip.is_loopback and not ip.is_unspecified and not ip.is_multicast:
            usable.append(address)
    return sorted(usable, key=lambda address: (address != preferred, ipaddress.IPv4Address(address)))


def main(argv=None, event_callback=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    receiver = commands.add_parser('receive')
    receiver.add_argument('url')
    receiver.add_argument('destination')
    sender = commands.add_parser('send')
    sender.add_argument('folder')
    sender.add_argument('port', type=int)
    args = parser.parse_args(argv)
    if args.command == 'receive':
        parsed = urlsplit(args.url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
            parser.error('Enter a valid HTTP or HTTPS directory URL without credentials, query, or fragment.')
        if event_callback is not None:
            connected = [False]
            def on_directory_loaded(url):
                if not connected[0]:
                    connected[0] = True
                    event_callback({'type': 'receive_connected'})
            receive.directory_loaded_callback = on_directory_loaded
        receive.BASE_URL = args.url.rstrip('/') + '/'
        receive.DESTINATION = Path(args.destination).expanduser().resolve()
        receive.STATE_DIRECTORY = receive.DESTINATION / '.transfer-state'
        receive.PARTIAL_DIRECTORY = receive.STATE_DIRECTORY / 'partials'
        receive.CHECKPOINT_FILE = receive.STATE_DIRECTORY / 'checkpoint.sqlite3'
        receive.LOG_FILE = receive.STATE_DIRECTORY / 'transfer-failures.log'
        return receive.main()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir() or not 1 <= args.port <= 65535:
        parser.error('Choose an existing folder and a port between 1 and 65535.')
    try:
        from RangeHTTPServer import RangeRequestHandler
    except ImportError:
        parser.error('Install the sender dependency with python -m pip install -r requirements.txt.')
    RangeRequestHandler.index_pages = ()

    class ActivityHandler(RangeRequestHandler):
        def send_response(self, code, message=None):
            super().send_response(code, message)
            if event_callback is not None and code in (200, 206) and not getattr(self, '_counted', False):
                self._counted = True
                with self.server.activity_lock:
                    self.server.active_requests += 1
                    event_callback({'type': 'peer_activity', 'address': self.client_address[0], 'active': self.server.active_requests})

        def finish_activity(self):
            if getattr(self, '_counted', False):
                with self.server.activity_lock:
                    self.server.active_requests -= 1
                    event_callback({'type': 'peer_activity', 'address': self.client_address[0], 'active': self.server.active_requests})
                self._counted = False

        def do_GET(self):
            try:
                super().do_GET()
            finally:
                self.finish_activity()

        def do_HEAD(self):
            try:
                super().do_HEAD()
            finally:
                self.finish_activity()

    handler = partial(ActivityHandler, directory=str(folder))
    server = ThreadingHTTPServer(('0.0.0.0', args.port), handler)
    server.activity_lock = threading.Lock()
    server.active_requests = 0
    if event_callback is not None:
        event_callback({'type': 'share_ready', 'addresses': local_ipv4_addresses(), 'port': args.port})
    print('Sharing: ' + str(folder), flush=True)
    print('Listening on port: ' + str(args.port), flush=True)
    print('Use your machine IP address to connect from another device.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
