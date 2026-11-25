# RelayNest

RelayNest copies folders between machines on a trusted network. The sending machine shares a folder using a range-capable HTTP server; the receiving machine scans its directory listings and downloads files in parallel. The project is a starting point for future improvements.

## Requirements

- Python 3.8 or newer on both machines.
- Network access from the receiver to the sender on port 8000 (or your chosen port).
- `RangeHTTPServer` installed on the sender. The receiver uses Python's standard library only.

## Start the sender

In PowerShell on the machine **with the files**, from the RelayNest project folder:

```powershell
py -m pip install -r requirements.txt
py server.py
```

Set `SHARE_FOLDER` in `server.py` to the folder you want to share and change `PORT` there if needed. The supplied default is `C:\Users\TelvinCaesarVarfley\.codex`; confirm that this is the folder you intend to expose before starting the server. Run `ipconfig` to find the sender's IPv4 address. Leave the server running until the transfer finishes; press Ctrl+C to stop it.

## Receive files

On the other machine, set `BASE_URL` and `DESTINATION` near the top of `receive.py` to the sender's IP address and your chosen destination. Then run the receiver from the RelayNest folder:

```powershell
py receive.py
```

The receiver creates the destination and its subfolders. Change `MAX_WORKERS` in `receive.py` to adjust the default of six simultaneous downloads. The receiver also works with an existing compatible HTTP directory-listing server; no custom server is required on that machine.

## Restarting and exclusions

Keep the destination's `.transfer-state` folder between runs. It contains a SQLite record of completed downloads, partial downloads, and a failure log. Every run checks the sender's metadata, including for previously completed files. An existing destination file is skipped when its modification time is equal to or newer than the source; a newer source is downloaded and replaces it. Downloaded files retain the source modification time. HTTP dates have one-second precision, so changes within the same second may not be detected. If an existing file cannot be compared because the server supplies no valid `Last-Modified` date, the receiver reports a failure and leaves it untouched. Partial downloads resume if the server supplies a usable modification date or ETag and supports range requests; otherwise they restart. Partial files from earlier versions of the script are not automatically imported.

The receiver excludes `node_modules`, `google-cloud-sdk`, common caches and virtual environments, and selected generated files; see the constants in `receive.py` to adjust the list. It includes `.git` and its contents. Close programs and avoid Git operations that change source files during the transfer. Install application dependencies and tools such as the Google Cloud SDK separately on the receiving machine.

## Limitations

- Modification times determine whether existing files are updated. Equal or newer local timestamps do not prove identical content; clock differences and changes within one second can cause skips. This tool does not verify source hashes.
- Source files should remain unchanged while being downloaded; metadata checks cannot guarantee a consistent snapshot.
- The receiver does not delete extra destination files. A fresh destination is preferable for a clean copy, particularly for Git repositories.
- Git worktrees and submodules can reference paths or repositories outside the shared folder; copying a `.git` file alone may not preserve their history. Git configuration may also contain machine-specific paths.
- The sender is unauthenticated and unencrypted HTTP. Anyone who can reach it can browse and download the shared files, which may include secrets and Git configuration. Use a trusted network, share only what you intend, and stop the server after use.
- Avoid running multiple receivers against the same destination at the same time.

## Desktop development build

The initial Python desktop interface can send and receive using the existing Python engine. See [DEVELOPMENT.md](DEVELOPMENT.md) for installation, automated tests, and a step-by-step manual test. This is not yet a packaged release; it requires Python and desktop dependencies and is intended for trusted networks. Node.js is needed for Playwright tests.

## Windows package

Run `npm run build` on 64-bit Windows to set up the build environment and package the desktop app. See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) for prerequisites, verification, GitHub Actions, and the current Windows Defender blocker. A successful package and a clean-machine test are required before distribution.
