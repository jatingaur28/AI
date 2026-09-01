"""
╔══════════════════════════════════════════════════════════════════════╗
║        8BOT QUANT ENGINE  —  APEX GOD-MODE EDITION                   ║
║     1-Sec Medallion Scalper | 1K Profit Sweep | Instant QGLP Buying  ║
╠══════════════════════════════════════════════════════════════════════╣
║  INSTALL: pip install numpy pandas scipy scikit-learn hmmlearn hurst ║
║           colorama requests                                          ║
║  RUN:     python backend_8bot.py                                     ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import asyncio
import csv
import json
import math
import os
import random
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from colorama import Back, Fore, Style, init

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError: HMM_AVAILABLE = False

try:
    from fyers_apiv3 import fyersModel
    from fyers_apiv3.FyersWebsocket import data_ws
    FYERS_AVAILABLE = True
except ImportError: FYERS_AVAILABLE = False

init(autoreset=True)
MATH_EXECUTOR = ThreadPoolExecutor(max_workers=32)

# ═══════════════════════════════════════════════════════════════════════
# 01 MASTER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MasterConfig:
    CLIENT_ID:          str   = "7K9AEBKBAJ-200"
    TOTAL_CAPITAL:      float = 1_000_000.0
    CURRENCY:           str   = "₹"
    
    # 50/50 Capital Split (No Short-Term)
    WEIGHT_LONG:        float = 0.50
    WEIGHT_TRADING:     float = 0.50
    
    # 1-Second Ultra-Fast Loop
    TR_LOOP_INTERVAL:   float = 1.0     
    TR_MAX_POSITIONS:   int   = 6
    TR_MIN_HISTORY:     int   = 40
    
    LT_EVAL_INTERVAL:   int   = 60   
    LT_MAX_POSITIONS:   int   = 20
    LT_MIN_SCORE:       float = 7.5 
    
    AI_REPORT_INTERVAL: int   = 1    
    MAX_RISK_PER_TRADE: float = 0.08
    
    BASE_DIR:           str   = field(default_factory=lambda: os.path.dirname(os.path.abspath(__file__)))
    LOG_DIR:            str   = field(init=False)
    
    ALL_NSE_EQUITIES:   List[str] = field(default_factory=list)
    LT_WATCHLIST:       List[str] = field(default_factory=list)
    TR_WATCHLIST:       List[str] = field(default_factory=list)
    _LAST_ROTATION_HR:  int       = -1

    def __post_init__(self):
        self.LOG_DIR = os.path.join(self.BASE_DIR, "logs")
        Path(self.LOG_DIR).mkdir(parents=True, exist_ok=True)
        self._load_universe()

    def _load_universe(self):
        benchmark = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", "SBIN.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS"]
        self.ALL_NSE_EQUITIES = benchmark
        self.rotate_universe(force=True)
        threading.Thread(target=self._fetch_full_universe_background, daemon=True).start()

    def _fetch_full_universe_background(self):
        try:
            res = requests.get("https://public.fyers.in/sym_details/NSE_CM.csv", timeout=10)
            if res.status_code == 200:
                valid_syms = [cols.split(':')[1].replace("-EQ", ".NS") for cols in res.text.split('\n') if len(cols.split(',')) > 10 and cols.split(',')[9].endswith("-EQ")]
                if len(valid_syms) > 100:
                    self.ALL_NSE_EQUITIES = sorted(list(set(valid_syms)))
        except Exception: pass

    def rotate_universe(self, force: bool = False) -> bool:
        current_hr = datetime.now().hour
        if not force and current_hr == self._LAST_ROTATION_HR: return False
        self._LAST_ROTATION_HR = current_hr
        np.random.seed(int(time.time()))
        active = list(np.random.choice(self.ALL_NSE_EQUITIES, min(80, len(self.ALL_NSE_EQUITIES)), replace=False))
        self.LT_WATCHLIST = active[:50] 
        self.TR_WATCHLIST = active[50:80]
        return True

# ═══════════════════════════════════════════════════════════════════════
# 02 RENAISSANCE MATH & FUNDAMENTAL ORACLE
# ═══════════════════════════════════════════════════════════════════════

class FundamentalOracle:
    """Simulates Buffet, Munger, Lynch QGLP fundamentals."""
    @staticmethod
    def get_qglp_metrics(symbol: str) -> dict:
        np.random.seed(abs(hash(symbol)) % 100000)
        roe = np.random.uniform(10.0, 35.0)
        debt_to_eq = np.random.uniform(0.0, 1.5)
        peg_ratio = np.random.uniform(0.5, 2.5)
        moat_score = np.random.uniform(50, 99) 
        
        score = 0
        if roe > 15.0: score += 3
        if debt_to_eq < 0.5: score += 3
        if peg_ratio < 1.0: score += 2 
        if moat_score > 80: score += 2
        
        return {"ROE": f"{roe:.1f}%", "D/E": f"{debt_to_eq:.2f}", "PEG": f"{peg_ratio:.2f}", "Moat": f"{moat_score:.0f}/100", "QGLP_Score": score}

class SimonsMathEngine:
    """High-Frequency Mathematical Models."""
    @staticmethod
    def shannon_entropy(prices: np.ndarray, window: int = 14) -> float:
        if len(prices) < window: return 1.0
        returns = np.diff(prices[-window:])
        hist, _ = np.histogram(returns, bins=10, density=True)
        probs = hist[hist > 0]
        return float(-np.sum(probs * np.log2(probs)))

    @staticmethod
    def ornstein_uhlenbeck_drift(prices: np.ndarray) -> float:
        """Calculates ultra-short-term mean reversion drift."""
        if len(prices) < 20: return 0.0
        y = prices[1:]
        x = prices[:-1]
        x_mat = np.vstack([x, np.ones(len(x))]).T
        try:
            theta, intercept = np.linalg.lstsq(x_mat, y, rcond=None)[0]
            if theta >= 1 or theta <= 0: return 0.0 # Random walk
            mu = intercept / (1 - theta)
            drift = (mu - prices[-1]) / prices[-1] # Normalized drift %
            return float(drift)
        except Exception: return 0.0

# ═══════════════════════════════════════════════════════════════════════
# 03 LIVE BROKER & BAYESIAN KELLY SIZER
# ═══════════════════════════════════════════════════════════════════════

class BayesianKellyRiskManager:
    def __init__(self, max_risk_cap: float = 0.08):
        self.max_risk_cap = max_risk_cap
        self.alpha_prior = 7.0
        self.beta_prior = 3.0

    def record_outcome(self, won: bool) -> None:
        if won: self.alpha_prior += 1.0
        else: self.beta_prior += 1.0

    def compute_allocation_risk(self) -> float:
        p_mean = self.alpha_prior / (self.alpha_prior + self.beta_prior)
        kelly = p_mean - ((1.0 - p_mean) / 2.0) # Assume 2:1 payoff
        return float(np.clip(kelly * 0.5, 0.02, self.max_risk_cap)) # Half-Kelly

@dataclass
class TradeRecord:
    timestamp: str; portfolio: str; symbol: str; side: str; qty: int; price: float; pnl: float = 0.0; notes: str = ""

class PaperBroker:
    def __init__(self, name: str, capital: float) -> None:
        self.name = name; self.cash = capital; self.initial_capital = capital
        self.positions: Dict[str, int] = {}
        self.entry_prices: Dict[str, float] = {}
        self.history: List[TradeRecord] = []
        self.realized_pnl: float = 0.0
        self.get_price_fn: Callable[[str], float] = lambda sym: 0.0

    @property
    def equity(self) -> float:
        pos_val = sum(qty * self.get_price_fn(sym) for sym, qty in self.positions.items() if qty > 0)
        return self.cash + pos_val
    @property
    def total_pnl(self) -> float: return self.equity - self.initial_capital

    def buy(self, symbol: str, qty: int, price: float, notes: str = "") -> bool:
        if qty <= 0 or (qty * price) > self.cash: return False
        old_qty = self.positions.get(symbol, 0)
        old_entry = self.entry_prices.get(symbol, price)
        new_qty = old_qty + qty
        self.entry_prices[symbol] = ((old_qty * old_entry) + (qty * price)) / new_qty
        self.cash -= qty * price
        self.positions[symbol] = new_qty
        self.history.append(TradeRecord(datetime.now().isoformat(timespec="seconds"), self.name, symbol, "BUY", qty, price, notes=notes))
        print(f"{Fore.GREEN}  [{self.name}] ✅ BUY  {qty:>4} {symbol} @ ₹{price:>10,.2f} | Eq: ₹{self.equity:>12,.0f}{Fore.RESET}")
        return True

    def sell(self, symbol: str, qty: int, price: float, notes: str = "") -> bool:
        held = self.positions.get(symbol, 0)
        if qty <= 0 or held < qty: return False
        self.cash += qty * price
        self.positions[symbol] = held - qty
        trade_pnl = (price - self.entry_prices.get(symbol, price)) * qty
        self.realized_pnl += trade_pnl
        if self.positions[symbol] == 0: self.entry_prices.pop(symbol, None)
        self.history.append(TradeRecord(datetime.now().isoformat(timespec="seconds"), self.name, symbol, "SELL", qty, price, pnl=trade_pnl, notes=notes))
        print(f"{Fore.GREEN if trade_pnl >= 0 else Fore.RED}  [{self.name}] {'💰' if trade_pnl >= 0 else '💸'} SELL {qty:>4} {symbol} @ ₹{price:>10,.2f} | PnL: ₹{trade_pnl:>+10,.2f}{Fore.RESET}")
        return True

    def top_up(self, amount: float) -> None: self.cash += amount
    def withdraw(self, amount: float) -> float:
        actual = min(amount, self.cash); self.cash -= actual; return actual

class PerformanceTracker:
    def __init__(self) -> None: self.pnls: List[float] = []
    def record(self, pnl: float) -> None: self.pnls.append(pnl)
    @property
    def win_rate(self) -> float: return sum(1 for p in self.pnls if p > 0) / len(self.pnls) if self.pnls else 0.50
    @property
    def profit_factor(self) -> float:
        w = sum(p for p in self.pnls if p > 0); l = abs(sum(p for p in self.pnls if p < 0))
        return round(w / l, 4) if l > 0 else 1.5

class TradeLogger:
    def __init__(self, log_dir: str, name: str) -> None:
        self.path = Path(log_dir) / f"{datetime.now():%Y-%m-%d}_{name}.csv"
        if not self.path.exists():
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=["timestamp", "portfolio", "symbol", "side", "qty", "price", "pnl", "notes"]).writeheader()
    def log(self, rec: TradeRecord) -> None:
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=list(rec.__dict__.keys())).writerow(rec.__dict__)

# ═══════════════════════════════════════════════════════════════════════
# 04 LIVE DATA FEED
# ═══════════════════════════════════════════════════════════════════════

class FyersDataFeed:
    def __init__(self, client_id: str) -> None:
        self._cache: Dict[str, pd.DataFrame] = {}
        self._live_prices: Dict[str, float] = {}
        self.client_id = client_id

    def subscribe_live_ticks(self, symbols: List[str]): pass

    async def async_fetch(self, symbol: str, interval: str = "1m", bars: int = 120) -> pd.DataFrame:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(MATH_EXECUTOR, self._simulate, symbol, bars)

    def _simulate(self, symbol: str, bars: int) -> pd.DataFrame:
        base = self.last_price(symbol)
        z = np.random.standard_normal(bars)
        closes = base * np.exp(np.cumsum((0.0001 - 0.5 * 0.01**2) + 0.01 * z))
        df = pd.DataFrame({"Close": closes, "High": closes*1.002, "Low": closes*0.998}, index=pd.date_range(end=datetime.now(), periods=bars, freq="1min"))
        self._live_prices[symbol] = float(closes[-1])
        return df

    def last_price(self, symbol: str) -> float:
        if symbol not in self._live_prices: self._live_prices[symbol] = 1800.0 + (abs(hash(symbol)) % 2500)
        # Jitter added to simulate high-frequency tape movement
        self._live_prices[symbol] *= (1.0 + np.random.uniform(-0.0008, 0.0008))
        return self._live_prices[symbol]

# ═══════════════════════════════════════════════════════════════════════
# 05 THE GOD-MODE STRATEGIES
# ═══════════════════════════════════════════════════════════════════════

class LongTermPortfolio:
    """Buffet / QGLP Value Engine. Reacts instantly when cash is swept."""
    def __init__(self, cfg: MasterConfig, feed: FyersDataFeed, broker: PaperBroker, tracker: PerformanceTracker, logger: TradeLogger) -> None:
        self.cfg, self.feed, self.broker, self.tracker, self.logger = cfg, feed, broker, tracker, logger
        self._last_eval = 0.0
        self.oracle = FundamentalOracle()

    async def _score_async(self, symbol: str) -> Tuple[str, float, dict]:
        funds = self.oracle.get_qglp_metrics(symbol)
        score = funds["QGLP_Score"]
        return symbol, score, funds

    async def evaluate(self, force: bool = False) -> None:
        # Evaluate standardly every 60s OR instantly if forced by a sweep
        if not force and (time.time() - self._last_eval < self.cfg.LT_EVAL_INTERVAL): return
        self._last_eval = time.time()
        
        tasks = [self._score_async(sym) for sym in self.cfg.LT_WATCHLIST]
        results = await asyncio.gather(*tasks)
        ranked = sorted(results, key=lambda x: x[1], reverse=True)
        top = [s for s, sc, _ in ranked if sc >= self.cfg.LT_MIN_SCORE][: self.cfg.LT_MAX_POSITIONS]

        slots = self.cfg.LT_MAX_POSITIONS - sum(1 for q in self.broker.positions.values() if q > 0)
        
        for sym, sc, funds in ranked:
            if slots <= 0 or self.broker.cash < 5000: break
            if sc >= self.cfg.LT_MIN_SCORE and self.broker.positions.get(sym, 0) == 0:
                px = self.feed.last_price(sym)
                qty = int((self.broker.cash / max(slots, 1)) / max(px, 1.0))
                if qty > 0 and self.broker.buy(sym, qty, px, notes=f"QGLP Buy (Score:{sc})"):
                    self.logger.log(self.broker.history[-1])
                    slots -= 1

class TradingPortfolio:
    """Ultra-High-Frequency Simons Scalper. Runs every 1 second."""
    def __init__(self, cfg: MasterConfig, math_engine: SimonsMathEngine, feed: FyersDataFeed, broker: PaperBroker, tracker: PerformanceTracker, logger: TradeLogger, kelly: BayesianKellyRiskManager) -> None:
        self.cfg, self.math, self.feed, self.broker, self.tracker, self.logger, self.kelly = cfg, math_engine, feed, broker, tracker, logger, kelly

    async def _process_tick(self, sym: str) -> None:
        df = await self.feed.async_fetch(sym, interval="1m", bars=60)
        c = df["Close"].values
        mid_px = self.feed.last_price(sym)
        held = self.broker.positions.get(sym, 0)
        
        # 1. Manage existing positions with hyper-tight stops & TPs
        if held > 0:
            entry = self.broker.entry_prices.get(sym, mid_px)
            ret_pct = (mid_px - entry) / entry
            
            # Take Profit at +0.15% OR Stop Loss at -0.10% (Ultra-Fast turnover)
            if ret_pct >= 0.0015 or ret_pct <= -0.0010:
                if self.broker.sell(sym, held, mid_px, notes=f"{'TAKE_PROFIT' if ret_pct > 0 else 'STOP_LOSS'}"):
                    pnl = (mid_px - entry) * held
                    self.tracker.record(pnl, self.broker.equity)
                    self.kelly.record_outcome(pnl > 0)
                    self.logger.log(self.broker.history[-1])
            return

        # 2. Look for new entries using OU Drift
        entropy = self.math.shannon_entropy(c)
        if entropy > 4.0: return # Market is completely random right now
        
        ou_drift = self.math.ornstein_uhlenbeck_drift(c)
        
        # Aggressive entry logic
        if held == 0 and (ou_drift > 0.0002 or random.random() < 0.05):
            slots = self.cfg.TR_MAX_POSITIONS - sum(1 for q in self.broker.positions.values() if q > 0)
            if slots > 0:
                risk_alloc = self.kelly.compute_allocation_risk()
                qty = int((self.broker.cash / slots * risk_alloc * 2.0) / max(mid_px, 1.0))
                if qty > 0 and self.broker.buy(sym, qty, mid_px, notes="Simons Entry"):
                    self.logger.log(self.broker.history[-1])

    async def run_tick(self) -> None:
        # Run exactly every second on a rotating batch of 15 stocks
        targets = random.sample(self.cfg.TR_WATCHLIST, min(15, len(self.cfg.TR_WATCHLIST)))
        tasks = [self._process_tick(sym) for sym in targets]
        await asyncio.gather(*tasks)

# ═══════════════════════════════════════════════════════════════════════
# 06 INSTANT PROFIT SWEEPER
# ═══════════════════════════════════════════════════════════════════════

class CapitalSweepRebalancer:
    """Instantly sweeps ALL cash generated from >=1k trading profits into Long-Term."""
    def __init__(self, cfg: MasterConfig, lt: PaperBroker, tr: PaperBroker) -> None:
        self.cfg, self.lt, self.tr = cfg, lt, tr
        self.tr_baseline = cfg.TOTAL_CAPITAL * cfg.WEIGHT_TRADING
        self.total_swept = 0.0

    def check_and_sweep(self) -> float:
        # If trading equity exceeds baseline by 1000...
        if self.tr.equity >= self.tr_baseline + 1000.0:
            excess = self.tr.equity - self.tr_baseline
            # Sweep only available cash! (Cannot sweep unrealized stocks)
            sweep_amount = min(excess, self.tr.cash)
            
            if sweep_amount >= 1000.0:
                withdrawn = self.tr.withdraw(sweep_amount)
                self.lt.top_up(withdrawn)
                self.total_swept += withdrawn
                print(f"{Fore.MAGENTA}🧹 AUTO-SWEEP: ₹{withdrawn:,.2f} locked in from TRADING to LONG-TERM VALUE.{Fore.RESET}")
                return withdrawn
        return 0.0

class AIPortfolioTracker:
    def __init__(self, cfg: MasterConfig, lt_b: PaperBroker, lt_t: PerformanceTracker, tr_b: PaperBroker, tr_t: PerformanceTracker, reb: CapitalSweepRebalancer, feed: FyersDataFeed) -> None:
        self.cfg, self.reb, self.feed = cfg, reb, feed
        self.ports = {"LONG_TERM_VALUE": (lt_b, lt_t), "MEDALLION_SCALPER": (tr_b, tr_t)}
        self._count = 0
        self._report_path = Path(cfg.LOG_DIR) / "ai_portfolio_report.json"

    def update(self) -> None:
        self._count += 1
        eq = sum(b.equity for b, _ in self.ports.values())
        
        report = {
            "report_id": self._count, "timestamp": datetime.now().isoformat(), "total_swept": round(self.reb.total_swept, 2),
            "consolidated": {"total_capital": self.cfg.TOTAL_CAPITAL, "total_equity": round(eq, 2), "total_pnl": round(eq - self.cfg.TOTAL_CAPITAL, 2), "return_pct": round((eq - self.cfg.TOTAL_CAPITAL) / self.cfg.TOTAL_CAPITAL, 4)},
            "portfolios": {
                name: {
                    "cash": round(b.cash, 2), "equity": round(b.equity, 2), "total_pnl": round(b.total_pnl, 2),
                    "trades": len(t.pnls), "win_rate": round(t.win_rate, 4), "profit_factor": round(t.profit_factor, 2),
                    "open_positions": {k: {"qty": v, "entry": round(b.entry_prices.get(k, self.feed.last_price(k)), 2), "ltp": round(self.feed.last_price(k), 2), "unrealized_pnl": round(v * (self.feed.last_price(k) - b.entry_prices.get(k, self.feed.last_price(k))), 2)} for k, v in b.positions.items() if v > 0},
                } for name, (b, t) in self.ports.items()
            },
            "live_ticks": {sym: round(self.feed.last_price(sym), 2) for sym in (self.cfg.LT_WATCHLIST[:10] + self.cfg.TR_WATCHLIST[:10])},
            "alerts": [
                f"[{datetime.now().strftime('%H:%M:%S')}] 🧹 SWEEP EVENT: Total ₹{self.reb.total_swept:,.0f} realized profits injected into Long-Term.",
                f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 MEDALLION: 1-Second micro-scalp loop active. Analyzing OU Drift.",
                f"[{datetime.now().strftime('%H:%M:%S')}] 🏛️ QGLP ORACLE: Deploying swept capital into fundamental assets."
            ]
        }
        with open(self._report_path, "w") as f: json.dump(report, f, indent=2)

# ═══════════════════════════════════════════════════════════════════════
# 07 ASYNC ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

async def orchestrate(cfg: MasterConfig, lt_b: PaperBroker, lt_t: PerformanceTracker, tr_b: PaperBroker, tr_t: PerformanceTracker) -> None:
    math_engine, feed = SimonsMathEngine(), FyersDataFeed(client_id=cfg.CLIENT_ID)
    lt_b.get_price_fn = feed.last_price; tr_b.get_price_fn = feed.last_price

    sweeper = CapitalSweepRebalancer(cfg, lt_b, tr_b)
    ai_tracker = AIPortfolioTracker(cfg, lt_b, lt_t, tr_b, tr_t, sweeper, feed)
    kelly = BayesianKellyRiskManager(max_risk_cap=cfg.MAX_RISK_PER_TRADE)

    lt_p = LongTermPortfolio(cfg, feed, lt_b, lt_t, TradeLogger(cfg.LOG_DIR, "long_term"))
    tr_p = TradingPortfolio(cfg, math_engine, feed, tr_b, tr_t, TradeLogger(cfg.LOG_DIR, "trading"), kelly)

    ai_tracker.update()
    print(f"\n{Fore.CYAN}🚀 GOD-MODE ENGINE ONLINE: 1-Second Telemetry & 1k Profit Sweeper Active.{Fore.RESET}\n")

    while True:
        try:
            t0 = time.time()
            if cfg.rotate_universe(): feed.subscribe_live_ticks(list(set(cfg.LT_WATCHLIST + cfg.TR_WATCHLIST)))

            # 1. Run 1-second high frequency scalper
            await tr_p.run_tick()
            
            # 2. Run standard long term evaluation
            await lt_p.evaluate()
            
            # 3. Check for scalping profits
            swept_amount = sweeper.check_and_sweep()
            if swept_amount > 0:
                # ⚡ INSTANT BUY: If cash was swept, force the LT portfolio to buy immediately
                await lt_p.evaluate(force=True)
            
            ai_tracker.update()
            
            elapsed = time.time() - t0
            await asyncio.sleep(max(0.1, cfg.TR_LOOP_INTERVAL - elapsed))
        except KeyboardInterrupt: raise
        except Exception as e:
            print(f"{Fore.RED}❌ Engine Error: {e}{Fore.RESET}"); await asyncio.sleep(1)

def main() -> None:
    cfg = MasterConfig()
    lt_b = PaperBroker("LONG_TERM_VALUE", cfg.TOTAL_CAPITAL * cfg.WEIGHT_LONG)
    tr_b = PaperBroker("MEDALLION_SCALPER", cfg.TOTAL_CAPITAL * cfg.WEIGHT_TRADING)
    lt_t, tr_t = PerformanceTracker(), PerformanceTracker()

    print(f"\n{Back.BLACK}{Fore.CYAN}═"*70)
    print(f"{Back.BLACK}{Fore.WHITE}{'⚡ 8BOT GOD-MODE: 50/50 PROFIT-SWEEP ENGINE':^70}")
    print(f"{Back.BLACK}{Fore.CYAN}─"*70 + Style.RESET_ALL)
    try: asyncio.run(orchestrate(cfg, lt_b, lt_t, tr_b, tr_t))
    except KeyboardInterrupt: print(f"\n{Fore.YELLOW}🛑 Stopping safely...")

if __name__ == "__main__": main()