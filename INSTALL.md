# Dahab AI - Installation Guide

## Step 1: Verify Python Installation

python --version

## Step 2: Create Virtual Environment (Recommended)

python -m venv venv

## Step 3: Activate Virtual Environment

### On Windows:
venv\Scripts\activate

### On macOS/Linux:
source venv/bin/activate

## Step 4: Install Dependencies

pip install -r requirements.txt

## Step 5: Run the Application

streamlit run app.py

## Alternative: Use PowerShell Script (Windows)

.\start.ps1

## First Time Usage

1. Open browser to http://localhost:8501
2. Navigate to "📰 News" page
3. Click "🔄 Collect Fresh News" to populate database
4. Go to "🎯 AI Market Outlook" to generate forecasts
5. Explore other pages

## Troubleshooting

### Import Errors
pip install --upgrade -r requirements.txt

### Translation Issues
pip install --upgrade deep-translator

### Market Data Issues  
pip install --upgrade yfinance

### Port Already in Use
streamlit run app.py --server.port 8502

## System Requirements

- Python 3.8+
- 2GB RAM minimum
- Internet connection for data collection
- Modern web browser (Chrome, Firefox, Edge)

## Database Location

The SQLite database will be created as `dahab_ai.db` in the project root directory.

## Notes

- First data collection may take 1-2 minutes
- Translation requires internet connection
- Market data updates every 60 seconds (cached)
- Forecast evaluation happens automatically based on time horizons
