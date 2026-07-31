<#
.SYNOPSIS
    Start (or restart) the Manufacturing ERP dev server on Windows.

    Windows equivalent of manufacture.service on the Linux box: keeps
    `manage.py runserver` running in the background, tracked via a PID
    file so it can be found and stopped/restarted reliably (Windows has
    no systemd process-group tracking to lean on).

.PARAMETER Restart
    Stop the currently tracked server (if any) before starting a new one.
    Without this switch, the script is a no-op if a tracked process is
    already running.
#>
param(
    [switch]$Restart
)

# --- Adjust these two paths if your clone/venv live somewhere else ---------
$RepoDir = 'C:\tester\manufacture'
$VenvPy  = 'C:\tester\virt\Scripts\python.exe'
$Port    = 8000
# -----------------------------------------------------------------------

$PidFile = Join-Path $RepoDir 'manufacture-server.pid'
$LogFile = Join-Path $RepoDir 'manufacture-server.log'

function Get-TrackedProcess {
    if (-not (Test-Path $PidFile)) { return $null }
    $procId = Get-Content $PidFile -ErrorAction SilentlyContinue
    if (-not $procId) { return $null }
    return Get-Process -Id $procId -ErrorAction SilentlyContinue
}

$existing = Get-TrackedProcess

if ($existing -and -not $Restart) {
    Write-Host "Server already running (PID $($existing.Id)); nothing to do. Pass -Restart to force."
    exit 0
}

if ($existing) {
    Write-Host "Stopping existing server (PID $($existing.Id))..."
    Stop-Process -Id $existing.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host "Starting server: $VenvPy manage.py runserver 0.0.0.0:$Port"
$proc = Start-Process -FilePath $VenvPy `
    -ArgumentList "manage.py", "runserver", "0.0.0.0:$Port" `
    -WorkingDirectory $RepoDir `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError "$LogFile.err" `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Out-File -FilePath $PidFile -Encoding ascii
Write-Host "Started (PID $($proc.Id)). Logs: $LogFile"
