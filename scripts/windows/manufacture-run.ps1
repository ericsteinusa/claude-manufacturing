<#
.SYNOPSIS
    Start (or restart) the Manufacturing ERP dev server on Windows.

    Windows equivalent of manufacture.service on the Linux box. "Already
    running" is determined by whether something is listening on the
    configured port, not a tracked PID - a PID-file-based check was tried
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

function Get-ServerProcessIds {
    # Find the server by the socket it holds, NOT by matching CommandLine.
    #
    # Win32_Process.CommandLine reads back EMPTY for a process owned by a
    # different user unless the caller is elevated. A CommandLine-only
    # match therefore finds nothing in exactly the case that matters -- a
    # server left behind by some earlier session -- so no kill is ever
    # attempted, $stopFailures stays 0, and the caller reports
    # "still held (kill failures: 0)" with the run-elevated hint
    # suppressed. That reads as "the process vanished" when the truth is
    # "I was not allowed to see it". Observed live on the deployment box:
    # a stale server served fb8f2df for hours after the repo had pulled
    # 6d7e61b, and taskkill by PID was the only thing that could see it.
    #
    # OwningProcess from Get-NetTCPConnection carries no such restriction.
    $found = New-Object 'System.Collections.Generic.HashSet[int]'

    foreach ($conn in @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
        if ($conn.OwningProcess) { [void]$found.Add([int]$conn.OwningProcess) }
    }

    # runserver's autoreloader is a parent/child pair and only the child
    # binds the port. Killing just the child lets the parent respawn it,
    # so walk up one level and take a python.exe parent too. ParentProcessId
    # is readable cross-user even when CommandLine is not.
    foreach ($procId in @($found)) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
        if (-not $proc -or -not $proc.ParentProcessId) { continue }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.ParentProcessId)" -ErrorAction SilentlyContinue
        if ($parent -and $parent.Name -eq 'python.exe') { [void]$found.Add([int]$parent.ProcessId) }
    }

    # Keep the CommandLine match as a supplement, not the primary. When it
    # IS readable it catches a reloader parent that holds no socket of its
    # own, and it still finds a runserver that died mid-bind.
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'manage\.py runserver' } |
        ForEach-Object { [void]$found.Add([int]$_.ProcessId) }

    return $found
}

function Stop-AllServerProcesses {
    # Kill failures are reported, not swallowed: a Stop-Process that fails
    # on a permission boundary (scheduled task running as a different or
    # non-elevated user than the one that launched the server) used to
    # vanish under -ErrorAction SilentlyContinue, after which the script
    # cheerfully started a replacement that could never bind the port.
    $targets = Get-ServerProcessIds
    $script:stopAttempts = $targets.Count
    if ($targets.Count -eq 0) {
        Write-Host "No server process found holding port $Port."
        return
    }
    foreach ($procId in $targets) {
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
$stopAttempts = 0

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
    # error - invisible unless someone reads manufacture-server.log.err.
    #
    # Keep this file ASCII-only. It is UTF-8 without a BOM, and Windows
    # PowerShell 5.1 decodes such files as ANSI/cp1252 — so a UTF-8 em-dash
    # (E2 80 94) arrives as three characters ending in 0x94, which cp1252
    # maps to U+201D RIGHT DOUBLE QUOTATION MARK. PowerShell accepts smart
    # quotes as string delimiters, so an em-dash inside a double-quoted
    # string silently terminates it and the rest of the file parses as
    # garbage. Comments survive it; executable strings do not.
    $freed = $false
    foreach ($i in 1..10) {
        Start-Sleep -Milliseconds 500
        if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
            $freed = $true
            break
        }
    }

    if (-not $freed) {
        Write-Host "ERROR: port $Port is still held after stopping (found: $stopAttempts, kill failures: $stopFailures)."
        Write-Host "       Refusing to start a second server that cannot bind."
        # Report BOTH shapes of permission failure. Previously the hint was
        # gated on $stopFailures alone, so the "could not even see it" case
        # printed nothing actionable.
        if ($stopFailures -gt 0) {
            Write-Host "       Hint: the owning process belongs to another user - run this elevated,"
            Write-Host "       or set the scheduled task to run as the same account with highest privileges."
        } elseif ($stopAttempts -eq 0) {
            Write-Host "       Hint: something holds the port but no owning process could be identified."
            Write-Host "       Run elevated and check: Get-NetTCPConnection -LocalPort $Port -State Listen"
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
