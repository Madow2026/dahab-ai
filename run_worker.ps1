<# 
.SYNOPSIS
    DAHAB AI - Persistent Worker Process (PowerShell)

.DESCRIPTION
    Starts the worker.py process in the background as a fully detached process.
    The worker keeps running even after closing PowerShell and Streamlit.
    It generates recommendations, evaluates them, and trades 24/7.

.USAGE
    .\run_worker.ps1
    .\run_worker.ps1 -Stop    # Stop running worker
    .\run_worker.ps1 -Status  # Check worker status
#>

param(
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Continue"
$WorkerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogFile = Join-Path $WorkerDir "worker_output.log"
$PidFile = Join-Path $WorkerDir "worker_pid.txt"

Set-Location $WorkerDir

function Get-WorkerPid {
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($pid) {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -match "python") {
                return [int]$pid
            }
        }
    }
    return $null
}

if ($Stop) {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  DAHAB AI - Stopping Worker" -ForegroundColor Yellow
    Write-Host "============================================================"
    
    $existingPid = Get-WorkerPid
    if ($existingPid) {
        Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Worker process (PID: $existingPid) stopped." -ForegroundColor Green
    } else {
        Write-Host "[INFO] No running worker found." -ForegroundColor Cyan
    }
    exit 0
}

if ($Status) {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  DAHAB AI - Worker Status" -ForegroundColor Cyan
    Write-Host "============================================================"
    
    $existingPid = Get-WorkerPid
    if ($existingPid) {
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        Write-Host "[RUNNING] Worker PID: $existingPid" -ForegroundColor Green
        Write-Host "  Started: $($proc.StartTime)" -ForegroundColor Gray
        Write-Host "  CPU Time: $($proc.TotalProcessorTime)" -ForegroundColor Gray
        Write-Host "  Memory: $([math]::Round($proc.WorkingSet64/1MB, 1)) MB" -ForegroundColor Gray
    } else {
        Write-Host "[STOPPED] Worker is not running." -ForegroundColor Red
    }
    
    if (Test-Path $LogFile) {
        Write-Host ""
        Write-Host "Last 5 log lines:" -ForegroundColor Gray
        Get-Content $LogFile -Tail 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }
    exit 0
}

# ---- Start Worker ----
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "  DAHAB AI - Starting Persistent Worker" -ForegroundColor Yellow
Write-Host "============================================================"
Write-Host ""

# Check if already running
$existingPid = Get-WorkerPid
if ($existingPid) {
    Write-Host "[INFO] Worker is already running (PID: $existingPid)" -ForegroundColor Cyan
    Write-Host "  Use -Stop to stop it, or -Status to check." -ForegroundColor Gray
    exit 0
}

# Find Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

Write-Host "Python: $($python.Source)" -ForegroundColor Gray
Write-Host "Worker: $WorkerDir\worker.py" -ForegroundColor Gray
Write-Host "Log:    $LogFile" -ForegroundColor Gray
Write-Host ""

# Start as detached background process
$proc = Start-Process -FilePath $python.Source `
    -ArgumentList "worker.py" `
    -WorkingDirectory $WorkerDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError "$WorkerDir\worker_error.log" `
    -PassThru

# Save PID
$proc.Id | Out-File $PidFile -Force

Write-Host "[OK] Worker started successfully! (PID: $($proc.Id))" -ForegroundColor Green
Write-Host ""
Write-Host "The worker will:" -ForegroundColor White
Write-Host "  - Generate recommendations continuously" -ForegroundColor Gray
Write-Host "  - Evaluate past recommendations automatically" -ForegroundColor Gray
Write-Host "  - Execute paper trades based on forecasts" -ForegroundColor Gray
Write-Host "  - Keep running even when Streamlit website is closed" -ForegroundColor Gray
Write-Host ""
Write-Host "Commands:" -ForegroundColor White
Write-Host "  .\run_worker.ps1 -Status   Check if worker is running" -ForegroundColor Gray
Write-Host "  .\run_worker.ps1 -Stop     Stop the worker" -ForegroundColor Gray
Write-Host "  Get-Content $LogFile -Tail 20   View recent logs" -ForegroundColor Gray
