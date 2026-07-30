# 📈 AI Market Intelligence Platform

A modular AI-powered market intelligence, paper trading, and quantitative research platform for the Indian stock market.

Built with **Python**, **FYERS API**, **PostgreSQL**, and a scalable architecture designed for data engineering, algorithmic trading, and future machine learning models.

> **Current Status:** Active Development (Paper Trading Mode)

---

# 🚀 Project Vision

The long-term goal is to build a complete AI-powered trading platform capable of:

- 📡 Real-time market monitoring
- 📊 Historical market data warehouse
- 🤖 AI-assisted trade decision support
- 📈 Strategy development & backtesting
- 💼 Portfolio analytics
- 📉 Risk management
- 🧠 Machine Learning & Deep Learning models
- ⚡ Automated paper trading
- 🔄 Future live trading support

---

# ✨ Current Features

## 📡 Market Data

- FYERS API v3 Integration
- Live WebSocket market streaming
- Real-time tick collection
- OHLCV candle support
- Unified market data interface
- Automatic reconnection

---

## 🗄 Database

- PostgreSQL backend
- Historical market storage
- Tick persistence
- Minute candle generation
- Optimized database schema
- SQLAlchemy ORM integration

---

## ⚙ Backend

- Flask REST API
- Provider abstraction layer
- Live market cache
- Health monitoring
- Modular architecture
- Configurable components

---

## 📈 Trading Engine

- Paper Trading Mode
- Strategy execution framework
- Risk profile configuration
- Trade signal generation
- Extensible broker architecture

---

## 🧠 AI Foundation

Currently under development:

- Feature engineering
- Dataset generation
- Technical indicators
- ML-ready data pipeline
- Strategy evaluation framework

---

# 🏗 System Architecture

```text
                    FYERS API
                        │
        ┌───────────────┴───────────────┐
        │                               │
 Historical API                  WebSocket Feed
        │                               │
        └───────────────┬───────────────┘
                        │
             Market Data Provider
                        │
          Provider Abstraction Layer
                        │
               Tick Collection Engine
                        │
                PostgreSQL Database
                        │
                Feature Engineering
                        │
                Strategy Engine
                        │
              Flask REST Backend
                        │
 Dashboard • Analytics • AI Models
```

---

# 📂 Project Structure

```text
AI-Trader/
│
├── audit/
├── backend/
├── broker/
├── config/
├── dashboard/
├── database/
├── datasets/
├── features/
├── models/
├── scripts/
├── strategies/
├── utils/
│
├── requirements.txt
├── README.md
└── TODO.md
```

---

# 🛠 Tech Stack

## Languages

- Python

## Backend

- Flask
- SQLAlchemy

## Database

- PostgreSQL

## Market Data

- FYERS API v3
- WebSocket Streaming

## Data Science

- Pandas
- NumPy

## Machine Learning (Planned)

- Scikit-Learn
- XGBoost
- LightGBM
- PyTorch
- Transformers

---

# 📅 Development Roadmap

## ✅ Version 1.0 — Market Data Platform

- FYERS Integration
- PostgreSQL Database
- Live Tick Collection
- Provider Abstraction
- Paper Trading Foundation

---

## 🚧 Version 1.5 — Historical Data Pipeline

Currently Working On

- Historical market downloader
- Option data collection
- Historical database population
- Feature generation
- Data validation

---

## 📊 Version 2.0 — Research Platform

Planned

- Interactive Dashboard
- Portfolio Tracking
- Strategy Framework
- Performance Analytics
- Paper Trading Dashboard

---

## 🤖 Version 3.0 — AI Trading Engine

Planned

- Technical Indicators
- Feature Store
- AI Signal Generation
- Probability Forecasting
- Explainable AI

---

## 🧠 Version 4.0 — Machine Learning Platform

Planned

- XGBoost
- LightGBM
- Random Forest
- LSTM
- Transformer Models
- Ensemble Learning

---

## 🚀 Version 5.0 — Intelligent Trading Assistant

Future Vision

Example Output

```text
Market Direction

Bullish

Probability Up: 78%

Probability Down: 22%

Confidence: High

Reasoning

• Strong buying pressure
• Volume confirmation
• Trend continuation
• Positive momentum
```

---

# 📥 Installation

Clone the repository

```bash
git clone https://github.com/Sanjay1318/AI-Trader-FYERS.git
cd AI-Trader-FYERS
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate

Windows

```bash
.venv\Scripts\activate
```

Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# ⚙ Configuration

Create a `.env` file

```env
FYERS_CLIENT_ID=
FYERS_APP_SECRET=
FYERS_ACCESS_TOKEN=

MARKET_DATA_PROVIDER=fyers

TRADE_MODE=paper

PAPER_TRADING_ONLY=true

ENABLE_LIVE_ORDER_EXECUTION=false
```

---

# ▶ Running the Project

Initialize Database

```bash
python init_database.py
```

Collect Market Data

```bash
python scripts/collect_fyers_ticks.py
```

Run Backend

```bash
python backend/app.py
```

---

# 🔒 Safety

This project operates in **Paper Trading Mode** by default.

Live order execution is intentionally disabled to provide a safe environment for:

- Strategy development
- AI experimentation
- Backtesting
- Feature engineering
- Paper trading

---

# 📌 Current Development Focus

The current milestone is focused on building a robust historical market data platform by implementing:

- Historical data downloader
- Option chain collection
- Historical database population
- Feature engineering
- Dataset generation
- Data quality validation

This foundation will support all future AI and quantitative research modules.

---

# 📜 Disclaimer

This software is intended for educational and research purposes only.

Trading in financial markets carries significant risk. The authors and contributors are not responsible for any financial losses arising from the use of this software.

---

# 📄 License

This project is licensed under the MIT License.

---

# 👨‍💻 Author

**Sanjay Kumar**

GitHub: https://github.com/Sanjay1318

Building AI-powered financial systems through software engineering, quantitative research, and machine learning.