# Sakura LAN Deployment Script for Windows
# This script sets up a secure production environment on a local LAN.

Write-Host "--- Sakura LAN Deployment (Windows) ---" -ForegroundColor Cyan

# 1. Check for Dependencies
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Error: Docker Desktop is not installed or not in PATH."
    exit 1
}

# 2. Get Local LAN IP
$localIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'vEthernet|Loopback' } | Select-Object -First 1).IPAddress
Write-Host "[INFO] Detected Local LAN IP: $localIp" -ForegroundColor Gray

# 3. Setup Environment Variables
if (!(Test-Path .env)) {
    Write-Host "[INFO] Generating secure keys and .env file..." -ForegroundColor Gray
    
    $jwtSecret = [Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 255) }))
    
    # Try to generate Fernet key using python if available
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $encryptionKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    } else {
        $encryptionKey = [Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 255) }))
    }

    $envContent = @"
ENVIRONMENT=production
JWT_SECRET_KEY=$jwtSecret
ENCRYPTION_KEY=$encryptionKey
ALLOWED_ORIGINS=http://$localIp,http://localhost
FORCE_HTTPS=false
"@
    $envContent | Out-File -FilePath .env -Encoding utf8
    Write-Host "[INFO] .env file created with secure keys." -ForegroundColor Green
} else {
    Write-Host "[INFO] Using existing .env file." -ForegroundColor Gray
}

# 4. Configure Firewall
Write-Host "[INFO] Configuring Windows Firewall for port 80..." -ForegroundColor Gray
if (!(Get-NetFirewallRule -DisplayName "Sakura LAN Port 80" -ErrorAction SilentlyContinue)) {
    try {
        New-NetFirewallRule -DisplayName "Sakura LAN Port 80" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow -ErrorAction Stop
        Write-Host "[INFO] Firewall rule created." -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] Could not create firewall rule. You may need to run this script as Administrator." -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] Firewall rule already exists." -ForegroundColor Gray
}

# 5. Launch Application
Write-Host "[INFO] Building and starting Sakura stack..." -ForegroundColor Gray
docker-compose up -d --build

Write-Host ""
Write-Host "--- Deployment Complete ---" -ForegroundColor Cyan
Write-Host "Sakura is now accessible on your LAN at:"
Write-Host "URL: http://$localIp" -ForegroundColor White
Write-Host "---------------------------" -ForegroundColor Cyan
