<#
.SYNOPSIS
    One-time setup: register the two Scheduled Tasks that make this
    machine behave like the Linux box (systemd manufacture.service +
    manufacture-autopull.timer).

    Run this once, in an elevated PowerShell prompt (Run as Administrator),
    after copying the manufacture-run.ps1 and manufacture-autopull.ps1
    scripts to this same folder.

.NOTES
    Re-running this script is safe — it replaces any existing tasks of
    the same name rather than duplicating them.
#>

$ScriptDir = $PSScriptRoot
$RunScript      = Join-Path $ScriptDir 'manufacture-run.ps1'
$AutopullScript = Join-Path $ScriptDir 'manufacture-autopull.ps1'

# --- Task 1: start the server at logon (systemd's WantedBy=multi-user.target) ---
$startAction  = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""
$startTrigger = New-ScheduledTaskTrigger -AtLogOn
$startSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName 'ManufactureServer' `
    -Action $startAction -Trigger $startTrigger -Settings $startSettings `
    -Description 'Start the Manufacturing ERP dev server on logon (Windows equivalent of manufacture.service).' `
    -Force

# --- Task 2: poll for new commits every 2 minutes (systemd's OnUnitActiveSec=2min) ---
$pullAction  = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$AutopullScript`""
$pullTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 2) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$pullSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'ManufactureAutopull' `
    -Action $pullAction -Trigger $pullTrigger -Settings $pullSettings `
    -Description 'Poll origin/main every 2 minutes; pull + test-gate + restart on green (Windows equivalent of manufacture-autopull.timer).' `
    -Force

# Start the server right now too, instead of waiting for the next logon.
& $RunScript

Write-Host ""
Write-Host "Done. Two scheduled tasks registered:"
Write-Host "  ManufactureServer   — starts the dev server at logon"
Write-Host "  ManufactureAutopull — polls origin/main every 2 minutes"
Write-Host ""
Write-Host "Check status with:  Get-ScheduledTask ManufactureServer, ManufactureAutopull"
Write-Host "View logs at:       C:\tester\manufacture\manufacture-*.log"
