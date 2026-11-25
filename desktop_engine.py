"""Command-line boundary used by the desktop application."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import sys

import receive


def main(argv=None):
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
    handler = partial(RangeRequestHandler, directory=str(folder))
    server = ThreadingHTTPServer(('0.0.0.0', args.port), handler)
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
