# 📈 AI Market Intelligence Platform

An AI-powered market intelligence and paper trading platform for the Indian stock market built using **Python**, **FYERS API**, **PostgreSQL**, and a modular architecture designed for future machine learning and quantitative analysis.

The platform provides real-time market data ingestion, historical data collection, paper trading, and a scalable foundation for AI-driven market prediction.

> ⚠️ This project is currently configured for **Paper Trading Only**. Live order execution is intentionally disabled.

---

# Features

## Real-Time Market Data

- Live market data using FYERS API v3
- Real-time WebSocket streaming
- Historical OHLCV candle retrieval
- Provider-neutral market data abstraction
- Automatic reconnect and re-subscription
- Standardized quote, tick, and candle models

---

## Market Data Storage

- PostgreSQL backend
- Tick storage
- Minute candle generation
- Historical data persistence
- Optimized indexes for fast retrieval
- Standard PostgreSQL compatibility (no TimescaleDB required)

---

## Backend

- Flask REST API
- Provider health monitoring
- Live price cache
- Configurable market data providers
- REST endpoints for market state
- Modular architecture for future expansion

---

## Trading Engine

- Paper Trading Only
- Fail-safe protection against live order execution
- Broker abstraction layer
- Ready for future strategy execution modules

---

## Architecture

```
                 FYERS API
                     │
         ┌───────────┴───────────┐
         │                       │
   Historical API          WebSocket Feed
         │                       │
         └───────────┬───────────┘
                     │
          Market Data Provider
                     │
          Provider Neutral Models
                     │
              Tick Collector
                     │
             PostgreSQL Database
                     │
              Flask Backend API
                     │
      Dashboard / Analytics / AI
```

---

# Tech Stack

### Backend

- Python
- Flask
- SQLAlchemy
- PostgreSQL

### Market Data

- FYERS API v3
- WebSocket Streaming

### Database

- PostgreSQL

### Machine Learning (Planned)

- Pandas
- NumPy
- Scikit-Learn
- XGBoost
- LightGBM
- PyTorch
- Transformers

---

# Current Capabilities

- Live market quotes
- Live tick collection
- Historical candle download
- Tick persistence
- Minute candle generation
- Backend health monitoring
- Paper trading safeguards
- Modular provider architecture

---

# Roadmap

## Phase 1 ✅

- FYERS Integration
- Provider Abstraction
- PostgreSQL Support
- Real-time Tick Collection
- Historical Data Collection
- Paper Trading Foundation

---

## Phase 2 🚧

- Dashboard Integration
- Historical Data Visualization
- Portfolio Tracking
- Strategy Framework
- Paper Trading Dashboard

---

## Phase 3

Artificial Intelligence & Quantitative Analysis

- Technical Indicators
- Feature Engineering
- AI Signal Generation
- Probability Forecasting
- Strategy Evaluation

---

## Phase 4

Machine Learning Models

- XGBoost
- LightGBM
- Random Forest
- LSTM
- Transformer Models
- Ensemble Models

---

## Phase 5

AI Market Assistant

Example output:

```
Market Direction

Probability Up: 78%

Probability Down: 22%

Confidence: High

Reasons:
• Strong buying pressure
• Bullish momentum
• Volume confirmation
• RSI recovery
```

---

# Project Structure

```
AI-Trader/
│
├── backend/
├── broker/
├── config/
├── dashboard/
├── data/
├── database/
├── models/
├── scripts/
├── strategies/
├── utils/
│
├── requirements.txt
└── README.md
```

---

# Installation

Clone the repository

```bash
git clone https://github.com/Sanjay1318/AI-Trader-FYERS.git
cd AI-Trader-FYERS
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate it

Windows

```bash
.venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file

```env
FYERS_CLIENT_ID=YOUR_CLIENT_ID
FYERS_APP_SECRET=YOUR_SECRET
FYERS_ACCESS_TOKEN=YOUR_ACCESS_TOKEN

MARKET_DATA_PROVIDER=fyers

TRADE_MODE=paper

PAPER_TRADING_ONLY=true

ENABLE_LIVE_ORDER_EXECUTION=false
```

---

# Database

Initialize PostgreSQL

```bash
python init_database.py
```

---

# Start Tick Collection

```bash
python scripts/collect_fyers_ticks.py
```

---

# Run Backend

```bash
python backend/app.py
```

---

# Safety

This project intentionally disables live order execution.

```
Paper Trading Only
```

No live broker orders can be submitted unless the protection mechanisms are explicitly removed.

---

# Future Vision

The goal of this project is to evolve into a complete **AI-powered Market Intelligence Platform** capable of:

- Real-time market monitoring
- AI-powered trend prediction
- Strategy backtesting
- Portfolio analytics
- Explainable AI insights
- Automated signal generation
- Multi-model machine learning pipelines

---

# Disclaimer

This software is intended for educational and research purposes only.

Trading in financial markets involves substantial risk. The authors are not responsible for any financial losses resulting from the use of this software.

---

# License

This project is licensed under the MIT License.

```

## 👨‍💻 Author

**Sanjay Kumar**

GitHub: https://github.com/Sanjay1318

Building intelligent financial systems with AI, Machine Learning, and Quantitative Analytics.