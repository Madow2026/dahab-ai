# 🟨 Dahab AI - Economic News & Market Analysis Platform

A professional-grade artificial intelligence system specialized in economic and financial news analysis, market impact assessment, and probabilistic forecasting.

## 🌟 Features

- **📰 Multi-Source News Analysis**: Aggregates economic news from global RSS feeds with automatic Arabic translation
- **🤖 AI-Powered Classification**: Intelligent news categorization and impact analysis
- **🎯 Probabilistic Forecasting**: Risk-aware market predictions with confidence levels (never guarantees)
- **📊 Performance Tracking**: Continuous evaluation of forecast accuracy vs actual outcomes
- **💼 Paper Portfolio**: Virtual $1,000 trading simulation for educational purposes
- **🌍 Multi-Language**: Arabic translation support for all news content

## 🏗️ Architecture

```
gold ai/
├── app.py                          # Main Streamlit entry point
├── requirements.txt                # Python dependencies
├── .streamlit/
│   └── config.toml                # Streamlit configuration (dark theme)
├── core/
│   ├── database.py                # SQLite database manager
│   ├── ai_engine.py               # AI analysis and forecasting engine
│   └── data_collector.py          # News and market data collection
└── pages/
    ├── 1_📈_Markets_Dashboard.py  # Live market overview
    ├── 2_📰_News.py                # News feed with filtering
    ├── 3_🎯_AI_Market_Outlook.py  # Probabilistic forecasts
    ├── 4_📊_Accuracy_Performance.py # Forecast evaluation
    └── 5_💼_Paper_Portfolio.py     # Trading simulation
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Run the application**:
```bash
streamlit run app.py
```

3. **Access the platform**:
Open your browser to `http://localhost:8501`

## 📖 How to Use

### 1. Collect News
- Navigate to **📰 News** page
- Click **"🔄 Collect Fresh News"** button
- System will fetch and analyze economic news from multiple sources
- News is automatically translated to Arabic

### 2. Generate Forecasts
- Go to **🎯 AI Market Outlook** page
- Click **"Generate Forecasts from News"**
- System creates probabilistic forecasts for affected assets
- Each forecast includes:
  - Expected direction (Up/Down/Neutral)
  - Confidence level (0-100%)
  - Time horizon (15 min - 24 hours)
  - Risk level
  - Key reasoning

### 3. Track Accuracy
- Visit **📊 Accuracy & Performance** page
- Click **"Evaluate Pending Forecasts"** to check outcomes
- View accuracy metrics, calibration charts, and trends
- System honestly tracks all predictions

### 4. Simulate Trading
- Open **💼 Paper Portfolio** page
- Enter simulated trades based on forecasts
- Track performance with $1,000 virtual capital
- Educational only - no real money involved

### 5. Monitor Markets
- **📈 Markets Dashboard** shows live prices
- Market sentiment indicators
- High-impact news alerts
- Platform statistics

## 🎲 Core Principles

### ❌ NEVER
- Present forecasts as certain or guaranteed
- Provide direct investment advice
- Hide forecast failures
- Use sensational language

### ✅ ALWAYS
- Probabilistic predictions only
- Confidence-weighted forecasts
- Time-bound expectations
- Risk-aware recommendations
- Transparent performance tracking

## 📊 Data Sources

### News Sources (Free RSS Feeds)
- Reuters Business
- Investing.com Economic Calendar
- ForexLive
- MarketWatch

### Market Data
- Yahoo Finance API (free, no API key required)
- Assets tracked:
  - USD (Dollar Index)
  - Gold (GC=F)
  - Silver (SI=F)
  - Oil (CL=F)
  - Bitcoin (BTC-USD)

## 🗄️ Database Schema

SQLite database with four main tables:

1. **news**: Economic news items with translation
2. **forecasts**: Probabilistic predictions with evaluation
3. **portfolio_trades**: Virtual trading simulation
4. **portfolio_summary**: Performance metrics

## ⚙️ Configuration

### Theme Customization
Edit `.streamlit/config.toml` to modify colors and appearance.

### Data Collection Settings
Modify `core/data_collector.py` to:
- Add/remove news sources
- Change translation settings
- Adjust rate limiting

### Forecast Parameters
Adjust `core/ai_engine.py` to modify:
- Confidence level caps
- Time horizons
- Risk assessment logic

## 🔧 Technical Stack

- **Framework**: Streamlit (multi-page app)
- **Database**: SQLite
- **Charts**: Plotly
- **Data Processing**: Pandas, NumPy
- **Translation**: deep-translator (Google Translate)
- **Market Data**: yfinance
- **News Parsing**: feedparser

## ⚠️ Important Disclaimer

**This platform is for EDUCATIONAL and ANALYTICAL purposes only.**

- NOT financial advice
- NOT investment recommendations
- NOT a trading signal service
- All forecasts are probabilistic estimates
- Portfolio is virtual simulation only
- Past performance ≠ future results

Always consult licensed financial professionals before making investment decisions.

## 📈 Performance Philosophy

Success is measured by:
- **Honesty**: Transparent tracking of all forecasts
- **Consistency**: Systematic approach to analysis
- **Self-correction**: Learning from outcomes
- **Risk awareness**: Never overpromising

NOT by:
- Bold predictions
- Cherry-picked results
- Guaranteed returns

## 🛠️ Development

### Project Structure
- `core/`: Backend logic (database, AI engine, data collection)
- `pages/`: Streamlit pages (one file per page)
- `app.py`: Main entry point and landing page

### Adding Features
1. Core logic goes in `core/` modules
2. UI pages go in `pages/` directory
3. Follow naming convention: `N_emoji_PageName.py`

### Database Migrations
Initialize/reset database:
```python
from core.database import DatabaseManager
db = DatabaseManager()
db.init_database()
```

## 📝 License

Educational and research purposes. Not for commercial trading services.

## 🤝 Support

For issues or questions about the platform functionality, review the code documentation in each module.

---

**Version**: 1.0  
**Last Updated**: January 2026  
**Built with**: Python, Streamlit, AI/ML
