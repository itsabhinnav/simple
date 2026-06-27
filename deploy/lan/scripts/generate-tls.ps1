# Generate a self-signed TLS certificate for the LAN nginx reverse proxy.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$CertDir = Join-Path $Root "deploy\lan\nginx\certs"
$LanIp = if ($args[0]) { $args[0] } else {
    (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -First 1).IPAddress
}
if (-not $LanIp) { $LanIp = "localhost" }

New-Item -ItemType Directory -Force -Path $CertDir | Out-Null

$san = "DNS:localhost,DNS:sakura,DNS:sakura.local,IP:127.0.0.1,IP:$LanIp"
$docker = Get-Command docker -ErrorAction SilentlyContinue

if ($docker) {
    $mount = "${CertDir}:/certs"
    docker run --rm -v $mount alpine/openssl req -x509 -nodes -days 825 -newkey rsa:4096 `
        -keyout /certs/sakura.key -out /certs/sakura.crt `
        -subj "/CN=Sakura/O=Enterprise LAN/C=XX" `
        -addext "subjectAltName=$san" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker openssl cert generation failed" }
    Write-Host "(ok) TLS material in $CertDir via docker openssl (SAN includes $LanIp)" -ForegroundColor Green
    exit 0
}

if (Get-Command openssl -ErrorAction SilentlyContinue) {
    & openssl req -x509 -nodes -days 825 -newkey rsa:4096 `
        -keyout (Join-Path $CertDir "sakura.key") `
        -out (Join-Path $CertDir "sakura.crt") `
        -subj "/CN=Sakura/O=Enterprise LAN/C=XX" `
        -addext "subjectAltName=$san"
    Write-Host "(ok) TLS material in $CertDir (SAN includes $LanIp)" -ForegroundColor Green
    exit 0
}

throw "Need docker or openssl to generate TLS certs for nginx"
