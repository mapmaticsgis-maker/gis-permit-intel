# Setup Windows Task Scheduler jobs for automated TX RRC monitoring
# Run this as Administrator

$pythonExe = "C:\Users\mapma\AppData\Local\Programs\Python\Python314\python.exe"
$repoDir = "C:\GIS\permit_intel"

# Verify Python exists
if (-not (Test-Path $pythonExe)) {
    Write-Error "Python not found at $pythonExe"
    Write-Error "Update this script with your Python path: python -c 'import sys; print(sys.executable)'"
    exit 1
}

Write-Host "Setting up Windows Task Scheduler tasks..."
Write-Host "Python: $pythonExe"
Write-Host "Repo: $repoDir"
Write-Host ""

# Task 1: Auto-commit monitor (every 15 minutes)
Write-Host "Task 1: Inbox Auto-Commit (every 15 minutes)"
$taskName1 = "TX-RRC-Inbox-AutoCommit"
$scriptPath1 = Join-Path $repoDir "auto_commit_inbox.py"

$action1 = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument $scriptPath1 `
    -WorkingDirectory $repoDir

$trigger1 = New-ScheduledTaskTrigger `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Hours 23 -Minutes 59) `
    -Once -At (Get-Date).AddMinutes(1)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName1 `
    -Action $action1 `
    -Trigger $trigger1 `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host "  ✓ Task registered: $taskName1"
Write-Host "    Runs: Every 15 minutes"
Write-Host "    Script: auto_commit_inbox.py"
Write-Host ""

# Task 2: Daily download attempt (at 8:00 AM, for future use)
Write-Host "Task 2: Daily Download Attempt (8:00 AM, if RRC URL becomes available)"
$taskName2 = "TX-RRC-Daily-Download"
$scriptPath2 = Join-Path $repoDir "auto_download_txrrc.py"

$action2 = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument $scriptPath2 `
    -WorkingDirectory $repoDir

$trigger2 = New-ScheduledTaskTrigger -Daily -At "08:00 AM"

Register-ScheduledTask -TaskName $taskName2 `
    -Action $action2 `
    -Trigger $trigger2 `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host "  ✓ Task registered: $taskName2"
Write-Host "    Runs: Daily at 8:00 AM"
Write-Host "    Script: auto_download_txrrc.py"
Write-Host ""

# Summary
Write-Host "Setup complete!"
Write-Host ""
Write-Host "Your workflow is now:"
Write-Host "  1. Download daf420.dat.MM-DD-YYYY from RRC GoDrive folder (from any device)"
Write-Host "  2. Drop it in: C:\GIS\permit_intel\data\tx\inbox\"
Write-Host "  3. Auto-commit monitor detects it within 15 minutes"
Write-Host "  4. File is automatically committed & pushed to GitHub"
Write-Host "  5. GitHub Actions workflow runs at 10:15 AM"
Write-Host ""
Write-Host "Logs are in: C:\GIS\permit_intel\logs\inbox_commit.log"
Write-Host ""

# Show task status
Write-Host "Current task status:"
Get-ScheduledTask -TaskName $taskName1 | Select-Object TaskName, State
Get-ScheduledTask -TaskName $taskName2 | Select-Object TaskName, State
