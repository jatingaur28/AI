# AI TRADING + PORTFOLIO SYSTEM[cite: 8]

> Complete Tech Stack, Methodologies & Concepts[cite: 8]
> **Backend Engine + Streamlit Dashboard Frontend**[cite: 8]

---

## 1. TECH STACK OVERVIEW[cite: 8]

### 1.1 Backend Core Stack[cite: 8]
* **Python 3.x**: Primary language[cite: 8].
* **asyncio**: Concurrent orchestration[cite: 8].
* **numpy**: Numerical computation[cite: 8].
* **pandas**: OHLCV data manipulation[cite: 8].
* **TA-Lib (talib)**: Technical indicators[cite: 8].
* **yfinance**: Live NSE market data[cite: 8].
* **hmmlearn**: Hidden Markov Models[cite: 8].
* **hurst**: Hurst Exponent calculation[cite: 8].
* **colorama**: CLI colour output[cite: 8].
* **dataclasses**: Config & Trade records[cite: 8].
* **csv / json / Path**: File I/O & logging[cite: 8].
* **random / math**: Simulation & rounding[cite: 8].

### 1.2 Frontend (Dashboard) Stack[cite: 8]
* **Streamlit**: Reactive web framework[cite: 8].
* **Plotly**: Interactive charts[cite: 8].
* **Plotly Express**: High-level chart API[cite: 8].
* **pandas**: Data wrangling[cite: 8].
* **numpy**: Simulation & calcs[cite: 8].
* **yfinance**: Live OHLCV data[cite: 8].
* **CSS3 / HTML5**: Custom terminal UI[cite: 8].
* **Google Fonts**: IBM Plex Mono, Bebas Neue[cite: 8].
* **json / Path**: Reads backend state files[cite: 8].

### 1.3 Data Flow Between Backend & Frontend[cite: 8]
* **ai_portfolio_report.json**: Master AI state containing consolidated metrics, per-portfolio stats, grades, recommendations, alerts, and Darwin DNA[cite: 8].
* **logs/YYYY-MM-DD_*.csv**: Per-portfolio trade history with fields for timestamp, symbol, side, qty, price, pnl, votes, and notes[cite: 8].
* **Session State (`st.session_state`)**: Frontend-only ephemeral state handling tick counter, engine on/off toggle, price history cache, and selected symbol[cite: 8].

---

## 2. BACKEND — ARCHITECTURE & DESIGN PATTERNS[cite: 8]

| Pattern / Concept | Application | Category |
| :--- | :--- | :--- |
| **Single Source of Truth** | `MasterConfig` dataclass holds every parameter (capital, risk, watchlists, intervals). No magic numbers anywhere else.[cite: 8] | Centralised configuration[cite: 8] |
| **Master Orchestrator** | `async orchestrate()` launches all portfolio loops as concurrent coroutines and coordinates timing with asyncio.[cite: 8] | Async actor model[cite: 8] |
| **Tick-Based Event Loop** | Everything runs on a 60-second tick, triggering trading, short-term checks, long-term checks, and AI reports on their own intervals.[cite: 8] | Game-loop / event-driven[cite: 8] |
| **Strategy Pattern** | Each portfolio (Long, Short, Trading) is a separate class with its own `evaluate()`/`run_tick()` method, swappable without touching others.[cite: 8] | OOP Strategy pattern[cite: 8] |
| **Circuit Breaker** | `RiskGuard` halts a portfolio completely if daily loss limit is exceeded and enters timed cooldown after N consecutive losses.[cite: 8] | Fault-tolerance pattern[cite: 8] |
| **Observer / Logger** | `TradeLogger` subscribes to every trade and appends structured CSV rows without coupling to the broker or portfolio logic.[cite: 8] | Observer / decorator[cite: 8] |
| **Repository Pattern** | `PaperBroker` encapsulates all order state (positions, cash, history) behind buy/sell/force_close_all methods.[cite: 8] | Encapsulation[cite: 8] |
| **Decorator / Cache** | `LiveDataFeed` throttles and caches yfinance calls per symbol+interval key, returning cached data within the throttle window.[cite: 8] | Caching / throttling[cite: 8] |

---

## 3. QUANTITATIVE FINANCE — ALGORITHMS & SIGNALS[cite: 8]

### 3.1 Statistical Signal Processing[cite: 8]
* **Kalman Filter**: 1-dimensional filter for real-time noise-filtered price tracking[cite: 8]. Uses process noise (Q=1e-5) and measurement noise (R=0.01) tuned for financial time series, returning a smoothed price estimate on every tick[cite: 8].
* **Hidden Markov Model (HMM)**: 2-state Gaussian HMM trained on rolling return series to detect market regimes (State 0 = bear/low-volatility, State 1 = bull/trending)[cite: 8]. Re-trained incrementally from live data[cite: 8].
* **Hurst Exponent**: Computed with the R/S method[cite: 8]. H > 0.6 = TRENDING, H < 0.4 = MEAN_REVERTING, 0.4-0.6 = RANDOM[cite: 8]. Requires minimum 100 price points[cite: 8].
* **Monte Carlo GBM**: Generates 1000 future price paths using Geometric Brownian Motion[cite: 8]. Trade is gated if Probability of profit < 55%[cite: 8].
* **Simulated GBM Fallback**: Generates synthetic OHLCV using GBM if yfinance fails so portfolios keep running in simulation mode[cite: 8].

### 3.2 Technical Analysis Indicators (TA-Lib)[cite: 8]
* **RSI**: 14-period[cite: 8]. Returns overbought (>70) or oversold (<30) signals[cite: 8]. Weighted ×2 in the vote consensus[cite: 8].
* **Bollinger Bands**: 20-period SMA ± 2σ[cite: 8]. Signals: price below lower = +1, above upper = -1[cite: 8].
* **MACD**: Fast 12 / Slow 26 / Signal 9[cite: 8]. Signal on histogram crossover[cite: 8].
* **OBV**: Detects price-volume divergence[cite: 8].
* **Stochastic Oscillator**: %K(14)/%D(3)[cite: 8]. Cross in oversold zone = +1, overbought = -1[cite: 8].
* **EMA Cross (9/21)**: Golden cross = +1, death cross = -1[cite: 8].
* **EMA 200**: Price above EMA200 = bullish macro filter (+1)[cite: 8].
* **ATR Trailing Stop**: ATR(14) × `stop_loss_mult`[cite: 8]. Sets dynamic stop-loss below entry based on volatility[cite: 8].
* **Volume Trend Ratio**: Recent 20-bar avg volume / prior 20-bar avg[cite: 8]. Ratio > 1.0 indicates rising participation[cite: 8].
* **52-Week Proximity**: Normalised position between 52-week high and low[cite: 8].

### 3.3 Candlestick Pattern Recognition — SniperEngine[cite: 8]
12 TA-Lib candlestick pattern functions are checked on every bar[cite: 8]. A bullish match contributes +2 votes, bearish -2[cite: 8]:
* **Bullish Reversals/Continuations**: Bullish Engulfing, Hammer, Morning Star, Piercing Line, 3 White Soldiers, Dragonfly Doji[cite: 8].
* **Bearish Reversals/Continuations**: Bearish Engulfing, Shooting Star, Evening Star, Dark Cloud Cover, 3 Black Crows, Gravestone Doji[cite: 8].

---

## 4. AI & EVOLUTIONARY ALGORITHMS[cite: 8]

### 4.1 Darwin Engine — Genetic Algorithm[cite: 8]
Implements a single-agent evolutionary/hill-climbing algorithm over trading strategy hyperparameters[cite: 8]:
* **Genome (DNA)**: 9 strategy genes including RSI periods, Bollinger windows, MACD settings, stop loss multipliers, and consensus thresholds[cite: 8].
* **Mutation Operator**: Selects one random gene, applies a random scale factor ∈ [0.88, 1.12], and clips to bounded ranges[cite: 8].
* **Fitness Function**: Total PnL of the current portfolio serves as the fitness proxy[cite: 8]. Reverts if new PnL is lower than previous (rollback/elitism)[cite: 8].
* **Selection Strategy**: Greedy hill-climbing with rollback[cite: 8]. Equivalent to (1+1)-ES (Evolution Strategy)[cite: 8].
* **Backtester Integration**: Runs `BT_MUTATIONS` cycles on historical data and validates minimum win rate before activating[cite: 8].

### 4.2 AI Portfolio Tracker & Grading[cite: 8]
* **Weighted Score**: Composite score = (WinRate×5) + (ProfitFactor×0.5) + (Sharpe×0.5) − (MaxDrawdown×10 penalty)[cite: 8].
* **Letter Grades**: A+ (≥5.0) down to D (<1.0), rendered as colour-coded badges[cite: 8].
* **Recommendations**: AI tracker generates text recommendations based on grade, drawdown, and win-rate thresholds[cite: 8].
* **Consolidated View**: Aggregates metrics across all portfolios into a single report[cite: 8].

---

## 5. PORTFOLIO MANAGEMENT & RISK FRAMEWORKS[cite: 8]

### 5.1 Three-Portfolio Capital Allocation[cite: 8]
Total capital (₹10 lakh) is split across three independent books[cite: 8]:
1. **Long-Term (60%)**: 10 NSE blue-chips. Daily candles, 6-month lookback. Re-scores every 60 min. Max 8 simultaneous positions[cite: 8].
2. **Short-Term (25%)**: 8 NSE mid-caps. Daily candles, 3-month lookback. Re-scores every 30 min. Max hold 10 days. Max 4 positions[cite: 8].
3. **Trading (15%)**: RELIANCE.NS only. 1-minute candles. Tick every 60 sec. Intraday scalp using full indicator suite[cite: 8].

### 5.2 Risk Management Systems[cite: 8]
* **Position Sizing**: Risk per trade = 5% of portfolio equity[cite: 8]. 
* **Daily Loss Limit**: Halts portfolio for the day if start-to-current equity drops ≥ 3%[cite: 8].
* **Consecutive Loss Cooldown**: Triggers a 300-second cooldown after 3 consecutive losing trades[cite: 8].
* **Max Time Stops**: Short-term portfolio force-exits beyond 10 calendar days[cite: 8].
* **Monte Carlo Gate**: Trade is rejected if Monte Carlo simulation gives P(profit) < 55%[cite: 8].
* **Consensus Threshold**: Minimum vote score required to enter prevents low-conviction trades[cite: 8].

### 5.3 Portfolio Rebalancer[cite: 8]
* **Target Weights**: 60% Long / 25% Short / 15% Trading[cite: 8].
* **Drift Threshold & Mechanism**: Triggered when drift exceeds ±5%. Overweight brokers withdraw capital; underweight brokers receive top-ups. Cash is redistributed without actual securities being sold[cite: 8].

---

## 6. PERFORMANCE MEASUREMENT & BACKTESTING[cite: 8]

### 6.1 Metrics Computed[cite: 8]
* **Sharpe Ratio**: mean(PnL) / std(PnL) × √(252 × 375)[cite: 8].
* **Profit Factor**: Σ winning PnLs / |Σ losing PnLs|[cite: 8].
* **Win Rate**: Count(wins) / Count(all trades)[cite: 8].
* **Max Drawdown**: Max peak-to-trough equity decline[cite: 8].

### 6.2 Backtesting Framework[cite: 8]
* **Walk-Forward Simulation**: Replays historical OHLCV bar-by-bar from 100 bars prior[cite: 8].
* **Validation Gate**: Refuses to go live if best backtest win rate < 35%[cite: 8].
* **Realistic Fill Model**: Buys at close price of the signal bar. Assumes paper trading with no slippage model[cite: 8].

---

## 7. FRONTEND — DASHBOARD ARCHITECTURE[cite: 8]

### 7.1 Streamlit Application Patterns[cite: 8]
* **Reactive Rendering & Auto-Refresh**: Updates data and charts every 1–30 seconds via `time.sleep` and `st.rerun()`[cite: 8].
* **TTL Caching**: Caches yfinance and JSON file reads for 10 seconds to avoid redundant I/O[cite: 8].
* **Multi-Page Navigation**: Includes Overview, Live Charts, Portfolios, Signal Lab, Trade History, and AI Tracker[cite: 8].
* **Mock Data Fallback**: Generates realistic random states if backend JSON is missing, preventing crashes[cite: 8].
* **Unsafe HTML Injection**: Renders custom CSS components (cards, badges, terminal log)[cite: 8].

### 7.2 Visualisation Techniques (Plotly)[cite: 8]
* **Candlestick Chart**: With EMA and Bollinger Band overlays, sharing an x-axis with a volume bar subplot[cite: 8].
* **Equity Curve Chart**: Three portfolio curves on one chart with distinct fills[cite: 8].
* **Donut/Pie & Bar Charts**: For capital allocation and stock score rankings[cite: 8].
* **RSI Gauge & Radar Chart**: For momentum tracking and 5-axis portfolio health (Win Rate, Profit Factor, Sharpe, Max DD, Trade Count)[cite: 8].

### 7.3 UI Design System — Bloomberg Terminal Aesthetic[cite: 8]
* **CSS Custom Properties**: Color palette definitions (`--bg-base #050608`, `--amber #ffb300`, `--green #00e676`, `--red #ff1744`, `--blue #40c4ff`)[cite: 8].
* **Scanline CRT Effect**: Simulates CRT scanlines from vintage terminal monitors[cite: 8].
* **Typography Pairing**: IBM Plex Mono for data, Bebas Neue for headings and readouts[cite: 8].
* **CSS Keyframe Animation**: Pulses a live status dot to indicate active connection[cite: 8].
* **Terminal Log**: Scrollable black box classifying lines by content (ok, warn, info, sys)[cite: 8].

---

*Disclaimer: This document covers every library, pattern, algorithm, and design concept used in the GOD MODE Portfolio System. For paper trading on NSE India only. Not financial advice.*[cite: 8]
