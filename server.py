from http.server import ThreadingHTTPServer
from pathlib import Path
from RangeHTTPServer import RangeRequestHandler
import os

SHARE_FOLDER = Path(r"C:\Users\TelvinCaesarVarfley\.codex")
PORT = 8000

os.chdir(SHARE_FOLDER)
RangeRequestHandler.index_pages = ()

print("Sharing: " + str(SHARE_FOLDER))
print("Range server running on port " + str(PORT))
print("Keep this window open while transferring.")

server = ThreadingHTTPServer(("0.0.0.0", PORT), RangeRequestHandler)
server.serve_forever()
