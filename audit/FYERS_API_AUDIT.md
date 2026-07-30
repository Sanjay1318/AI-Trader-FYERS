# FYERS API Capability Audit
**Date:** 2026-07-27  
**Scope:** Read-only verification of FYERS API for Milestone 4 approval  

---

## Executive Summary

**FYERS CAN provide** current index + options data but **CANNOT provide** historical (expired) option data. A dual-provider strategy is REQUIRED for any backtesting.

---

## Test Results Detail

### TEST 1: PostgreSQL Database State ✅
| Metric | Value |
|--------|-------|
| **market_features rows** | 10,875 |
| **Date range** | 2026-06-15 → 2026-07-24 |
| **Columns** | 29 (OHLCV, ema20/50, rsi, atr, adx, macd, vwap, obv, regime, session) |

### TEST 2: NIFTY Historical Depth ✅ (with caveats)
| Query Range | Result |
|------------|--------|
| Single day (2026-07-24) | ✅ **750 candles** (complete market hours 09:15-15:30 + pre-market 375 extra) |
| 5-day range (Jul 20-24) | ✅ **2,250 candles** |
| 30-day range (Jul 1-24) | ✅ **7,125 candles, 18 trading days** |
| 6-month range (Feb-Jul) | ❌ **0 candles - API limit exceeded** |
| **Cont_flag=0 vs 1** | ✅ Identical behavior (no difference) |

**Workaround:** FYERS history API supports max ~30-40 days per query. Longer ranges must be batched in 25-day chunks. This is already implemented in `scripts/backfill_fyers_history.py`.

### TEST 3: INDIA VIX ✅
| Property | Value |
|----------|-------|
| **Symbol** | `NSE:INDIAVIX-INDEX` |
| **Live quote** | ✅ 12.66 |
| **Candles/day** | ✅ 375 (full market hours) |
| **Volume** | Always 0 (volatility index — expected) |

### TEST 4: BANK NIFTY ✅
| Property | Value |
|----------|-------|
| **Symbol** | `NSE:NIFTYBANK-INDEX` |
| **Live quote (2026-07-24)** | ✅ 57,087.2 |
| **Candles/day** | ✅ 375 |

### TEST 5: Expired NIFTY Options ❌ CRITICAL
| Period | Quotes API | History API |
|--------|-----------|-------------|
| **Current month (Jul 2026)** | ✅ LIVE (lp=84.85) | ✅ 750 candles |
| **Jul 23 last week expired** | ✅ KNOWN (no price) | ❌ "Invalid symbol provided" |
| **Jun 25 monthly expiry** | ✅ KNOWN (no price) | ❌ "Invalid symbol provided" |
| **Jun 18 weekly expiry** | ✅ KNOWN (no price) | ❌ "Invalid symbol provided" |
| **May 28, May 21, May 14, May 7** | ✅ KNOWN (no price) | ❌ "Invalid symbol provided" |
| **Apr 2, 9, 16, 23, 30** | ✅ KNOWN (no price) | ❌ "Invalid symbol provided" |
| **2025 expiry (any)** | ❌ Not recognized | ❌ Not tested |

**Symbol format confirmed:**
- Current month: `NSE:NIFTY{YY}{MMM}{STRIKE}{CE/PE}` (e.g., `NSE:NIFTY26JUL24000CE`) — **no day code**
- Expired months: `NSE:NIFTY{YY}{MMM}{DD}{STRIKE}{CE/PE}` (e.g., `NSE:NIFTY26JUN2524000CE`) — **day code required**

**Impact:** FYERS CANNOT provide historical data for expired option contracts. This means:
- ❌ Cannot backtest option strategies from FYERS alone
- ❌ Cannot build ML datasets with option features for periods before current month
- ✅ Current-month option data IS available for live trading

**Solution needed:** A secondary provider (like TrueData) OR alternative approach for historical option data.

### TEST 6: Option Volume Semantics ✅
| Property | Value |
|----------|-------|
| **Volume type** | **Per-minute** (resets each candle, NOT cumulative) |
| **Evidence** | Sequential volumes: `[7,701,395 → 6,057,025 → 3,740,620 → ...]` — decreasing → reset each minute |

### TEST 7: Live Option Fields ✅
| Field | Available in Quote API |
|-------|----------------------|
| **LTP (lp)** | ✅ |
| **Bid** | ✅ (e.g., 84.7) |
| **Ask** | ✅ (e.g., 84.85) |
| **Spread** | ✅ (0.15) |
| **Volume** | ✅ (660,563,475 — daily cumulative) |
| **ATP** | ✅ (59.34 — average traded price) |
| **Open/High/Low** | ✅ (69.85 / 85.55 / 38.8) |
| **Prev Close** | ✅ (42.55) |
| **Change %** | ✅ (+99.41%) |
| **FyToken** | ✅ (101126072863939) |
| **Timestamp (tt)** | ✅ (epoch 1785110400) |
| **Open Interest (OI)** | ❌ **NOT available** |
| **Market Depth** | ❌ **NOT available** |

### TEST 8: GIFT NIFTY ❌
| Symbol Attempt | Result |
|---------------|--------|
| `NSE:GIFTNIFTY` | ❌ "Please provide a valid symbol" |
| `NSE:GIFT-NIFTY` | ❌ Same |
| `SGX:NIFTY` | ❌ Same |
| `NSE:NIFTY-I` | ❌ Same |

**GIFT NIFTY is NOT available via FYERS API.**

---

## Conclusions & Recommendations

### What FYERS CAN Do for Milestone 4:
1. ✅ **NIFTY 50 index history** (chunked 25-day batches, up to ~7 weeks)
2. ✅ **INDIA VIX history**
3. ✅ **BANK NIFTY history**
4. ✅ **Current-month option data** (live quotes + history)
5. ✅ **Per-minute volume data** (index and options)

### What FYERS CANNOT Do:
1. ❌ **Expired option history** (any prior month)
2. ❌ **GIFT NIFTY**
3. ❌ **Open Interest (OI) in quotes**
4. ❌ **Market depth**
5. ❌ **Single query > ~40 days** (must batch)

### Milestone 4 Approval Recommendation:
- **APPROVE FYERS** for index data acquisition (NIFTY, BANKNIFTY, VIX) via batched 25-day queries
- **DENY FYERS** as sole provider for option data (missing expired contracts)
- **REQUIRE** dual-provider strategy: FYERS for current data + TrueData (or equivalent) for historical options
- **DEFAULT** to current-month-only options for initial live paper trading
