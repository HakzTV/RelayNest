# RelayNest desktop development and testing

RelayNest uses Python and pywebview to open a desktop window. On Windows pywebview uses Microsoft WebView2; it does not launch the Electron executable that was blocked on this device. This is a development build; the Windows executable has not completed packaged release verification. Organization security policies can still block Python, its dependencies or WebView2. Never change or bypass those policies without your administrator.

## Windows setup and launch

From PowerShell in the project folder, use the same Python for installation and launch:

```powershell
python -m pip install -r requirements-desktop.txt
python desktop_host.py
```

`npm start` also launches the app, using the project `.venv` when present; Node is not needed to run the app itself. WebView2 Runtime is required on Windows. If the runtime or Python packages are missing or blocked, contact your administrator or install them according to your organization's approved process.

For an isolated Python environment instead:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe desktop_host.py
```

On macOS and Linux use `python3`, and install the pywebview operating-system prerequisites described in its documentation. Those platforms have not been verified for this build.

## Automated checks and TDD

Write a failing behavior test first, implement the smallest change, make the test pass, and refactor while tests remain green. Add a regression test for each reproducible bug.

```powershell
npm install
npm run test:engine
npm run test:ui
```

`npm run test:engine` and the Windows desktop UI test use the project `.venv` when present. Set `$env:RELAYNEST_PYTHON` to a Python executable path to select a different interpreter for the desktop UI test. The Windows Playwright test opens the actual source-based desktop window, connects to WebView2 with a debugging port enabled only during the test, and exercises real local sending and receiving with temporary files. Do not use this test configuration for normal operation or on an untrusted machine. The test is Windows-specific; macOS and Linux desktop automation still needs a separate approach. The browser-level tests use installed Microsoft Edge. The Playwright tests require Node and installed npm dependencies, but launching `desktop_host.py` directly does not.

Python tests exercise validation, engine events, and a local HTTP transfer including repeat skip and newer-source update. These do not replace a cross-machine transfer test or installer verification.

## Manual testing on one machine

1. Create two different empty test folders for source and destination. Put a small text file and subfolder in the source, without private data.
2. Start RelayNest, choose **Send**, select the source folder, and start sharing on port 8000. Confirm that the activity log says it is listening; choose another port if needed.
3. Launch a second RelayNest window with the same command. Choose **Receive**, enter `http://127.0.0.1:8000/`, select the destination, and start. Check the copied files and summary.
4. Run Receive again; the existing file should be skipped. Edit the source file, ensure its modification time is at least two seconds later, and run again. Check the new contents.
5. Stop sharing in the first window. Check that another receive fails and that the log explains it. Close both windows.

For two machines, use the sender's local IP and port instead of `127.0.0.1`. Use a trusted network: the transfer server is currently unauthenticated and unencrypted. Anyone who can reach it can browse the shared folder. The receiver compares timestamps with one-second precision, does not hash-verify contents, keeps newer local files, and does not delete extra files. Do not run two receivers against the same destination.

## Current limitations

No installers, auto-update, persisted history, encrypted sharing, pairing, per-file retry or measured aggregate progress yet. Stopping terminates the worker; a later run may resume partials when the source server and metadata permit. Transfers between operating systems, accessibility and packaged builds still need verification. Source files should not change during a transfer. The existing receiver's path and symlink handling require hardening for untrusted sources.

## Interface design checks

The visual design follows `DESIGN.md` and the CSS tokens in `desktop/styles.css`. The browser-level Playwright tests exercise navigation, themes, default settings, input validation, and a mocked folder picker in installed Microsoft Edge:

```powershell
node node_modules/@playwright/test/cli.js test tests/interface.spec.cjs
```

These browser tests use a mocked desktop bridge. Run the desktop WebView2 test and manual transfer checks separately to verify the native window and actual file operations. Light/dark theme and defaults currently last only for the open window; Activity shows the current session only.

## Windows packaging

`npm run build` produces a single executable containing the transfer engine rather than embedding a separate worker executable. `npm run test:package` launches the actual executable with an explicit self-test and checks a real local sender and receiver, repeat skip, and newer-source update. The source-based equivalent has passed, but Windows Defender blocked the packaged executable on this machine, so the packaged test remains unverified. See `WINDOWS_INSTALL.md`.

## Refresh the README screenshots

On Windows, with `.venv` and the npm test dependencies installed, run `node scripts/capture-readme.cjs`. The script launches the source-based desktop app, connects to its WebView2 instance using a temporary debugging port, and captures the Receive, Send and light-mode Settings views in `docs/screenshots`. Close other apps or enter no personal data in the capture window. The port is enabled only for the capture process; review the images before sharing them.
