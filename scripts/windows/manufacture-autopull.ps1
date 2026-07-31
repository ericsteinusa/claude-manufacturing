<#
.SYNOPSIS
    Poll origin/main for new commits and redeploy if found.

    Windows equivalent of manufacture-autopull.sh + the Linux
    manufacture-autopull.timer (which fires this every 2 minutes). Same
    safety gate as the Linux version: only restarts the running server
    if `manage.py check` and the full pytest suite both pass on the new
    commit. A failing gate leaves whatever was already running in place
    and just logs the failure — a broken push to main never takes down
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
    Write-Log "git fetch failed (exit $LASTEXITCODE) — leaving current deployment as-is."
    exit 1
}

$local  = (git rev-parse main).Trim()
$remote = (git rev-parse origin/main).Trim()

if ($local -eq $remote) {
    # Nothing new to pull, but mirror systemd's Restart=on-failure: if the
    # tracked server process has died (crash, manual kill, reboot without
    # a logon-trigger firing yet), bring it back up on the code that's
    # already known-good rather than waiting for the next push to notice.
    & (Join-Path $PSScriptRoot 'manufacture-run.ps1')
    exit 0
}

Write-Log "New commits detected ($local -> $remote), pulling"

git pull origin main --ff-only
if ($LASTEXITCODE -ne 0) {
    Write-Log "git pull --ff-only FAILED (local history has diverged?) — service NOT restarted, still running previous commit."
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
    & (Join-Path $PSScriptRoot 'manufacture-run.ps1') -Restart
} else {
    Write-Log "Checks FAILED after pull -- service NOT restarted, still running previous commit"
}
