' Launches manufacture-autopull.ps1 with zero visible window (see
' run-server-hidden.vbs for why this indirection exists). waitOnReturn is
' True here specifically so Task Scheduler sees this task as "still
' running" for the full duration of the fetch/check/pytest cycle — if we
' returned immediately, its MultipleInstances=IgnoreNew setting would stop
' protecting against overlapping runs every 2 minutes.
Set objShell = CreateObject("WScript.Shell")
objShell.Run "powershell.exe -NoProfile -File ""C:\tester\manufacture\scripts\windows\manufacture-autopull.ps1""", 0, True
