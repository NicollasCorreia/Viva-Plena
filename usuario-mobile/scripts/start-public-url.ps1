param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$PublicUrl
)

$ErrorActionPreference = "Stop"

function Stop-ProcessOnPort {
  param(
    [Parameter(Mandatory = $true)]
    [int]$Port
  )

  $lines = netstat -ano | Select-String ":$Port"
  if (-not $lines) {
    return
  }

  $processIds = @()
  foreach ($line in $lines) {
    $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
    if ($parts.Count -lt 5) {
      continue
    }

    $state = $parts[3]
    $processId = $parts[4]

    if ($state -in @("LISTENING", "ESTABLISHED") -and $processId -match "^\d+$") {
      $processIds += [int]$processId
    }
  }

  $processIds = $processIds | Sort-Object -Unique
  foreach ($processId in $processIds) {
    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
      Write-Host "Stopped process $processId on port $Port"
    } catch {
      Write-Warning "Could not stop process $processId on port ${Port}: $($_.Exception.Message)"
    }
  }
}

if (-not ($PublicUrl -match '^https?://')) {
  throw "Informe um URL publico valido, por exemplo: npm run start:public-url -- https://abc.ngrok-free.app"
}

Write-Host "Cleaning stale Expo/ngrok processes..."

Get-Process ngrok -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    Stop-Process -Id $_.Id -Force -ErrorAction Stop
    Write-Host "Stopped ngrok process $($_.Id)"
  } catch {
    Write-Warning "Could not stop ngrok process $($_.Id): $($_.Exception.Message)"
  }
}

Stop-ProcessOnPort -Port 8081
Stop-ProcessOnPort -Port 8082

Write-Host "Clearing proxy environment variables for Expo..."
$proxyVars = @(
  "HTTP_PROXY",
  "HTTPS_PROXY",
  "ALL_PROXY",
  "NO_PROXY",
  "http_proxy",
  "https_proxy",
  "all_proxy",
  "no_proxy"
)

foreach ($proxyVar in $proxyVars) {
  if (Test-Path "Env:$proxyVar") {
    Remove-Item "Env:$proxyVar" -ErrorAction SilentlyContinue
    Write-Host "Removed $proxyVar"
  }
}

$env:EXPO_PACKAGER_PROXY_URL = $PublicUrl.TrimEnd("/")

Write-Host "Using public URL: $env:EXPO_PACKAGER_PROXY_URL"
Write-Host "Starting Expo on port 8082 with host=lan..."
npx expo start --host lan --clear --port 8082
