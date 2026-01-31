# Quick start script for Dahab AI platform
Write-Host "🟨 Starting Dahab AI Platform..." -ForegroundColor Yellow
Write-Host ""

# Check if virtual environment exists
if (Test-Path "venv") {
    Write-Host "✅ Virtual environment found" -ForegroundColor Green
    Write-Host "Activating environment..." -ForegroundColor Cyan
    .\venv\Scripts\Activate.ps1
} else {
    Write-Host "ℹ️ No virtual environment found. You can create one with:" -ForegroundColor Yellow
    Write-Host "   python -m venv venv" -ForegroundColor Gray
    Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Gray
    Write-Host ""
}

# Check if dependencies are installed
Write-Host "Checking dependencies..." -ForegroundColor Cyan
python -c "import streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ Dependencies not installed. Installing now..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host ""
Write-Host "🚀 Launching Streamlit application..." -ForegroundColor Green
Write-Host "📊 Access the platform at: http://localhost:8501" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# Run Streamlit
streamlit run app.py
