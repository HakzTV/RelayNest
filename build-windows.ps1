$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'This command builds the Windows package and must run on Windows.' }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) {
    Write-Host 'Creating the project Python environment...'
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv. Install Python and try again.' }
}
Write-Host 'Installing or checking build dependencies...'
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'build\spec') | Out-Null
& $python -m PyInstaller --noconfirm --onefile --windowed --name RelayNest --distpath dist --workpath build\app-work --specpath build\spec --collect-all webview --collect-all pythonnet --hidden-import RangeHTTPServer --add-data "$PSScriptRoot\desktop;desktop" desktop_host.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed. Check the output and any device security event.' }
Write-Host 'Build complete: dist\RelayNest.exe. Run npm run test:package and verify the desktop app before distribution.'
