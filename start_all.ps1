cd "D:\APP\gold ai"
.\.venv\Scripts\Activate.ps1

Start-Process powershell -ArgumentList '-NoExit','-Command','cd "D:\APP\gold ai"; .\.venv\Scripts\Activate.ps1; python worker.py'
Start-Process powershell -ArgumentList '-NoExit','-Command','cd "D:\APP\gold ai"; .\.venv\Scripts\Activate.ps1; streamlit run app.py'
