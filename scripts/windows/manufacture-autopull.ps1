<#
.SYNOPSIS
    Poll origin/main for new commits and redeploy if found.

    Windows equivalent of manufacture-autopull.sh + the Linux
    manufacture-autopull.timer (which fires this every 2 minutes). Same
    safety gate as the Linux version: only restarts the running server
    if `manage.py check` and the full pytest suite both pass on the new
    commit. A failing gate leaves whatever was already running in place
    and just logs the failure - a broken push to main never takes down
    what's live.
#>

# --- Adjust these two paths if your clone/venv live somewhere else ---------
$RepoDir  = 'C:\tester\manufacture'
$VenvPy   = 'C:\tester\virt\Scripts\python.exe'
$VenvPip  = 'C:\tester\virt\Scripts\pip.exe'
# -----------------------------------------------------------------------

$LogFile = Join-Path $RepoDir 'manufacture-autopull.log'

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LogFile -Value $line
}

Set-Location $RepoDir

git fetch origin main --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Log "git fetch failed (exit $LASTEXITCODE) - leaving current deployment as-is."
    exit 1
}

$local  = (git rev-parse main).Trim()
$remote = (git rev-parse origin/main).Trim()

if ($local -eq $remote) {
    # Nothing new to pull, but mirror systemd's Restart=on-failure: if the
    # tracked server process has died (crash, manual kill, reboot without
    # a logon-trigger firing yet), bring it back up on the code that's
    # already known-good rather than waiting for the next push to notice.
    #
    # No -Restart here: when the port is already listening this is a no-op,
    # so it stays quiet on the common path and only logs when a genuine
    # revival was attempted and failed.
    # *>&1 for the same reason as the restart path below: Write-Host goes
    # to the Information stream, so 2>&1 would capture nothing.
    $heartbeatOut = & (Join-Path $PSScriptRoot 'manufacture-run.ps1') *>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Server was down and could NOT be restarted (exit $LASTEXITCODE)."
        foreach ($line in $heartbeatOut) { Write-Log "    run.ps1: $line" }
        exit 1
    }
    exit 0
}

Write-Log "New commits detected (was $local, now $remote), pulling"

git pull origin main --ff-only
if ($LASTEXITCODE -ne 0) {
    Write-Log "git pull --ff-only FAILED (local history has diverged?) - service NOT restarted, still running previous commit."
    exit 1
}

& $VenvPip install -q -r requirements.txt

& $VenvPy manage.py check
$checkOk = ($LASTEXITCODE -eq 0)

$testOk = $false
if ($checkOk) {
    & $VenvPy -m pytest tests/ -q
    $testOk = ($LASTEXITCODE -eq 0)
}

if ($checkOk -and $testOk) {
    Write-Log "Checks passed, restarting service"
    # Log the OUTCOME, not just the intent. This message used to be the
    # only record of a restart, written before the attempt and never
    # reconciled against its result — so a run script that silently
    # failed to stop the old process (permission boundary) produced a log
    # full of apparent successes while the box served stale code for
    # weeks. Capture the transcript too: the failure detail only exists
    # in the run script's output.
    #
    # Must be *>&1, not 2>&1. manufacture-run.ps1 reports exclusively via
    # Write-Host, which since PowerShell 5.0 writes to the Information
    # stream (6) rather than stdout or stderr -- so 2>&1 captures nothing
    # and the transcript below logs zero lines. Observed live: a genuine
    # "Restart FAILED (exit 1)" was recorded with no explanation beneath
    # it, which defeats the point of capturing it at all.
    $runOut = & (Join-Path $PSScriptRoot 'manufacture-run.ps1') -Restart *>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Restart OK -- now serving $remote"
    } else {
        Write-Log "Restart FAILED (exit $LASTEXITCODE) -- repo is at $remote but the server may still be serving older code."
        foreach ($line in $runOut) { Write-Log "    run.ps1: $line" }
    }
} else {
    Write-Log "Checks FAILED after pull -- service NOT restarted, still running previous commit"
}
