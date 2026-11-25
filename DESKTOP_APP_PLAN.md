# RelayNest desktop roadmap

## Current implementation

RelayNest uses a Python transfer engine and a pywebview desktop window. The interface is HTML, CSS and JavaScript; on Windows it uses WebView2 and a direct Python bridge. A managed child process runs each transfer and sends output to the Activity page. The app supports one active operation per window.

The current Windows build command uses PyInstaller to create one executable containing the app and engine. Source-level tests and Windows desktop UI tests have exercised local sending and receiving. The packaged executable has not passed its tests: a managed Defender rule blocked it from launching on the development laptop. No successful two-machine or cross-platform packaged test is recorded.

## Delivery work

1. **Verify the Windows package.** Run the packaged engine and packaged desktop UI tests in an environment where the executable is permitted. Test a clean Windows laptop without Python or Node installed, confirm WebView2 availability, then transfer files between two machines. Investigate any packaging failures before publishing. Review signing and distribution with the appropriate certificate provider or device policy owner; signing is not a guarantee of acceptance.
2. **Improve transfer reliability.** Add tests for interruption and resume, changed files during transfer, invalid or missing metadata, path and symlink safety, mixed failures, duplicate requests and shutdown. Define how users can retry failed files and understand partial results. Preserve existing transfer state or provide a tested migration.
3. **Complete the desktop experience.** Consider measured progress, persistent settings and history, more focused error messages, and per-file retry. Only show capabilities supported by the engine. Continue to follow [DESIGN.md](DESIGN.md), including accessible keyboard interactions and both themes.
4. **Secure sharing.** Design pairing/authentication and encrypted transport before supporting untrusted networks. Define the intended trust boundary, prevent unsafe path handling, and decide whether optional content-hash verification is needed. Do not automatically delete destination files.
5. **Verify other platforms and release.** Confirm pywebview prerequisites and actual transfers on macOS and Linux, package for each supported platform, and test platform-specific paths, permissions, large files, interruption and resume. Decide on installer formats, signing/notarization, updates, rollback and supported OS versions before claiming release support.

## Test-driven development

Write a failing behavior or regression test first where practical, implement the change, and keep the tests green while refactoring. Use source engine tests for file logic, integration tests for actual HTTP and disk operations, and Playwright tests for user journeys. Browser tests with a mocked bridge do not verify desktop integration. Packaged tests must run the actual executable; successful source tests do not establish that a package works.

## Release acceptance criteria

A user can install or open the app on each claimed platform, select a source and destination, transfer files, see actual status and errors, interrupt and continue when supported, and rerun to skip equal or newer local files and update newer source files. Test results cover the packaged app and representative cross-machine combinations. Security limitations and prerequisites are clear, and no automatic deletion occurs.
