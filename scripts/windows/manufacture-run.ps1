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
    #
    # Kill failures are reported, not swallowed: a Stop-Process that fails
    # on a permission boundary (scheduled task running as a different or
    # non-elevated user than the one that launched the server) used to
    # vanish under -ErrorAction SilentlyContinue, after which the script
    # cheerfully started a replacement that could never bind the port.
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match 'manage\.py runserver' } |
        ForEach-Object {
            # Capture the PID before the try: inside catch, $_ is rebound to
            # the ErrorRecord, so $_.ProcessId would be null there.
            $procId = $_.ProcessId
            Write-Host "Stopping PID $procId"
            try {
                Stop-Process -Id $procId -Force -ErrorAction Stop
            } catch {
                Write-Host "  FAILED to stop PID ${procId}: $($_.Exception.Message)"
                $script:stopFailures++
            }
        }
}

$stopFailures = 0

$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if ($listening -and -not $Restart) {
    Write-Host "Server already listening on port $Port; nothing to do. Pass -Restart to force."
    exit 0
}

if ($listening -or $Restart) {
    Write-Host "Stopping existing server..."
    Stop-AllServerProcesses

    # Wait for the socket to actually clear rather than assuming a fixed
    # sleep was long enough. Starting while the old process still holds
    # the port produces a replacement that dies instantly on a bind
    # error — invisible unless someone reads manufacture-server.log.err.
    $freed = $false
    foreach ($i in 1..10) {
        Start-Sleep -Milliseconds 500
        if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
            $freed = $true
            break
        }
    }

    if (-not $freed) {
        Write-Host "ERROR: port $Port is still held after stopping (kill failures: $stopFailures)."
        Write-Host "       Refusing to start a second server that cannot bind."
        if ($stopFailures -gt 0) {
            Write-Host "       Hint: the owning process belongs to another user — run this elevated,"
            Write-Host "       or set the scheduled task to run as the same account with highest privileges."
        }
        exit 1
    }
}

Write-Host "Starting server: $VenvPy manage.py runserver 0.0.0.0:$Port"
Start-Process -FilePath $VenvPy `
    -ArgumentList "manage.py", "runserver", "0.0.0.0:$Port" `
    -WorkingDirectory $RepoDir `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError "$LogFile.err" `
    -WindowStyle Hidden

# Confirm it came up instead of reporting success unconditionally. A
# runserver that dies on startup (bad .env, DB auth failure, port still
# held) otherwise leaves this script exiting 0 while nothing is serving.
$up = $false
foreach ($i in 1..20) {
    Start-Sleep -Milliseconds 500
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        $up = $true
        break
    }
}

if (-not $up) {
    Write-Host "ERROR: server did not come up on port $Port within 10s."
    Write-Host "       Last lines of ${LogFile}.err:"
    if (Test-Path "$LogFile.err") { Get-Content "$LogFile.err" -Tail 15 | ForEach-Object { "         $_" } }
    exit 1
}

Write-Host "Started and listening on port $Port. Logs: $LogFile"
