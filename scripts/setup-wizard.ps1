# Sakura interactive setup wizard (PowerShell).
# Dot-source from setup.ps1 / bootstrap.ps1:
#   . "$RootDir\scripts\setup-wizard.ps1"
#   $cfg = Invoke-SakuraSetupWizard

function Write-Step {
    param([int]$N, [int]$Total, [string]$Title)
    Write-Host ""
    Write-Host "[$N/$Total] $Title" -ForegroundColor Cyan
    Write-Host ("-" * 60) -ForegroundColor DarkGray
}

function Read-Choice {
    param(
        [string]$Prompt,
        [string[]]$Options,
        [int]$Default = 0
    )
    for ($i = 0; $i -lt $Options.Count; $i++) {
        $mark = if ($i -eq $Default) { " (default)" } else { "" }
        Write-Host "  $($i + 1)) $($Options[$i])$mark"
    }
    $raw = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($raw)) { return $Default }
    $n = 0
    if ([int]::TryParse($raw, [ref]$n) -and $n -ge 1 -and $n -le $Options.Count) {
        return $n - 1
    }
    Write-Host "  Invalid choice — using default." -ForegroundColor Yellow
    return $Default
}

function Read-YesNo {
    param([string]$Prompt, [bool]$Default = $true)
    $hint = if ($Default) { "Y/n" } else { "y/N" }
    $raw = Read-Host "$Prompt [$hint]"
    if ([string]::IsNullOrWhiteSpace($raw)) { return $Default }
    return $raw -match '^[yY]'
}

function Get-LanIpAddress {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike '169.254.*' -and
            $_.IPAddress -ne '127.0.0.1' -and
            $_.InterfaceAlias -notmatch 'vEthernet|Loopback' -and
            $_.PrefixOrigin -ne 'WellKnown'
        } |
        Sort-Object InterfaceMetric |
        Select-Object -First 1).IPAddress
    if (-not $ip) { return "localhost" }
    return $ip
}

function New-SakuraSecrets {
    param([string]$PythonExe = "python")
    $jwt = (& $PythonExe -c "import secrets;print(secrets.token_urlsafe(48))").Trim()
    $enc = (& $PythonExe -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())").Trim()
    return @{ Jwt = $jwt; Encryption = $enc }
}

function Invoke-SakuraSetupWizard {
    param(
        [string]$PythonExe = "python",
        [switch]$Force
    )

    $total = 7
    Write-Host ""
    Write-Host "=== Sakura Setup Wizard ===" -ForegroundColor Green
    Write-Host "Answer each step; press Enter to accept the default." -ForegroundColor Gray

    Write-Step 1 $total "Deployment mode"
    $modeIdx = Read-Choice "Select deployment" @(
        "Native — Python venv on this machine (dev / single-user)",
        "Docker LAN — nginx TLS + isolated container network (enterprise)"
    ) 1
    $DockerMode = ($modeIdx -eq 1)

    Write-Step 2 $total "Network exposure"
    if ($DockerMode) {
        $bindIdx = Read-Choice "Who should reach Sakura?" @(
            "LAN clients via nginx HTTPS (recommended)",
            "This machine only (localhost)"
        ) 0
        $LanExpose = ($bindIdx -eq 0)
    } else {
        $bindIdx = Read-Choice "Bind address" @(
            "Localhost only (127.0.0.1 — safest for dev)",
            "All interfaces (0.0.0.0 — reachable on LAN)"
        ) 0
        $HostBind = if ($bindIdx -eq 0) { "127.0.0.1" } else { "0.0.0.0" }
        $LanExpose = ($bindIdx -eq 1)
    }

    Write-Step 3 $total "Security posture"
    $restrictIdx = Read-Choice "Outbound network restrictor" @(
        "strict — loopback only (recommended for on-prem)",
        "allow_lan — RFC-1918 private ranges (requires explicit opt-in at boot)"
    ) 0
    $Restrictor = if ($restrictIdx -eq 0) { "strict" } else { "allow_lan" }

    $RequireAuth = Read-YesNo "Require JWT on all /api/* routes?" $true
    $ForceHttps = if ($DockerMode) { $true } else { (Read-YesNo "Enable FORCE_HTTPS (use with reverse proxy)?" $false) }

    Write-Step 4 $total "TLS / ports"
    $lanIp = Get-LanIpAddress
    if ($DockerMode) {
        $httpsPort = Read-Host "HTTPS port [443]"
        if ([string]::IsNullOrWhiteSpace($httpsPort)) { $httpsPort = "443" }
        $httpPort = Read-Host "HTTP redirect port [80]"
        if ([string]::IsNullOrWhiteSpace($httpPort)) { $httpPort = "80" }
        $port = $httpsPort
    } else {
        $port = Read-Host "Backend port [5000]"
        if ([string]::IsNullOrWhiteSpace($port)) { $port = "5000" }
        $httpsPort = "443"
        $httpPort = "80"
        if (-not $DockerMode) { $HostBind = if ($bindIdx -eq 0) { "127.0.0.1" } else { "0.0.0.0" } }
    }

    Write-Step 5 $total "Optional features"
    $Observability = Read-YesNo "Enable local API observability (admin dashboard, no cloud)?" $true
    $OllamaSidecar = $false
    if ($DockerMode) {
        $OllamaSidecar = Read-YesNo "Enable in-container Ollama sidecar? (requires model blobs)" $false
    } else {
        $OllamaSidecar = Read-YesNo "Try to start bundled/local Ollama for the assistant?" $false
    }
    $LiveIndexer = Read-YesNo "Enable RAG live indexer background thread?" $true

    $ComposeProfiles = @()
    if ($DockerMode) {
        Write-Step 6 $total "Docker IAM profiles (optional)"
        if (Read-YesNo "Enable Keycloak IAM profile (--profile iam)?" $false) {
            $ComposeProfiles += "iam"
        }
        if (Read-YesNo "Enable Authelia edge-auth profile (--profile edge-auth)?" $false) {
            $ComposeProfiles += "edge-auth"
        }
    } else {
        Write-Step 6 $total "Docker IAM profiles"
        Write-Host "  Skipped (native deployment)." -ForegroundColor DarkGray
    }

    Write-Step 7 $total "Confirm"
    $secrets = New-SakuraSecrets -PythonExe $PythonExe

    if ($DockerMode) {
        if ($LanExpose) {
            $origins = "https://${lanIp},https://localhost"
        } else {
            $origins = "https://localhost"
        }
        $hostBind = "0.0.0.0"
    } else {
        $origins = if ($LanExpose) {
            "http://${lanIp}:$port,http://localhost:$port"
        } else {
            "http://localhost:$port"
        }
        if (-not $HostBind) { $HostBind = "127.0.0.1" }
    }

    Write-Host "  Mode           : $(if ($DockerMode) { 'Docker LAN' } else { 'Native' })" -ForegroundColor White
    Write-Host "  LAN IP         : $lanIp"
    Write-Host "  Restrictor     : $Restrictor"
    Write-Host "  Require auth   : $RequireAuth"
    Write-Host "  Observability  : $Observability"
    if ($DockerMode) {
        Write-Host "  HTTPS port     : $httpsPort"
        Write-Host "  Compose profiles: $(if ($ComposeProfiles.Count) { $ComposeProfiles -join ', ' } else { '(none)' })"
    } else {
        Write-Host "  Host:Port      : ${HostBind}:$port"
    }

    if (-not (Read-YesNo "Write .env and continue?" $true)) {
        Write-Host "Setup cancelled." -ForegroundColor Yellow
        return $null
    }

    $envLines = @(
        "ENVIRONMENT=production"
        "FLASK_ENV=production"
        "HOST=$hostBind"
        "PORT=$port"
        "JWT_SECRET_KEY=$($secrets.Jwt)"
        "ENCRYPTION_KEY=$($secrets.Encryption)"
        "ALLOWED_ORIGINS=$origins"
        "FORCE_HTTPS=$($ForceHttps.ToString().ToLower())"
        "ENABLE_NETWORK_RESTRICTIONS=$Restrictor"
        "SAKURA_LLM_ALLOW_EXTERNAL=false"
        "SAKURA_LLM_ALLOW_REMOTE_OLLAMA=false"
        "SAKURA_REQUIRE_AUTH=$($RequireAuth.ToString().ToLower())"
        "SAKURA_ENABLE_OBSERVABILITY=$($Observability.ToString().ToLower())"
        "SAKURA_DISABLE_OLLAMA_SIDECAR=$((-not $OllamaSidecar).ToString().ToLower())"
        "SAKURA_DISABLE_LIVE_INDEXER=$((-not $LiveIndexer).ToString().ToLower())"
    )
    if ($DockerMode) {
        $envLines += "NGINX_HTTPS_PORT=$httpsPort"
        $envLines += "NGINX_HTTP_PORT=$httpPort"
        if ($ComposeProfiles -contains "iam") {
            $kcPass = Read-Host "Keycloak admin password (KEYCLOAK_ADMIN_PASSWORD)"
            if ([string]::IsNullOrWhiteSpace($kcPass)) {
                $kcPass = (& $PythonExe -c "import secrets;print(secrets.token_urlsafe(24))").Trim()
            }
            $envLines += "KEYCLOAK_ADMIN_PASSWORD=$kcPass"
        }
    }

    return [PSCustomObject]@{
        DockerMode       = $DockerMode
        LanIp            = $lanIp
        HostBind         = $hostBind
        Port             = $port
        HttpsPort        = $httpsPort
        HttpPort         = $httpPort
        ComposeProfiles  = $ComposeProfiles
        EnvLines         = $envLines
        RequireAuth      = $RequireAuth
        ForceHttps       = $ForceHttps
    }
}

function Write-SakuraEnvFile {
    param(
        [string]$Path,
        [string[]]$Lines,
        [switch]$Merge
    )
    if ($Merge -and (Test-Path $Path)) {
        Write-Host "[sakura] .env exists — wizard will overwrite security keys and selected settings." -ForegroundColor Yellow
    }
    Set-Content -Path $Path -Value ($Lines -join "`n") -Encoding UTF8
    Write-Host "[sakura] Wrote $Path" -ForegroundColor Green
}
