# install_watchdog.ps1
# Installs two Windows Task Scheduler entries:
#   1. PromaiaAutostart  — starts the unified manager at login (headless via pythonw.exe)
#   2. PromaiaWatchdog   — checks health every 60 min, Telegrams if down
#
# Run once from an elevated PowerShell prompt:
#   cd "c:\Users\Zachary Turner\dev\promaia"
#   powershell -ExecutionPolicy Bypass -File scripts\install_watchdog.ps1

$ProjectRoot = "c:\Users\Zachary Turner\dev\promaia"

# Resolve pythonw.exe (windowless) and python.exe paths
$PythonW = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
$Python  = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonW) {
    Write-Host "[ERROR] pythonw.exe not found on PATH. Cannot register headless autostart." -ForegroundColor Red
    exit 1
}
if (-not $Python) {
    Write-Host "[ERROR] python.exe not found on PATH. Cannot register watchdog." -ForegroundColor Red
    exit 1
}

Write-Host "Using pythonw: $PythonW" -ForegroundColor Cyan
Write-Host "Using python:  $Python" -ForegroundColor Cyan
Write-Host "Project root:  $ProjectRoot" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. PROMAIA AUTOSTART — runs unified manager at login (headless, no console)
# ---------------------------------------------------------------------------

# pythonw.exe runs Python without a console window — perfect for Task Scheduler.
# We pass -m promaia.manager so it runs the unified manager (Web + Telegram + Scheduler + MuninnDB).
# PYTHONPATH=. is set via WorkingDirectory pointing to the project root.
$AutostartAction = New-ScheduledTaskAction `
    -Execute $PythonW `
    -Argument "-m promaia.manager" `
    -WorkingDirectory $ProjectRoot

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
    -Description "Start Promaia unified manager at login - Web, Telegram, Scheduler, MuninnDB" `
    | Out-Null

Write-Host "[OK] PromaiaAutostart task registered - runs pythonw.exe -m promaia.manager at login." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. PROMAIA WATCHDOG — hourly health check with Telegram alert + auto-restart
# ---------------------------------------------------------------------------

$WatchdogScript = Join-Path $ProjectRoot "scripts\watchdog.py"

$WatchdogAction = New-ScheduledTaskAction `
    -Execute  $Python `
    -Argument "`"$WatchdogScript`"" `
    -WorkingDirectory $ProjectRoot

# Repeat every 60 minutes, indefinitely
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
    -Description "Hourly Promaia health check - alerts if offline during waking hours, auto-restarts if down" `
    | Out-Null

Write-Host "[OK] PromaiaWatchdog task registered - runs hourly 07:00-23:00." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. BRAIN WATCHDOG — runs 'brain start' every 5 min (idempotent, ensures brain is always up)
# ---------------------------------------------------------------------------

$BrainAction = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "-m promaia brain start" `
    -WorkingDirectory $ProjectRoot

# Repeat every 5 minutes, indefinitely
$BrainTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At "00:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$BrainSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Unregister-ScheduledTask -TaskName "PromaiBrainWatchdog" -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName   "PromaiBrainWatchdog" `
    -Action     $BrainAction `
    -Trigger    $BrainTrigger `
    -Settings   $BrainSettings `
    -RunLevel   Highest `
    -Description "Every 5 min: ensures Brain MCP server is running (idempotent start)" `
    | Out-Null

Write-Host "[OK] PromaiBrainWatchdog task registered - runs 'brain start' every 5 min." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Verify
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "Registered tasks:" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "Promai*" | Format-Table TaskName, State, Description -AutoSize

Write-Host ""
Write-Host "Done. To test the watchdog now (without waiting 60 min):" -ForegroundColor Yellow
Write-Host "  python scripts\watchdog.py"
Write-Host ""
Write-Host "To start Brain immediately:" -ForegroundColor Yellow
Write-Host "  python -m promaia brain start"
Write-Host ""
Write-Host "To start all Promaia services via the scheduled task:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'PromaiaAutostart'"
