# Start the VVF local render agent on this PC with Tailscale preview enabled.
# Run from the repo root:  powershell -File scripts/start-agent-pc.ps1

$ErrorActionPreference = "Stop"

# --- Tailscale preview settings (this PC) ---
$env:VVF_API_URL      = "https://api.purapuraninja.my.id"
$env:VVF_AGENT_NAME   = "render-pc-01"
$env:MPT_BASE_URL     = "http://127.0.0.1:8080"
$env:VVF_PREVIEW_HOST = "100.96.233.10"
$env:VVF_PREVIEW_PORT = "8090"
$env:VVF_PREVIEW_ROOT = "C:\Users\haris\Papi\MoneyPrinterTurbo\storage\tasks"

# Safety: never bind preview to a public/wildcard interface.
if ($env:VVF_PREVIEW_HOST -in @("0.0.0.0", "", "127.0.0.1", "localhost")) {
    Write-Error "VVF_PREVIEW_HOST must be this PC's Tailscale IP (100.96.233.10)."
}

# Warn if the preview root doesn't exist (preview would 404).
if (-not (Test-Path $env:VVF_PREVIEW_ROOT)) {
    Write-Warning "VVF_PREVIEW_ROOT not found: $($env:VVF_PREVIEW_ROOT)"
}

Write-Host "Preview server: http://$($env:VVF_PREVIEW_HOST):$($env:VVF_PREVIEW_PORT) (Tailscale-only)" -ForegroundColor Cyan
Write-Host "Preview root  : $($env:VVF_PREVIEW_ROOT)" -ForegroundColor Cyan
python -m vvf_local_agent.main
