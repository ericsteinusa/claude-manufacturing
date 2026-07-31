' Launches manufacture-run.ps1 with zero visible window.
' Task Scheduler's own "Hidden" task setting does not reliably suppress
' the console flash for a task running in an interactive logon session —
' WScript.Shell.Run with window style 0 is the reliable way to do that.
Set objShell = CreateObject("WScript.Shell")
objShell.Run "powershell.exe -NoProfile -File ""C:\tester\manufacture\scripts\windows\manufacture-run.ps1""", 0, True
