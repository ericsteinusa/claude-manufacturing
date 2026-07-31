<#
.SYNOPSIS
    Start (or restart) the Manufacturing ERP dev server on Windows.

    Windows equivalent of manufacture.service on the Linux box. "Already
    running" is determined by whether something is listening on the
    configured port, not a tracked PID — a PID-file-based check was tried
    first and found unreliable in practice: Django's `runserver`
    autoreloader can replace its own process during normal operation
    (confirmed live), so the recorded PID periodically stopped matching
    the actual worker even though the server was still serving requests
    fine. That made the autopull's self-heal cycle (which calls this
    script with no -Restart) wrongly conclude the server had died and
    start a duplicate on top of the one still running, accumulating
    redundant `manage.py runserver` process chains every couple of
    cycles. Checking the port instead answers the question that actually
    matters ("is the app serving?") and sidesteps the reloader's process
    lifecycle entirely.

.PARAMETER Restart
    Stop any existing `manage.py runserver` process(es) before starting a
    new one. Without this switch, the script is a no-op if the port is
    already listening.
#>
param(
    [switch]$Restart
)

# --- Adjust these two paths if your clone/venv live somewhere else ---------
$RepoDir = 'C:\tester\manufacture'
$VenvPy  = 'C:\tester\virt\Scripts\python.exe'
$Port    = 8000
# -----------------------------------------------------------------------

$LogFile = Join-Path $RepoDir 'manufacture-server.log'

function Stop-AllServerProcesses {
    # Broad match rather than a single tracked PID — manage.py runserver's
    # autoreloader can leave more than one process alive in a watcher/child
    # chain, and a targeted kill of just one of them can leave the rest
    # (and the listening socket) behind.
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match 'manage\.py runserver' } |
        ForEach-Object {
            Write-Host "Stopping PID $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if ($listening -and -not $Restart) {
    Write-Host "Server already listening on port $Port; nothing to do. Pass -Restart to force."
    exit 0
}

if ($listening -or $Restart) {
    Write-Host "Stopping existing server..."
    Stop-AllServerProcesses
    Start-Sleep -Seconds 2
}

Write-Host "Starting server: $VenvPy manage.py runserver 0.0.0.0:$Port"
Start-Process -FilePath $VenvPy `
    -ArgumentList "manage.py", "runserver", "0.0.0.0:$Port" `
    -WorkingDirectory $RepoDir `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError "$LogFile.err" `
    -WindowStyle Hidden

Write-Host "Started. Logs: $LogFile"
