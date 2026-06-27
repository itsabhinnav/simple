# Sakura LAN deployment — delegates to the interactive bootstrap wizard.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "bootstrap.ps1") @args
