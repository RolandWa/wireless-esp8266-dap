# Build wireless-esp8266-dap firmware using Docker
# Usage: .\build_docker.ps1 [-Target esp32c3|esp32s3|esp32|esp8266]

param(
    [ValidateSet("esp32c3", "esp32s3", "esp32", "esp8266")]
    [string]$Target = "esp32c3"
)

$ErrorActionPreference = "Stop"
$ImageName = "wireless-dap"
$OutDir = Join-Path $PSScriptRoot "dist"

# --- Check Docker is installed ---
Write-Host "Checking Docker..." -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Download Docker Desktop from https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# --- Check Docker daemon is running ---
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker daemon is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host "Docker OK." -ForegroundColor Green

# --- Build image ---
Write-Host ""
Write-Host "Building firmware for target: $Target" -ForegroundColor Cyan
docker build --build-arg TARGET=$Target -t "${ImageName}:${Target}" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed." -ForegroundColor Red
    exit 1
}
Write-Host "Image built: ${ImageName}:${Target}" -ForegroundColor Green

# --- Extract binary ---
Write-Host ""
Write-Host "Extracting firmware binary to .\dist\" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

docker run --rm `
    -v "${OutDir}:/builder/dist" `
    "${ImageName}:${Target}"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to extract firmware." -ForegroundColor Red
    exit 1
}

$BinFile = Join-Path $OutDir "wireless_dap_full_${Target}.bin"
if (Test-Path $BinFile) {
    $size = [math]::Round((Get-Item $BinFile).Length / 1KB, 1)
    Write-Host ""
    Write-Host "Done! Firmware ready:" -ForegroundColor Green
    Write-Host "  $BinFile  ($size KB)" -ForegroundColor White
    Write-Host ""
    Write-Host "Flash with:" -ForegroundColor Cyan
    Write-Host "  python -m esptool -p COM12 -b 460800 --chip $Target write_flash 0x0 dist\wireless_dap_full_${Target}.bin" -ForegroundColor White
} else {
    Write-Host "WARNING: Binary not found at expected path: $BinFile" -ForegroundColor Yellow
}
