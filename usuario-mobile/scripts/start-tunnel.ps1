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

  $pids = @()
  foreach ($line in $lines) {
    $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
    if ($parts.Count -lt 5) {
      continue
    }

    $state = $parts[3]
    $processId = $parts[4]

    if ($state -in @("LISTENING", "ESTABLISHED") -and $processId -match "^\d+$") {
      $pids += [int]$processId
    }
  }

  $pids = $pids | Sort-Object -Unique
  foreach ($processId in $pids) {
    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
      Write-Host "Stopped process $processId on port $Port"
    } catch {
      Write-Warning "Could not stop process $processId on port ${Port}: $($_.Exception.Message)"
    }
  }
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

Write-Host "Clearing proxy environment variables for ngrok/Expo..."
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

if (-not $Env:NGROK_AUTHTOKEN) {
  $userToken = [Environment]::GetEnvironmentVariable("NGROK_AUTHTOKEN", "User")
  if ($userToken) {
    $Env:NGROK_AUTHTOKEN = $userToken
  }
}

if (-not $Env:NGROK_AUTHTOKEN) {
  throw "NGROK_AUTHTOKEN nao encontrado. Defina a variavel de ambiente antes de rodar o tunnel."
}

Write-Host "Starting modern ngrok tunnel and Expo on port 8082..."
node ./scripts/start-expo-with-ngrok.cjs
