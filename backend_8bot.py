"""
╔══════════════════════════════════════════════════════════════════════╗
║             8BOT QUANT ENGINE  —  ENTERPRISE EDITION                 ║
║             NSE Real-Time Multi-Portfolio Quantitative System        ║
╠══════════════════════════════════════════════════════════════════════╣
║  INSTALL: pip install numpy pandas talib-binary hmmlearn hurst       ║
║           colorama xgboost scikit-learn joblib fyers-apiv3 requests  ║
║  RUN:     python backend_8bot.py                                     ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import asyncio
import csv
import json
import math
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import requests
import talib
from colorama import Back, Fore, Style, init
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
from hmmlearn.hmm import GaussianHMM
from hurst import compute_Hc

init(autoreset=True)

# Thread pool for offloading CPU-heavy quantitative calculations
MATH_EXECUTOR = ThreadPoolExecutor(max_workers=4)

# ═══════════════════════════════════════════════════════════════════════
# 01 MASTER CONFIGURATION & DYNAMIC UNIVERSE ROTATOR
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MasterConfig:
    CLIENT_ID:          str   = "7K9AEBKBAJ-200"
    TOTAL_CAPITAL:      float = 1_000_000.0
    CURRENCY:           str   = "₹"
    WEIGHT_LONG:        float = 0.60
    WEIGHT_SHORT:       float = 0.25
    WEIGHT_TRADING:     float = 0.15
    REBALANCE_DRIFT:    float = 0.05
    REBALANCE_INTERVAL: int   = 24 * 3600
    MAX_RISK_PER_TRADE: float = 0.08
    DAILY_LOSS_LIMIT:   float = 0.03
    MAX_CONSEC_LOSSES:  int   = 3
    COOLDOWN_SECS:      int   = 300
    ATR_PERIOD:         int   = 14

    # Portfolio execution intervals (in seconds)
    LT_MAX_POSITIONS:   int   = 8
    LT_EVAL_INTERVAL:   int   = 600      # Evaluates every 10 minutes
    LT_MIN_SCORE:       float = 3.0
    LT_CANDLE_PERIOD:   str   = "1d"
    LT_CANDLE_LOOKBACK: str   = "6mo"

    ST_MAX_POSITIONS:   int   = 6
    ST_EVAL_INTERVAL:   int   = 120      # Evaluates every 2 minutes
    ST_MIN_SCORE:       float = 2.0
    ST_CANDLE_PERIOD:   str   = "1d"
    ST_CANDLE_LOOKBACK: str   = "3mo"
    ST_HOLD_DAYS_MAX:   int   = 10

    TR_MAX_POSITIONS:   int   = 4        # Multi-asset intraday scalping
    TR_LOOP_INTERVAL:   int   = 15       # Ticks every 15 seconds
    TR_MIN_HISTORY:     int   = 60
    TR_CANDLE_PERIOD:   str   = "1m"
    TR_FETCH_THROTTLE:  int   = 10

    BT_MIN_WIN_RATE:    float = 0.35
    BT_MUTATIONS:       int   = 5
    AI_REPORT_INTERVAL: int   = 5
    LOG_DIR:            str   = "logs"

    ALL_NSE_EQUITIES:   List[str] = field(default_factory=list)
    LT_WATCHLIST:       List[str] = field(default_factory=list)
    ST_WATCHLIST:       List[str] = field(default_factory=list)
    TR_WATCHLIST:       List[str] = field(default_factory=list)
    _LAST_ROTATION_HR:  int       = -1

    def __post_init__(self):
        """Dynamically downloads the entire active NSE universe directly from FYERS master database."""
        print(f"\n{Fore.CYAN}📥 Connecting to Exchange Master Index...{Fore.RESET}")
        try:
            res = requests.get("https://public.fyers.in/sym_details/NSE_CM.csv", timeout=15)
            if res.status_code == 200:
                valid_syms = []
                for line in res.text.split('\n'):
                    cols = line.split(',')
                    if len(cols) > 10 and cols[9].endswith("-EQ"):
                        sym = cols[9].split(':')[1].replace("-EQ", ".NS")
                        valid_syms.append(sym)
                
                self.ALL_NSE_EQUITIES = sorted(list(set(valid_syms)))
                print(f"{Fore.GREEN}✅ Acquired complete universe of {len(self.ALL_NSE_EQUITIES)} tradable NSE Equities!{Fore.RESET}")
            else:
                raise ValueError(f"HTTP Status {res.status_code}")
        except Exception as e:
            print(f"{Fore.RED}⚠️ Master index fetch warning: {e}. Falling back to default list.{Fore.RESET}")
            self.ALL_NSE_EQUITIES = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", "SBIN.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS"]

        self.rotate_universe(force=True)

    def rotate_universe(self, force: bool = False) -> bool:
        """Slices the 2,200+ stock master list into high-priority active chunks."""
        current_hr = datetime.now().hour
        if not force and current_hr == self._LAST_ROTATION_HR:
            return False
            
        self._LAST_ROTATION_HR = current_hr
        np.random.seed(int(time.time()))
        active_universe = list(np.random.choice(self.ALL_NSE_EQUITIES, min(150, len(self.ALL_NSE_EQUITIES)), replace=False))
        
        self.LT_WATCHLIST = active_universe[:60]
        self.ST_WATCHLIST = active_universe[60:120]
        self.TR_WATCHLIST = active_universe[120:150]
        print(f"{Fore.MAGENTA}🔄 UNIVERSE ROTATED: Active monitoring split across LT ({len(self.LT_WATCHLIST)}), ST ({len(self.ST_WATCHLIST)}), Scalp ({len(self.TR_WATCHLIST)}).{Fore.RESET}")
        return True

# ═══════════════════════════════════════════════════════════════════════
# 02 DARWIN GENETIC ENGINE
# ═══════════════════════════════════════════════════════════════════════

class DarwinEngine:
    GENE_BOUNDS: Dict[str, Tuple] = {
        "rsi_period":          (5, 30),
        "rsi_overbought":      (60, 85),
        "rsi_oversold":        (15, 40),
        "bollinger_window":    (10, 50),
        "macd_fast":           (5, 20),
        "macd_slow":           (15, 40),
        "macd_signal":         (5, 15),
        "stop_loss_mult":      (1.0, 4.0),
        "consensus_threshold": (2, 5),
    }

    def __init__(self) -> None:
        self.dna: Dict = {
            "rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30,
            "bollinger_window": 20, "macd_fast": 12, "macd_slow": 26,
            "macd_signal": 9, "stop_loss_mult": 2.0, "consensus_threshold": 2,
        }
        self.generation: int = 1
        self._prev_dna: Dict = dict(self.dna)
        self._prev_pnl: float = 0.0

    def mutate(self, current_pnl: float) -> None:
        if current_pnl < self._prev_pnl:
            self.dna = dict(self._prev_dna)
        self._prev_dna = dict(self.dna)
        self._prev_pnl = current_pnl
        gene = random.choice(list(self.dna.keys()))
        lo, hi = self.GENE_BOUNDS[gene]
        old = self.dna[gene]
        factor = random.uniform(0.88, 1.12)
        if isinstance(old, int):
            self.dna[gene] = int(np.clip(round(old * factor), lo, hi))
        else:
            self.dna[gene] = round(float(np.clip(old * factor, lo, hi)), 4)
        print(f"{Fore.MAGENTA}  🧬 Gen{self.generation:>3} | '{gene}': {old} → {self.dna[gene]}")
        self.generation += 1

# ═══════════════════════════════════════════════════════════════════════
# 03 NON-BLOCKING QUANT MATH & ASYNC CPU WORKERS
# ═══════════════════════════════════════════════════════════════════════

def _worker_hurst(prices: np.ndarray) -> str:
    if len(prices) < 80:
        return "UNKNOWN"
    try:
        H, _, _ = compute_Hc(prices, kind="price", simplified=True)
        return "TRENDING" if H > 0.58 else ("MEAN_REVERTING" if H < 0.42 else "NEUTRAL")
    except Exception:
        return "NEUTRAL"

def _worker_monte_carlo(price: float, vol: float, drift: float, simulations: int) -> Tuple[bool, float]:
    z = np.random.standard_normal(simulations)
    paths = price * np.exp((drift - 0.5 * vol**2) + vol * z)
    prob = float(np.mean(paths > price))
    return prob >= 0.48, round(prob, 4)

class QuantMath:
    def __init__(self) -> None:
        self._kf_x, self._kf_p = 0.0, 1.0
        self._kf_q, self._kf_r = 1e-5, 0.01

    def kalman_update(self, price: float) -> float:
        p_pred = self._kf_p + self._kf_q
        k = p_pred / (p_pred + self._kf_r)
        self._kf_x = self._kf_x + k * (price - self._kf_x)
        self._kf_p = (1 - k) * p_pred
        return self._kf_x

    async def async_chaos_state(self, prices: np.ndarray) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(MATH_EXECUTOR, _worker_hurst, prices)

    def rsi(self, closes: np.ndarray, period: int) -> float:
        if len(closes) < period + 1:
            return 50.0
        val = talib.RSI(closes.astype(float), timeperiod=period)[-1]
        return float(val) if not np.isnan(val) else 50.0

    def bollinger_signal(self, closes: np.ndarray, window: int) -> int:
        if len(closes) < window:
            return 0
        upper, _, lower = talib.BBANDS(closes.astype(float), timeperiod=window)
        return 1 if closes[-1] < lower[-1] else (-1 if closes[-1] > upper[-1] else 0)

    def macd_signal(self, closes: np.ndarray, fast: int, slow: int, sig: int) -> int:
        if len(closes) < slow + sig + 1:
            return 0
        macd, signal, _ = talib.MACD(closes.astype(float), fastperiod=fast, slowperiod=slow, signalperiod=sig)
        prev, curr = macd[-2] - signal[-2], macd[-1] - signal[-1]
        return 1 if (prev < 0 and curr >= 0) else (-1 if (prev > 0 and curr <= 0) else 0)

    def obv_signal(self, closes: np.ndarray, volumes: np.ndarray, lb: int = 10) -> int:
        n = min(len(closes), len(volumes))
        if n < lb + 1:
            return 0
        obv = talib.OBV(closes[:n].astype(float), volumes[:n].astype(float))
        return 1 if obv[-1] - obv[-lb] > 0 and closes[-1] - closes[-lb] < 0 else (-1 if obv[-1] - obv[-lb] < 0 and closes[-1] - closes[-lb] > 0 else 0)

    def stochastic_signal(self, h: np.ndarray, l: np.ndarray, c: np.ndarray, k: int = 14, d: int = 3) -> int:
        if len(c) < k + d:
            return 0
        try:
            sk, sd = talib.STOCH(h.astype(float), l.astype(float), c.astype(float), fastk_period=k, slowk_period=d, slowd_period=d)
            prev, curr = sk[-2] - sd[-2], sk[-1] - sd[-1]
            return 1 if prev < 0 and curr >= 0 and sk[-1] < 25 else (-1 if prev > 0 and curr <= 0 and sk[-1] > 75 else 0)
        except Exception:
            return 0

    def ema_cross(self, closes: np.ndarray, fast: int = 9, slow: int = 21) -> int:
        if len(closes) < slow + 1:
            return 0
        fe, se = talib.EMA(closes.astype(float), timeperiod=fast), talib.EMA(closes.astype(float), timeperiod=slow)
        prev, curr = fe[-2] - se[-2], fe[-1] - se[-1]
        return 1 if (prev < 0 and curr >= 0) else (-1 if (prev > 0 and curr <= 0) else 0)

    def price_vs_ema200(self, closes: np.ndarray) -> int:
        if len(closes) < 200:
            return 0
        ema200 = talib.EMA(closes.astype(float), timeperiod=200)
        return 1 if closes[-1] > ema200[-1] else -1

    def atr_trailing_stop(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int, mult: float) -> float:
        atr = talib.ATR(highs.astype(float), lows.astype(float), closes.astype(float), timeperiod=period)
        val = atr[-1] if not np.isnan(atr[-1]) else (highs[-1] - lows[-1])
        return float(closes[-1] - val * mult)

    @staticmethod
    def volume_trend(volumes: np.ndarray, window: int = 20) -> float:
        if len(volumes) < window * 2:
            return 1.0
        prev_vol = np.mean(volumes[-window * 2 : -window])
        return float(np.mean(volumes[-window:]) / prev_vol) if prev_vol > 0 else 1.0

    @staticmethod
    def proximity_to_high(closes: np.ndarray, window: int = 252) -> float:
        n = min(len(closes), window)
        if n < 2:
            return 0.5
        lo, hi = np.min(closes[-n:]), np.max(closes[-n:])
        return float((closes[-1] - lo) / (hi - lo)) if hi != lo else 0.5

    @staticmethod
    def rolling_vol(returns: np.ndarray, w: int = 20) -> float:
        return float(np.std(returns[-w:])) if len(returns) >= w else 0.02

    @staticmethod
    def rolling_drift(returns: np.ndarray, w: int = 20) -> float:
        return float(np.mean(returns[-w:])) if len(returns) >= w else 0.0

class SniperEngine:
    _BULL = [
        (talib.CDLENGULFING, 100, "BULL_ENGULF"),
        (talib.CDLHAMMER, 100, "HAMMER"),
        (talib.CDLMORNINGSTAR, 100, "MORNING_STAR"),
        (talib.CDLPIERCING, 100, "PIERCING"),
        (talib.CDL3WHITESOLDIERS, 100, "3_SOLDIERS"),
    ]
    _BEAR = [
        (talib.CDLENGULFING, -100, "BEAR_ENGULF"),
        (talib.CDLSHOOTINGSTAR, -100, "SHOOT_STAR"),
        (talib.CDLEVENINGSTAR, -100, "EVENING_STAR"),
        (talib.CDLDARKCLOUDCOVER, -100, "DARK_CLOUD"),
        (talib.CDL3BLACKCROWS, -100, "3_CROWS"),
    ]

    def detect(self, o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> Tuple[int, str]:
        if len(c) < 10:
            return 0, "NONE"
        o, h, l, c = (a.astype(float) for a in (o, h, l, c))
        for fn, exp, lbl in self._BULL:
            try:
                if fn(o, h, l, c)[-1] == exp:
                    return 1, lbl
            except Exception:
                pass
        for fn, exp, lbl in self._BEAR:
            try:
                if fn(o, h, l, c)[-1] == exp:
                    return -1, lbl
            except Exception:
                pass
        return 0, "NONE"

class AsyncMonteCarlo:
    def __init__(self, simulations: int = 600) -> None:
        self.simulations = simulations

    async def async_is_safe(self, price: float, vol: float, drift: float = 0.0) -> Tuple[bool, float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(MATH_EXECUTOR, _worker_monte_carlo, price, vol, drift, self.simulations)

# ═══════════════════════════════════════════════════════════════════════
# 04 DYNAMIC KELLY RISK SIZER & EXECUTION BROKER
# ═══════════════════════════════════════════════════════════════════════

class DynamicKellyRiskManager:
    def __init__(self, max_capital_risk: float = 0.08, fraction: float = 0.5):
        self.max_risk = max_capital_risk
        self.fraction = fraction

    def compute_allocation_risk(self, win_rate: float, profit_factor: float) -> float:
        if profit_factor <= 0 or win_rate <= 0:
            return 0.02
        p = win_rate
        q = 1.0 - p
        b = profit_factor
        kelly_raw = (p * b - q) / b
        if kelly_raw <= 0:
            return 0.01
        optimal = kelly_raw * self.fraction
        return float(np.clip(optimal, 0.015, self.max_risk))

@dataclass
class TradeRecord:
    timestamp: str
    portfolio: str
    symbol: str
    side: str
    qty: int
    price: float
    pnl: float = 0.0

class PaperBroker:
    def __init__(self, name: str, capital: float) -> None:
        self.name, self.cash, self.initial_capital = name, capital, capital
        self.positions: Dict[str, int] = {}
        self.entry_prices: Dict[str, float] = {}
        self.active_stops: Dict[str, float] = {}
        self.entry_dates: Dict[str, datetime] = {}
        self.history: List[TradeRecord] = []

    @property
    def equity(self) -> float:
        return self.cash

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.history if t.side == "SELL")

    @property
    def last_pnl(self) -> Optional[float]:
        sells = [t for t in self.history if t.side == "SELL"]
        return sells[-1].pnl if sells else None

    @property
    def return_pct(self) -> float:
        return (self.equity - self.initial_capital) / self.initial_capital

    def buy(self, symbol: str, qty: int, price: float) -> bool:
        if qty <= 0 or qty * price > self.cash:
            return False
        self.cash -= qty * price
        self.positions[symbol] = self.positions.get(symbol, 0) + qty
        self.entry_prices[symbol] = price
        self.entry_dates[symbol] = datetime.now()
        self.history.append(TradeRecord(datetime.now().isoformat(timespec="seconds"), self.name, symbol, "BUY", qty, price))
        print(f"{Fore.GREEN}  [{self.name}] ✅ BUY  {qty:>4} {symbol} @ ₹{price:>10,.2f}  cash→₹{self.cash:>12,.2f}")
        return True

    def sell(self, symbol: str, qty: int, price: float) -> bool:
        held = self.positions.get(symbol, 0)
        if qty <= 0 or held < qty:
            return False
        self.cash += qty * price
        self.positions[symbol] = held - qty
        if self.positions[symbol] == 0:
            self.entry_prices.pop(symbol, None)
            self.active_stops.pop(symbol, None)
            self.entry_dates.pop(symbol, None)
        pnl = (price - self.entry_prices.get(symbol, price)) * qty
        self.history.append(TradeRecord(datetime.now().isoformat(timespec="seconds"), self.name, symbol, "SELL", qty, price, pnl))
        print(f"{Fore.GREEN if pnl >= 0 else Fore.RED}  [{self.name}] {'💰' if pnl >= 0 else '💸'} SELL {qty:>4} {symbol} @ ₹{price:>10,.2f} PnL ₹{pnl:>+10,.2f}")
        return True

    def top_up(self, amount: float) -> None:
        self.cash += amount

    def withdraw(self, amount: float) -> float:
        actual = min(amount, self.cash)
        self.cash -= actual
        return actual

class PerformanceTracker:
    def __init__(self, name: str) -> None:
        self.name = name
        self.pnls: List[float] = []
        self.equity_curve: List[float] = []
        self.peak_equity = 0.0
        self.max_drawdown = 0.0
        self.consec_losses = 0

    def record(self, pnl: float, equity: float) -> None:
        self.pnls.append(pnl)
        self.equity_curve.append(equity)
        self.peak_equity = max(self.peak_equity, equity)
        if self.peak_equity > 0:
            self.max_drawdown = max(self.max_drawdown, (self.peak_equity - equity) / self.peak_equity)
        self.consec_losses = (self.consec_losses + 1) if pnl < 0 else 0

    @property
    def win_rate(self) -> float:
        return sum(1 for p in self.pnls if p > 0) / len(self.pnls) if self.pnls else 0.50

    @property
    def profit_factor(self) -> float:
        w = sum(p for p in self.pnls if p > 0)
        l = abs(sum(p for p in self.pnls if p < 0))
        return round(w / l, 4) if l else 1.5

    @property
    def sharpe(self) -> float:
        if len(self.pnls) < 2:
            return 0.0
        std = np.std(np.array(self.pnls))
        return round(float(np.mean(np.array(self.pnls)) / std * math.sqrt(252 * 375)), 4) if std else 0.0

    def letter_grade(self) -> str:
        score = min(self.win_rate * 5, 2.0) + min(self.profit_factor * 0.5, 2.0) + min(max(self.sharpe * 0.5, 0), 2.0) - min(self.max_drawdown * 10, 2.0)
        return "A+" if score >= 5.0 else ("A" if score >= 4.0 else ("B+" if score >= 3.0 else ("B" if score >= 2.0 else ("C" if score >= 1.0 else "D"))))

class TradeLogger:
    FIELDS = ["timestamp", "portfolio", "symbol", "side", "qty", "price", "pnl", "cash_after", "generation", "votes", "notes"]

    def __init__(self, log_dir: str, portfolio_name: str) -> None:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self.path = Path(log_dir) / f"{datetime.now():%Y-%m-%d}_{portfolio_name}.csv"
        if not self.path.exists():
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=self.FIELDS).writeheader()

    def log(self, **kw) -> None:
        row = {k: kw.get(k, "") for k in self.FIELDS}
        row.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=self.FIELDS).writerow(row)

class RiskGuard:
    def __init__(self, cfg: MasterConfig, tracker: PerformanceTracker) -> None:
        self._cfg = cfg
        self._tracker = tracker
        self._start_equity = None
        self._cooldown_until = 0.0
        self._halted = False

    def set_start(self, equity: float) -> None:
        if self._start_equity is None:
            self._start_equity = equity

    def check(self, equity: float) -> Tuple[bool, str]:
        if self._halted:
            return False, "Daily limit hit — halted."
        if time.time() < self._cooldown_until:
            return False, f"Cooldown {int(self._cooldown_until - time.time())}s"
        if self._start_equity and self._start_equity > 0:
            if (self._start_equity - equity) / self._start_equity >= self._cfg.DAILY_LOSS_LIMIT:
                self._halted = True
                return False, "Daily loss limit hit"
        if self._tracker.consec_losses >= self._cfg.MAX_CONSEC_LOSSES:
            self._cooldown_until = time.time() + self._cfg.COOLDOWN_SECS
            return False, f"{self._cfg.MAX_CONSEC_LOSSES} consec losses"
        return True, "OK"

# ═══════════════════════════════════════════════════════════════════════
# 05 FYERS DATA FEED & WEBSOCKET ENGINE
# ═══════════════════════════════════════════════════════════════════════

class FyersDataFeed:
    COLS = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self, client_id: str, throttle_secs: int = 10) -> None:
        self._throttle = throttle_secs
        self._cache: Dict[str, pd.DataFrame] = {}
        self._last_fetch: Dict[str, float] = {}
        self._live_prices: Dict[str, float] = {}
        self.client_id = client_id

        try:
            with open("fyers_token.txt", "r") as f:
                self.access_token = f.read().strip()
        except FileNotFoundError:
            print(f"{Fore.RED}⚠️ fyers_token.txt not found. Run fyers_login.py first!{Fore.RESET}")
            sys.exit(1)

        self.fyers = fyersModel.FyersModel(
            client_id=self.client_id, token=self.access_token, is_async=False, log_path=""
        )
        self._start_websocket()

    def _start_websocket(self):
        def on_message(msg):
            if isinstance(msg, dict) and "ltp" in msg and "symbol" in msg:
                sym = msg["symbol"].replace("NSE:", "").replace("-EQ", "") + ".NS"
                self._live_prices[sym] = float(msg["ltp"])

        def on_error(msg): pass
        def on_close(msg): pass
        def on_open(): pass

        auth_string = f"{self.client_id}:{self.access_token}"
        try:
            self.ws = data_ws.FyersDataSocket(
                access_token=auth_string,
                log_path="",
                litemode=False,
                write_to_file=False,
                reconnect=True,
                on_connect=on_open,
                on_close=on_close,
                on_error=on_error,
                on_message=on_message
            )
            threading.Thread(target=self.ws.connect, daemon=True).start()
            time.sleep(2)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ WebSocket fallback to REST: {e}{Fore.RESET}")

    def subscribe_live_ticks(self, symbols: List[str]):
        safe_symbols = symbols[:150]
        fyers_syms = [f"NSE:{s.replace('.NS', '')}-EQ" for s in safe_symbols]
        try:
            self.ws.subscribe(symbols=fyers_syms, data_type="SymbolUpdate")
            print(f"{Fore.CYAN}📡 FYERS WebSockets Monitoring {len(fyers_syms)} active assets.{Fore.RESET}")
        except Exception:
            pass

    def fetch(self, symbol: str, period: str = "1d", interval: str = "1d", bars: int = 200) -> Optional[pd.DataFrame]:
        key = f"{symbol}|{interval}"
        now = time.time()
        if now - self._last_fetch.get(key, 0) < self._throttle and key in self._cache:
            return self._cache[key]

        res_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "D"}
        fyers_res = res_map.get(interval, "D")
        fyers_sym = f"NSE:{symbol.replace('.NS', '')}-EQ"
        days_back = bars if fyers_res == "D" else int(bars / 375) + 2
        range_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        range_to = datetime.now().strftime("%Y-%m-%d")

        data = {"symbol": fyers_sym, "resolution": fyers_res, "date_format": "1", "range_from": range_from, "range_to": range_to, "cont_flag": "1"}
        try:
            response = self.fyers.history(data=data)
            if response and response.get("s") == "ok" and response.get("candles"):
                df = pd.DataFrame(response["candles"], columns=["Epoch", "Open", "High", "Low", "Close", "Volume"])
                df["Date"] = pd.to_datetime(df["Epoch"], unit="s")
                df = df.set_index("Date")[self.COLS].tail(bars)
                self._cache[key] = df
                self._last_fetch[key] = now
                self._live_prices[symbol] = float(df["Close"].iloc[-1])
                return df
        except Exception:
            pass
        return self._simulate(symbol, bars)

    def _simulate(self, symbol: str, bars: int) -> pd.DataFrame:
        base = self._live_prices.get(symbol, 1500.0 + random.uniform(0, 2000))
        z = np.random.standard_normal(bars)
        closes = base * np.exp(np.cumsum((0.00005 - 0.5 * 0.0015**2) + 0.0015 * z))
        opens = closes * (1 + np.random.uniform(-0.003, 0.003, bars))
        highs = np.maximum(opens, closes) * (1 + np.abs(np.random.normal(0, 0.0015, bars)))
        lows = np.minimum(opens, closes) * (1 - np.abs(np.random.normal(0, 0.0015, bars)))
        df = pd.DataFrame(
            {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": np.random.randint(50_000, 800_000, bars).astype(float)},
            index=pd.date_range(end=datetime.now(), periods=bars, freq="1min"),
        )
        self._live_prices[symbol] = float(closes[-1])
        self._cache[f"{symbol}|sim"] = df
        return df

    def last_price(self, symbol: str) -> float:
        return self._live_prices.get(symbol, 0.0)

# ═══════════════════════════════════════════════════════════════════════
# 06 CONCURRENT MULTI-PORTFOLIO ENGINES
# ═══════════════════════════════════════════════════════════════════════

class LongTermPortfolio:
    def __init__(self, cfg: MasterConfig, quant: QuantMath, feed: FyersDataFeed, broker: PaperBroker, tracker: PerformanceTracker, logger: TradeLogger, kelly: DynamicKellyRiskManager) -> None:
        self.cfg, self.quant, self.feed, self.broker, self.tracker, self.logger, self.kelly = cfg, quant, feed, broker, tracker, logger, kelly
        self._last_eval = 0.0
        self.scores: Dict[str, float] = {}

    def _score_stock(self, symbol: str) -> Tuple[float, Dict]:
        df = self.feed.fetch(symbol, period=self.cfg.LT_CANDLE_LOOKBACK, interval=self.cfg.LT_CANDLE_PERIOD, bars=250)
        if df is None or len(df) < 50:
            return 0.0, {}
        c, v = df["Close"].to_numpy(), df["Volume"].to_numpy()
        score = 0.0
        detail = {}
        if self.quant.price_vs_ema200(c) == 1:
            score += 2
            detail["EMA200"] = "ABOVE"
        rsi = self.quant.rsi(c, 14)
        if 40 <= rsi <= 65:
            score += 2
        elif rsi < 30:
            score += 1
        if (vtrd := QuantMath.volume_trend(v, 20)) > 1.05:
            score += 1.5
        if (prox := QuantMath.proximity_to_high(c, 252)) > 0.65:
            score += 1.5
        if self.quant.macd_signal(c, 12, 26, 9) == 1:
            score += 1
        return score, {"price": float(c[-1]), "score": round(score, 2)}

    async def evaluate(self) -> None:
        if time.time() - self._last_eval < self.cfg.LT_EVAL_INTERVAL:
            return
        self._last_eval = time.time()
        print(f"\n{Fore.BLUE}  📈 [LONG-TERM CORE]  |  Scanning {len(self.cfg.LT_WATCHLIST)} macro assets{Fore.RESET}")

        ranked = []
        for sym in self.cfg.LT_WATCHLIST:
            sc, det = self._score_stock(sym)
            if sc > 0:
                self.scores[sym] = sc
                ranked.append((sym, sc, det))

        ranked.sort(key=lambda x: x[1], reverse=True)
        top = [s for s, sc, _ in ranked if sc >= self.cfg.LT_MIN_SCORE][: self.cfg.LT_MAX_POSITIONS]

        for sym, qty in list(self.broker.positions.items()):
            if qty > 0 and (sym not in top or self.scores.get(sym, 0) < self.cfg.LT_MIN_SCORE - 1.5):
                if (px := self.feed.last_price(sym)) > 0 and self.broker.sell(sym, qty, px):
                    self.tracker.record(self.broker.last_pnl or 0.0, self.broker.equity)
                    self.logger.log(portfolio="LONG_TERM", symbol=sym, side="SELL", qty=qty, price=px, pnl=self.broker.last_pnl, cash_after=self.broker.cash)

        slots = self.cfg.LT_MAX_POSITIONS - sum(1 for q in self.broker.positions.values() if q > 0)
        risk_alloc = self.kelly.compute_allocation_risk(self.tracker.win_rate, self.tracker.profit_factor) * 2.5

        for sym in top:
            if slots <= 0:
                break
            if self.broker.positions.get(sym, 0) == 0 and (px := self.feed.last_price(sym)) > 0:
                qty = int((self.broker.cash / max(slots, 1) * risk_alloc) / px)
                if qty > 0 and self.broker.buy(sym, qty, px):
                    self.logger.log(portfolio="LONG_TERM", symbol=sym, side="BUY", qty=qty, price=px, cash_after=self.broker.cash)
                    slots -= 1

class ShortTermPortfolio:
    def __init__(self, cfg: MasterConfig, quant: QuantMath, sniper: SniperEngine, mc: AsyncMonteCarlo, feed: FyersDataFeed, broker: PaperBroker, tracker: PerformanceTracker, logger: TradeLogger, darwin: DarwinEngine, kelly: DynamicKellyRiskManager) -> None:
        self.cfg, self.quant, self.sniper, self.mc, self.feed, self.broker, self.tracker, self.logger, self.darwin, self.kelly = cfg, quant, sniper, mc, feed, broker, tracker, logger, darwin, kelly
        self._last_eval = 0.0

    async def _score_swing(self, symbol: str) -> Tuple[float, float, Dict]:
        df = self.feed.fetch(symbol, period=self.cfg.ST_CANDLE_LOOKBACK, interval=self.cfg.ST_CANDLE_PERIOD, bars=150)
        if df is None or len(df) < 40:
            return 0.0, 0.0, {}
        c, h, l, o = df["Close"].to_numpy(), df["High"].to_numpy(), df["Low"].to_numpy(), df["Open"].to_numpy()
        votes = 0.0
        px = float(c[-1])
        rsi = self.quant.rsi(c, 14)
        if rsi <= 38:
            votes += 2
        elif rsi >= 68:
            votes -= 2
        votes += self.quant.bollinger_signal(c, 20) + (self.quant.macd_signal(c, 12, 26, 9) * 2) + self.quant.stochastic_signal(h, l, c) + self.quant.ema_cross(c, 9, 21) + (self.sniper.detect(o, h, l, c)[0] * 2)
        safe, prob = await self.mc.async_is_safe(px, QuantMath.rolling_vol(np.diff(c)), QuantMath.rolling_drift(np.diff(c)))
        if safe:
            votes += 1
        return votes, px, {"RSI": f"{rsi:.1f}", "MC": f"{prob:.0%}"}

    async def evaluate(self) -> None:
        if time.time() - self._last_eval < self.cfg.ST_EVAL_INTERVAL:
            return
        self._last_eval = time.time()
        print(f"\n{Fore.YELLOW}  📊 [SHORT-TERM SWING]  |  Evaluating {len(self.cfg.ST_WATCHLIST)} swing candidates{Fore.RESET}")

        for sym, qty in list(self.broker.positions.items()):
            if qty > 0:
                entry_date = self.broker.entry_dates.get(sym)
                days_held = (datetime.now() - entry_date).days if entry_date else 0
                votes, px, _ = await self._score_swing(sym)
                if (days_held >= self.cfg.ST_HOLD_DAYS_MAX) or (votes <= -1 and px > 0):
                    if px > 0 and self.broker.sell(sym, qty, px):
                        pnl = self.broker.last_pnl or 0.0
                        self.tracker.record(pnl, self.broker.equity)
                        self.logger.log(portfolio="SHORT_TERM", symbol=sym, side="SELL", qty=qty, price=px, pnl=pnl, cash_after=self.broker.cash)
                        if pnl < 0:
                            self.darwin.mutate(self.broker.total_pnl)

        slots = self.cfg.ST_MAX_POSITIONS - sum(1 for q in self.broker.positions.values() if q > 0)
        cands = []
        for sym in self.cfg.ST_WATCHLIST:
            if self.broker.positions.get(sym, 0) == 0:
                v, p, d = await self._score_swing(sym)
                if v >= self.cfg.ST_MIN_SCORE and p > 0:
                    cands.append((sym, v, p, d))

        cands.sort(key=lambda x: x[1], reverse=True)
        risk_alloc = self.kelly.compute_allocation_risk(self.tracker.win_rate, self.tracker.profit_factor) * 1.8

        for sym, votes, px, detail in cands:
            if slots <= 0:
                break
            qty = int((self.broker.cash * risk_alloc) / px)
            if qty > 0 and self.broker.buy(sym, qty, px):
                self.logger.log(portfolio="SHORT_TERM", symbol=sym, side="BUY", qty=qty, price=px, cash_after=self.broker.cash)
                slots -= 1

class TradingPortfolio:
    """Intraday multi-asset scalping engine evaluating real-time 1m streams."""
    def __init__(self, cfg: MasterConfig, darwin: DarwinEngine, quant: QuantMath, sniper: SniperEngine, mc: AsyncMonteCarlo, feed: FyersDataFeed, broker: PaperBroker, tracker: PerformanceTracker, logger: TradeLogger, guard: RiskGuard, kelly: DynamicKellyRiskManager) -> None:
        self.cfg, self.darwin, self.quant, self.sniper, self.mc, self.feed, self.broker, self.tracker, self.logger, self.guard, self.kelly = cfg, darwin, quant, sniper, mc, feed, broker, tracker, logger, guard, kelly
        self._tick = 0
        try:
            self.ml_model = joblib.load("xgboost_trading_brain.pkl")
            print(f"{Fore.MAGENTA}  🧠 ML Trading Brain Active!{Fore.RESET}")
        except Exception:
            self.ml_model = None

    def _get_ml_probability(self, df: pd.DataFrame) -> float:
        if self.ml_model is None or len(df) < 40:
            return 0.50
        c = df.copy()
        c["Ret_1d"] = c["Close"].pct_change(1)
        c["Ret_3d"] = c["Close"].pct_change(3)
        c["Ret_5d"] = c["Close"].pct_change(5)
        c["Vol_10d"] = c["Ret_1d"].rolling(10).std()
        c["Vol_20d"] = c["Ret_1d"].rolling(20).std()
        c["SMA_20"] = c["Close"].rolling(20).mean()
        c["SMA_50"] = c["Close"].rolling(50).mean()
        c["Dist_SMA20"] = (c["Close"] - c["SMA_20"]) / c["SMA_20"]
        c["Dist_SMA50"] = (c["Close"] - c["SMA_50"]) / c["SMA_50"]
        bb_u = c["SMA_20"] + (2 * c["Close"].rolling(20).std())
        bb_l = c["SMA_20"] - (2 * c["Close"].rolling(20).std())
        c["BB_Pct"] = (c["Close"] - bb_l) / (bb_u - bb_l).replace(0, 1e-9)
        d = c["Close"].diff()
        gain = (d.where(d > 0, 0)).rolling(14).mean()
        loss = (-d.where(d < 0, 0)).rolling(14).mean()
        c["RSI_14"] = 100 - (100 / (1 + (gain / loss.replace(0, 1e-9))))
        feats = c[["Ret_1d", "Ret_3d", "Ret_5d", "Vol_10d", "Vol_20d", "Dist_SMA20", "Dist_SMA50", "BB_Pct", "RSI_14"]].iloc[-1:]
        if feats.isna().values.any():
            return 0.50
        return float(self.ml_model.predict_proba(feats)[0][1])

    async def run_tick(self) -> None:
        self._tick += 1
        ok, reason = self.guard.check(self.broker.equity)
        if not ok:
            print(f"{Fore.RED}  [TRADE] 🚨 GUARD: {reason}")
            return

        # Scan across active intraday watchlist
        active_scalp_symbols = self.cfg.TR_WATCHLIST[:6]
        d = self.darwin.dna

        for sym in active_scalp_symbols:
            df = self.feed.fetch(sym, period="1d", interval=self.cfg.TR_CANDLE_PERIOD, bars=120)
            if df is None or len(df) < self.cfg.TR_MIN_HISTORY:
                continue

            c, h, l, o, v = df["Close"].to_numpy(), df["High"].to_numpy(), df["Low"].to_numpy(), df["Open"].to_numpy(), df["Volume"].to_numpy()
            px = float(c[-1])
            returns = np.diff(c)
            
            ml_prob = self._get_ml_probability(df)
            votes = 0
            if ml_prob >= 0.70:
                votes += 3
            elif ml_prob <= 0.30:
                votes -= 3

            if px < self.quant.kalman_update(px) * 0.9995:
                votes += 1
            rsi = self.quant.rsi(c, d["rsi_period"])
            votes += (2 if rsi < d["rsi_oversold"] else (-2 if rsi > d["rsi_overbought"] else 0))
            votes += self.quant.bollinger_signal(c, d["bollinger_window"]) + (self.quant.macd_signal(c, d["macd_fast"], d["macd_slow"], d["macd_signal"]) * 2) + self.quant.ema_cross(c) + (self.sniper.detect(o, h, l, c)[0] * 2)
            safe, prob = await self.mc.async_is_safe(px, QuantMath.rolling_vol(returns), QuantMath.rolling_drift(returns))
            if safe:
                votes += 1

            held = self.broker.positions.get(sym, 0)
            risk_alloc = self.kelly.compute_allocation_risk(self.tracker.win_rate, self.tracker.profit_factor)

            # Execution logic
            if votes >= d["consensus_threshold"] and held == 0:
                slots = self.cfg.TR_MAX_POSITIONS - sum(1 for q in self.broker.positions.values() if q > 0)
                if slots > 0:
                    qty = int((self.broker.cash / slots * risk_alloc * (1.2 if ml_prob > 0.70 else 1.0)) / px)
                    if qty > 0 and self.broker.buy(sym, qty, px):
                        self.broker.active_stops[sym] = self.quant.atr_trailing_stop(h, l, c, self.cfg.ATR_PERIOD, d["stop_loss_mult"])
                        self.logger.log(portfolio="TRADING", symbol=sym, side="BUY", qty=qty, price=px, cash_after=self.broker.cash, votes=votes, notes=f"ML:{ml_prob:.0%}")
            elif held > 0:
                ns = self.quant.atr_trailing_stop(h, l, c, self.cfg.ATR_PERIOD, d["stop_loss_mult"])
                if ns > self.broker.active_stops.get(sym, 0.0):
                    self.broker.active_stops[sym] = ns
                if px < self.broker.active_stops.get(sym, 0) or votes <= -d["consensus_threshold"] or ml_prob < 0.25:
                    if self.broker.sell(sym, held, px):
                        pnl = self.broker.last_pnl or 0.0
                        self.tracker.record(pnl, self.broker.equity)
                        self.logger.log(portfolio="TRADING", symbol=sym, side="SELL", qty=held, price=px, pnl=pnl, cash_after=self.broker.cash)
                        if pnl < 0:
                            self.darwin.mutate(self.broker.total_pnl)

# ═══════════════════════════════════════════════════════════════════════
# 07 REBALANCER & AI TELEMETRY EXPORTER
# ═══════════════════════════════════════════════════════════════════════

class PortfolioRebalancer:
    def __init__(self, cfg: MasterConfig, lt: PaperBroker, st: PaperBroker, tr: PaperBroker) -> None:
        self.cfg, self.brokers = cfg, {"LONG": (lt, cfg.WEIGHT_LONG), "SHORT": (st, cfg.WEIGHT_SHORT), "TRADING": (tr, cfg.WEIGHT_TRADING)}
        self._last_rebalance, self.rebalance_count = 0.0, 0

    def total_equity(self) -> float:
        return sum(b.equity for b, _ in self.brokers.values())

    def current_weights(self) -> Dict[str, float]:
        t = self.total_equity()
        return {k: b.equity / t for k, (b, _) in self.brokers.items()} if t else {k: 0.0 for k in self.brokers}

    def check_and_rebalance(self) -> bool:
        if time.time() - self._last_rebalance < self.cfg.REBALANCE_INTERVAL:
            return False
        w, t = self.current_weights(), self.total_equity()
        if max(abs(w[k] - tgt) for k, (_, tgt) in self.brokers.items()) < self.cfg.REBALANCE_DRIFT:
            return False
        self._last_rebalance = time.time()
        self.rebalance_count += 1
        pool = 0.0
        for _, (b, tgt) in self.brokers.items():
            if b.equity > t * tgt + 100:
                pool += b.withdraw((b.equity - t * tgt) * 0.8)
        for _, (b, tgt) in self.brokers.items():
            if b.equity < t * tgt - 100 and pool > 0:
                needed = min(t * tgt - b.equity, pool)
                b.top_up(needed)
                pool -= needed
        return True

class AIPortfolioTracker:
    def __init__(self, cfg: MasterConfig, lt_b: PaperBroker, lt_t: PerformanceTracker, st_b: PaperBroker, st_t: PerformanceTracker, tr_b: PaperBroker, tr_t: PerformanceTracker, reb: PortfolioRebalancer, feed: FyersDataFeed) -> None:
        self.cfg, self.ports, self.reb, self.feed = cfg, {"LONG_TERM": (lt_b, lt_t), "SHORT_TERM": (st_b, st_t), "TRADING": (tr_b, tr_t)}, reb, feed
        self._last, self._count = 0.0, 0
        self._report_path = Path(cfg.LOG_DIR) / "ai_portfolio_report.json"
        Path(cfg.LOG_DIR).mkdir(parents=True, exist_ok=True)

    def update(self) -> None:
        if time.time() - self._last < self.cfg.AI_REPORT_INTERVAL:
            return
        self._last = time.time()
        self._count += 1
        all_pnls = []
        eq = sum(b.equity for b, _ in self.ports.values())
        for _, t in self.ports.values():
            all_pnls.extend(t.pnls)
        sharpe = float(np.mean(all_pnls) / np.std(all_pnls) * math.sqrt(252 * 375)) if len(all_pnls) > 1 and np.std(all_pnls) else 0.0
        report = {
            "report_id": self._count,
            "timestamp": datetime.now().isoformat(),
            "master_universe_size": len(self.cfg.ALL_NSE_EQUITIES),
            "consolidated": {
                "total_capital": self.cfg.TOTAL_CAPITAL,
                "total_equity": eq,
                "total_pnl": eq - self.cfg.TOTAL_CAPITAL,
                "return_pct": (eq - self.cfg.TOTAL_CAPITAL) / self.cfg.TOTAL_CAPITAL,
                "total_trades": len(all_pnls),
                "win_rate": sum(1 for p in all_pnls if p > 0) / len(all_pnls) if all_pnls else 0.0,
                "profit_factor": round(sum(p for p in all_pnls if p > 0) / abs(sum(p for p in all_pnls if p < 0)), 4) if sum(p for p in all_pnls if p < 0) else 1.5,
                "sharpe": sharpe,
            },
            "portfolios": {
                name: {
                    "cash": b.cash,
                    "equity": b.equity,
                    "total_pnl": b.total_pnl,
                    "return_pct": b.return_pct,
                    "trades": len(t.pnls),
                    "win_rate": t.win_rate,
                    "sharpe": t.sharpe,
                    "max_drawdown": t.max_drawdown,
                    "grade": t.letter_grade(),
                    "weight": self.reb.current_weights().get(name.replace("_TERM", ""), 0),
                    "open_positions": {k: {"qty": v, "ltp": self.feed.last_price(k)} for k, v in b.positions.items() if v > 0},
                }
                for name, (b, t) in self.ports.items()
            },
            "rebalances": self.reb.rebalance_count,
            "live_ticks": {sym: self.feed.last_price(sym) for sym in (self.cfg.LT_WATCHLIST[:4] + self.cfg.ST_WATCHLIST[:4] + self.cfg.TR_WATCHLIST[:4])},
        }
        with open(self._report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

# ═══════════════════════════════════════════════════════════════════════
# 08 MASTER ASYNC CONCURRENT ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

async def orchestrate(cfg: MasterConfig, lt_b: PaperBroker, lt_t: PerformanceTracker, st_b: PaperBroker, st_t: PerformanceTracker, tr_b: PaperBroker, tr_t: PerformanceTracker, darwin: DarwinEngine) -> None:
    quant, sniper, mc, feed = QuantMath(), SniperEngine(), AsyncMonteCarlo(simulations=600), FyersDataFeed(client_id=cfg.CLIENT_ID, throttle_secs=cfg.TR_FETCH_THROTTLE)
    kelly = DynamicKellyRiskManager(max_capital_risk=cfg.MAX_RISK_PER_TRADE)
    reb = PortfolioRebalancer(cfg, lt_b, st_b, tr_b)
    ai_tracker = AIPortfolioTracker(cfg, lt_b, lt_t, st_b, st_t, tr_b, tr_t, reb, feed)

    lt_p = LongTermPortfolio(cfg, quant, feed, lt_b, lt_t, TradeLogger(cfg.LOG_DIR, "long_term"), kelly)
    st_p = ShortTermPortfolio(cfg, quant, sniper, mc, feed, st_b, st_t, TradeLogger(cfg.LOG_DIR, "short_term"), darwin, kelly)
    tr_p = TradingPortfolio(cfg, darwin, quant, sniper, mc, feed, tr_b, tr_t, TradeLogger(cfg.LOG_DIR, "trading"), RiskGuard(cfg, tr_t), kelly)

    print(f"\n{Fore.CYAN}🚀 8BOT ENGINE ONLINE: Concurrently orchestrating Long-Term, Short-Term, & Trading Scalper.{Fore.RESET}\n")
    
    active_universe = list(set(cfg.LT_WATCHLIST + cfg.ST_WATCHLIST + cfg.TR_WATCHLIST))
    feed.subscribe_live_ticks(active_universe)

    while True:
        try:
            t0 = time.time()
            
            # Rotate stock chunks periodically
            if cfg.rotate_universe():
                new_universe = list(set(cfg.LT_WATCHLIST + cfg.ST_WATCHLIST + cfg.TR_WATCHLIST))
                feed.subscribe_live_ticks(new_universe)

            # Concurrent execution across all three portfolio engines
            await asyncio.gather(
                tr_p.run_tick(),
                st_p.evaluate(),
                lt_p.evaluate(),
                return_exceptions=True
            )
            
            reb.check_and_rebalance()
            ai_tracker.update()
            
            elapsed = time.time() - t0
            await asyncio.sleep(max(0.5, cfg.TR_LOOP_INTERVAL - elapsed))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"{Fore.RED}❌ Orchestrator loop error: {e}{Fore.RESET}")
            await asyncio.sleep(3)

def main() -> None:
    cfg = MasterConfig()
    lt_b = PaperBroker("LONG", cfg.TOTAL_CAPITAL * cfg.WEIGHT_LONG)
    st_b = PaperBroker("SHORT", cfg.TOTAL_CAPITAL * cfg.WEIGHT_SHORT)
    tr_b = PaperBroker("TRADING", cfg.TOTAL_CAPITAL * cfg.WEIGHT_TRADING)
    lt_t, st_t, tr_t = PerformanceTracker("LONG"), PerformanceTracker("SHORT"), PerformanceTracker("TRADING")

    print(f"\n{Back.BLACK}{Fore.CYAN}═"*64)
    print(f"{Back.BLACK}{Fore.WHITE}{'🚀  8BOT FULL MULTI-PORTFOLIO QUANT SYSTEM':^64}")
    print(f"{Back.BLACK}{Fore.CYAN}─"*64 + Style.RESET_ALL)

    try:
        asyncio.run(orchestrate(cfg, lt_b, lt_t, st_b, st_t, tr_b, tr_t, DarwinEngine()))
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 Stopping 8BOT Systems safely...")

if __name__ == "__main__":
    main()