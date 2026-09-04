<#
.SYNOPSIS
    One-time setup: register the two Scheduled Tasks that make this
    machine behave like the Linux box (systemd manufacture.service +
    manufacture-autopull.timer).

    Run this once, in an elevated PowerShell prompt (Run as Administrator),
    after copying the manufacture-run.ps1 and manufacture-autopull.ps1
    scripts to this same folder.

.NOTES
    Re-running this script is safe - it replaces any existing tasks of
    the same name rather than duplicating them.
#>

$ScriptDir = $PSScriptRoot
$RunScript          = Join-Path $ScriptDir 'manufacture-run.ps1'
$RunLauncher        = Join-Path $ScriptDir 'run-server-hidden.vbs'
$AutopullLauncher   = Join-Path $ScriptDir 'autopull-hidden.vbs'

# Both tasks run wscript.exe against a tiny VBScript launcher (see the two
# *-hidden.vbs files) rather than calling powershell.exe directly. A task's
# own "Hidden" setting does not reliably suppress the console flash for a
# task running in an interactive logon session — WScript.Shell.Run with
# window style 0 does. -ExecutionPolicy Bypass is intentionally omitted:
# this machine's LocalMachine execution policy is already Unrestricted, so
# it's not needed (and it's the kind of flag worth not reaching for out of
# habit).

# Both tasks need an explicit -Principal. Without one, Register-ScheduledTask
# defaults to RunLevel 'Limited' (non-elevated), and the autopull task then
# cannot terminate a server process running at a higher integrity level — for
# instance one started from an elevated shell. Worse, a Limited process can't
# even read CommandLine from another user's process via Win32_Process, so
# manufacture-run.ps1's `Where-Object { $_.CommandLine -match 'runserver' }`
# filter silently matches nothing and no kill is even attempted. That is how
# the box came to serve weeks-old code behind a log full of apparent
# successes; see the "pulled is not deployed" note in CLAUDE.md.
#
# LogonType Interactive preserves the previous behaviour (tasks run in the
# registering user's interactive session, which the WScript.Shell launcher
# relies on for a hidden window); only the elevation changes.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Highest

# --- Task 1: start the server at logon (systemd's WantedBy=multi-user.target) ---
$startAction  = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$RunLauncher`""
$startTrigger = New-ScheduledTaskTrigger -AtLogOn
$startSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -Hidden

Register-ScheduledTask -TaskName 'ManufactureServer' `
    -Action $startAction -Trigger $startTrigger -Settings $startSettings `
    -Principal $principal `
    -Description 'Start the Manufacturing ERP dev server on logon (Windows equivalent of manufacture.service).' `
    -Force

# --- Task 2: poll for new commits every 2 minutes (systemd's OnUnitActiveSec=2min) ---
$pullAction  = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$AutopullLauncher`""
$pullTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 2) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$pullSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -Hidden

Register-ScheduledTask -TaskName 'ManufactureAutopull' `
    -Action $pullAction -Trigger $pullTrigger -Settings $pullSettings `
    -Principal $principal `
    -Description 'Poll origin/main every 2 minutes; pull + test-gate + restart on green (Windows equivalent of manufacture-autopull.timer).' `
    -Force

# Start the server right now too, instead of waiting for the next logon.
& $RunScript

Write-Host ""
Write-Host "Done. Two scheduled tasks registered:"
Write-Host "  ManufactureServer   - starts the dev server at logon"
Write-Host "  ManufactureAutopull - polls origin/main every 2 minutes"
Write-Host ""
Write-Host "Check status with:  Get-ScheduledTask ManufactureServer, ManufactureAutopull"
Write-Host "View logs at:       C:\tester\manufacture\manufacture-*.log"
