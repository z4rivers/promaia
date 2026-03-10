# install_watchdog.ps1
# Installs two Windows Task Scheduler entries:
#   1. PromaiaAutostart  — starts Promaia server at login
#   2. PromaiaWatchdog   — checks health every 60 min, Telegrams if down
#
# Run once from an elevated PowerShell prompt:
#   cd c:\Users\Zachary Turner\dev\promaia
#   powershell -ExecutionPolicy Bypass -File scripts\install_watchdog.ps1

$ProjectRoot = "c:\Users\Zachary Turner\dev\promaia"
$Python      = "python"   # assumes python is on PATH; change to full path if needed

# ---------------------------------------------------------------------------
# 1. PROMAIA AUTOSTART — runs uvicorn at login
# ---------------------------------------------------------------------------

$StartScript = Join-Path $ProjectRoot "scripts\start_promaia.bat"

# Write the launcher batch file
@"
@echo off
cd /d "$ProjectRoot"
$Python -m uvicorn promaia.web.main:app --host 0.0.0.0 --port 8000
"@ | Set-Content -Path $StartScript -Encoding ASCII

$AutostartAction  = New-ScheduledTaskAction -Execute $StartScript
$AutostartTrigger = New-ScheduledTaskTrigger -AtLogOn
$AutostartSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

# Remove existing task if present
Unregister-ScheduledTask -TaskName "PromaiaAutostart" -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName   "PromaiaAutostart" `
    -Action     $AutostartAction `
    -Trigger    $AutostartTrigger `
    -Settings   $AutostartSettings `
    -RunLevel   Highest `
    -Description "Start Promaia web server at login" `
    | Out-Null

Write-Host "[OK] PromaiaAutostart task registered - will start Promaia at next login." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. PROMAIA WATCHDOG — hourly health check with Telegram alert
# ---------------------------------------------------------------------------

$WatchdogScript = Join-Path $ProjectRoot "scripts\watchdog.py"

$WatchdogAction = New-ScheduledTaskAction `
    -Execute  $Python `
    -Argument "`"$WatchdogScript`"" `
    -WorkingDirectory $ProjectRoot

# Repeat every 60 minutes, indefinitely (PowerShell 5.1 compatible syntax)
$WatchdogTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At "07:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 60) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$WatchdogSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -StartWhenAvailable

Unregister-ScheduledTask -TaskName "PromaiaWatchdog" -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName   "PromaiaWatchdog" `
    -Action     $WatchdogAction `
    -Trigger    $WatchdogTrigger `
    -Settings   $WatchdogSettings `
    -RunLevel   Highest `
    -Description "Hourly Promaia health check - Telegrams if offline during waking hours" `
    | Out-Null

Write-Host "[OK] PromaiaWatchdog task registered - runs hourly 07:00-23:00." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. Verify
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "Registered tasks:" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "Promaia*" | Format-Table TaskName, State, Description -AutoSize

Write-Host ""
Write-Host "Done. To test the watchdog now (without waiting 60 min):" -ForegroundColor Yellow
Write-Host "  python scripts\watchdog.py"
