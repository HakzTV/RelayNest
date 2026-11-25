param(
    [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
    [Parameter(Mandatory=$true)][string]$TimestampUrl,
    [string]$SignToolPath = 'signtool.exe'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($CertificateThumbprint -notmatch '^[0-9A-Fa-f]{40}$') { throw 'CertificateThumbprint must be 40 hexadecimal characters.' }
$timestamp = $null
if (-not [Uri]::TryCreate($TimestampUrl, [UriKind]::Absolute, [ref]$timestamp) -or $timestamp.Scheme -ne 'https') { throw 'TimestampUrl must be an HTTPS URL for your signing provider.' }
$app = Join-Path $PSScriptRoot 'dist\RelayNest.exe'
if (!(Test-Path -LiteralPath $app -PathType Leaf)) { throw 'Build dist\RelayNest.exe before signing.' }
$tool = Get-Command $SignToolPath -ErrorAction Stop
Write-Host 'Signing the app with the specified certificate and timestamp provider...'
& $tool.Source sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $app
if ($LASTEXITCODE -ne 0) { throw 'Signing or timestamping failed; do not distribute this build.' }
& $tool.Source verify /pa /v $app
if ($LASTEXITCODE -ne 0) { throw 'Signature verification failed; do not distribute this build.' }
Write-Host 'Signature verified. A trusted signature does not guarantee acceptance by Windows Defender or managed-device policies.'
