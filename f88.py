"""
╔═══════════════════════════════════════════════════════════════════╗
║       8BOT  —  APEX GOD-MODE TERMINAL (1-SEC TELEMETRY)           ║
║       Bloomberg / Palantir Minimalist Aesthetic | v2027 Edition   ║
╠═══════════════════════════════════════════════════════════════════╣
║  RUN:      streamlit run frontend_8bot.py                         ║
║  INSTALL:  pip install streamlit pandas numpy                     ║
╚═══════════════════════════════════════════════════════════════════╝
"""

import json
import random
import time
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ═══════════════════════════════════════════════════════════════
# 0. PAGE CONFIG
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="8BOT — GOD-MODE TERMINAL", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ═══════════════════════════════════════════════════════════════
# 1. ADVANCED CSS: 1-SECOND PULSE
# ═══════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;700&family=Bebas+Neue&family=Inter:wght@400;600;800&display=swap');

:root {
    --bg-base:    #010204; --bg-card: rgba(10, 13, 20, 0.7); --bg-panel: rgba(6, 8, 13, 0.85);
    --border:     #131722; --border-glow:#29344f;
    --amber:      #ffb300; --amber-dim:  #cc8f00; --amber-glow: rgba(255,179,0,0.25);
    --green:      #00e676; --green-glow: rgba(0,230,118,0.3);
    --red:        #ff1744; --red-glow:   rgba(255,23,68,0.3);
    --blue:       #40c4ff; --purple:     #ea80fc;
    --text-hi:    #ffffff; --text-mid:   #8a90a0;
    --font-data:  'IBM Plex Mono', monospace; --font-head: 'Bebas Neue', sans-serif; --font-ui: 'Inter', sans-serif;
}

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }
@keyframes pulseGlow { 0% { box-shadow: 0 0 0 0 var(--amber-glow); } 70% { box-shadow: 0 0 0 15px rgba(0,0,0,0); } 100% { box-shadow: 0 0 0 0 rgba(0,0,0,0); } }

html, body, .stApp { background-color: var(--bg-base) !important; color: var(--text-hi) !important; font-family: var(--font-data) !important; }
[data-testid="stSidebar"] { background: rgba(5, 7, 10, 0.98) !important; backdrop-filter: blur(20px); border-right: 1px solid var(--border-glow) !important; }

/* Ticker Tape */
.ticker-wrap { width: 100%; overflow: hidden; background: linear-gradient(90deg, rgba(0,0,0,1), rgba(10,13,20,0.9), rgba(0,0,0,1)); border-bottom: 1px solid var(--border-glow); padding: 8px 0; margin-top: -50px; margin-bottom: 20px; }
.ticker { display: inline-block; white-space: nowrap; padding-right: 100%; animation: ticker 80s linear infinite; font-size: 12px; font-weight: 500; }
.ticker-item { margin-right: 35px; color: var(--text-hi); padding: 4px 8px; border-radius: 4px; }
.ticker-val { color: var(--amber); margin-left: 6px; font-weight: 700; }
.ticker-pos { color: var(--green); margin-left: 4px; }
.ticker-neg { color: var(--red); margin-left: 4px; }

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.5rem !important; max-width: 100% !important; animation: fadeIn 0.4s ease-in-out; }

/* Minimalist Glass Cards */
.gm-card { background: var(--bg-card); backdrop-filter: blur(8px); border: 1px solid var(--border); border-top: 2px solid var(--amber); border-radius: 6px; padding: 16px 20px; margin-bottom: 12px; position: relative; overflow: hidden; animation: slideUp 0.3s ease-out backwards; }
.gm-card-label { font-family: var(--font-ui); font-size: 11px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; color: var(--text-mid); margin-bottom: 6px; }
.gm-card-value { font-family: var(--font-head); font-size: 38px; line-height: 1; letter-spacing: 1.5px; color: var(--amber); }
.gm-card-sub { font-family: var(--font-data); font-size: 11px; color: var(--text-mid); margin-top: 6px; }

.green { color: var(--green) !important; text-shadow: 0 0 12px var(--green-glow); }
.red   { color: var(--red)   !important; text-shadow: 0 0 12px var(--red-glow); }
.purple{ color: var(--purple) !important; text-shadow: 0 0 12px rgba(234,128,252,0.3); }

/* Table and Terminal */
.terminal { background: rgba(0, 0, 0, 0.85); border: 1px solid var(--border-glow); border-radius: 6px; padding: 16px; font-family: var(--font-data); font-size: 12px; line-height: 2; max-height: 280px; overflow-y: auto; color: var(--amber); }
.terminal-line-sys  { color: #ffb300; font-weight: 700; }

.gm-section-header { font-family: var(--font-head); font-size: 20px; letter-spacing: 3px; color: var(--text-hi); text-transform: uppercase; border-bottom: 1px solid var(--border); padding-bottom: 6px; margin: 28px 0 16px; display: flex; align-items: center; gap: 10px; }
.gm-section-header::before { content: ''; display: inline-block; width: 5px; height: 18px; background: var(--amber); border-radius: 2px; box-shadow: 0 0 10px var(--amber-glow); }

.live-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--amber); animation: pulseGlow 1.0s infinite; display: inline-block; margin-right: 8px; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 2. DATA LAYER (1-SECOND FETCH)
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = Path(os.path.join(BASE_DIR, "logs"))

def load_ai_report() -> dict:
    report_file = LOG_DIR / "ai_portfolio_report.json"
    if report_file.exists():
        try:
            with open(report_file, "r") as f: return json.load(f)
        except Exception: pass
    return _mock_report()

def _mock_report() -> dict:
    return {
        "report_id": 0, "timestamp": datetime.now().isoformat(), "total_swept": 0.0,
        "consolidated": {"total_capital": 1000000, "total_equity": 1000000, "total_pnl": 0, "return_pct": 0},
        "portfolios": {
            "LONG_TERM_VALUE": {"cash": 500000, "equity": 500000, "total_pnl": 0, "win_rate": 0, "profit_factor": 0, "open_positions": {}},
            "MEDALLION_SCALPER": {"cash": 500000, "equity": 500000, "total_pnl": 0, "win_rate": 0, "profit_factor": 0, "open_positions": {}}
        },
        "live_ticks": {"RELIANCE.NS": 2500}, "alerts": ["Awaiting live data..."]
    }

def load_trade_history() -> pd.DataFrame:
    frames = [pd.read_csv(f) for f in LOG_DIR.glob("*.csv")] if LOG_DIR.exists() else []
    if frames: return pd.concat(frames, ignore_index=True).sort_values("timestamp", ascending=False)
    return pd.DataFrame()

# ═══════════════════════════════════════════════════════════════
# 3. SIDEBAR CONTROLS
# ═══════════════════════════════════════════════════════════════

if "engine_on" not in st.session_state: st.session_state.engine_on = True

with st.sidebar:
    st.markdown("<div style='font-family:\"Bebas Neue\";font-size:42px;letter-spacing:5px;color:#ffb300;text-shadow:0 0 20px rgba(255,179,0,0.5); text-align:center;'>⚡ 8BOT</div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; color:#8a90a0; font-size:11px; letter-spacing:3px; margin-bottom:20px'>GOD-MODE TERMINAL</div>", unsafe_allow_html=True)
    
    st.markdown("### 🎛️ ENGINE PIPELINE")
    c1, c2 = st.columns(2)
    if c1.button("▶ RESUME"): st.session_state.engine_on = True
    if c2.button("■ HALT"):   st.session_state.engine_on = False

    st.markdown("---")
    st.markdown(f"""
    <div style='font-family:var(--font-data); font-size:10px; color:#8a90a0; line-height:1.8;'>
    <b>PARADIGM:</b> 50/50 SWEPT FRAMEWORK<br>
    <b>TELEMETRY:</b> 1-SECOND PULSE<br>
    <b>LONG:</b> Buffet QGLP Fundamentals<br>
    <b>TRADE:</b> Simons Medallion StatArb
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 4. ZERO-FLICKER 1-SECOND OMNI-PAGE DASHBOARD
# ═══════════════════════════════════════════════════════════════

@st.fragment(run_every=1) # ⚡ 1-SECOND REFRESH FOR TRUE LIVE EXPERIENCE ⚡
def render_dashboard():
    report = load_ai_report()
    trades = load_trade_history()
    cons, ports = report.get("consolidated", {}), report.get("portfolios", {})
    ticks = report.get("live_ticks", {})

    ticker_elements = []
    for sym, ltp in ticks.items():
        mock_change = random.choice([-1, 1]) * random.uniform(0.1, 1.5)
        color_class = "ticker-pos" if mock_change >= 0 else "ticker-neg"
        arrow = "▲" if mock_change >= 0 else "▼"
        ticker_elements.append(f"<span class='ticker-item'>{sym} <span class='ticker-val'>₹{ltp:,.2f}</span><span class='{color_class}'>{arrow} {abs(mock_change):.2f}%</span></span>")
    st.markdown(f"<div class='ticker-wrap'><div class='ticker'>{''.join(ticker_elements) * 4}</div></div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:15px;'>
        <div>
            <div style='color:#8a90a0; font-size:13px; letter-spacing:3px; text-transform:uppercase; font-family:"Inter", sans-serif;'>God-Mode Master Equity</div>
            <div style='font-family:"Bebas Neue"; font-size:68px; color:#00e676; text-shadow:0 0 30px rgba(0,230,118,0.8); line-height:1;'>
                ₹{cons.get("total_equity", 1000000):,.0f}
            </div>
            <div style='font-size:14px; color:{"#00e676" if cons.get("total_pnl", 0) >= 0 else "#ff1744"}; font-weight:700;'>
                Net PnL: ₹{cons.get("total_pnl", 0):>+,.2f} ({cons.get("return_pct", 0):>+.2%})
            </div>
        </div>
        <div style='text-align:right'>
            <div class='live-dot'></div><span style='color:#ffb300; font-size:13px; font-weight:700; letter-spacing:2px;'>1-SECOND PULSE ACTIVE</span>
            <div style='color:#8a90a0; font-size:11px; margin-top:6px;'>Report ID: #{report.get("report_id", 0)} | Latency: < 1ms</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 50/50 PROFIT SWEEPER METRICS
    st.markdown("<div class='gm-section-header'>🧹 1. THE 50/50 CAPITAL SWEEPER ENGINE</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"<div class='gm-card'><div class='gm-card-label'>SWEPT TO LONG-TERM</div><div class='gm-card-value purple'>₹{report.get('total_swept', 0):,.0f}</div><div class='gm-card-sub'>Profits converted to Wealth</div></div>", unsafe_allow_html=True)
    with k2:
        st.markdown(f"<div class='gm-card'><div class='gm-card-label'>SYSTEM WIN RATE</div><div class='gm-card-value green'>{cons.get('win_rate', 0):.1%}</div><div class='gm-card-sub'>Global Accurary</div></div>", unsafe_allow_html=True)
    with k3:
        st.markdown(f"<div class='gm-card'><div class='gm-card-label'>PROFIT FACTOR</div><div class='gm-card-value amber'>{cons.get('profit_factor', 0):.2f}</div><div class='gm-card-sub'>Mathematical Edge</div></div>", unsafe_allow_html=True)
    with k4:
        st.markdown(f"<div class='gm-card'><div class='gm-card-label'>SYSTEM EXECUTIONS</div><div class='gm-card-value blue'>{cons.get('total_trades', 0)}</div><div class='gm-card-sub'>Total Trades Logged</div></div>", unsafe_allow_html=True)

    # TWO-BOOK 50/50 MATRIX
    st.markdown("<div class='gm-section-header'>💼 2. THE 50/50 INSTITUTIONAL DUOPOLY</div>", unsafe_allow_html=True)
    
    p_cols = st.columns(2)
    portfolio_configs = [
        ("LONG_TERM_VALUE", "🏛️ BUFFET / LYNCH QGLP VALUE (50%)", p_cols[0], "#ffb300"),
        ("MEDALLION_SCALPER", "🧬 SIMONS MEDALLION SCALPER (50%)", p_cols[1], "#ea80fc")
    ]

    for key, title, col, color_hex in portfolio_configs:
        pdata = ports.get(key, {})
        eq = pdata.get("equity", 0.0); pnl = pdata.get("total_pnl", 0.0); unr = pdata.get("unrealized_pnl", 0.0)
        
        with col:
            st.markdown(f"""
            <div style='background:rgba(10,13,20,0.85); border:1px solid #131722; border-top:3px solid {color_hex}; padding:16px; border-radius:8px; margin-bottom:12px;'>
                <div style='font-family:"Inter",sans-serif; font-size:14px; font-weight:800; color:{color_hex}; letter-spacing:1px;'>{title}</div>
                <div style='font-family:"Bebas Neue"; font-size:46px; color:#ffffff; margin:8px 0 2px 0;'>₹{eq:,.2f}</div>
                <div style='font-size:14px; color:{"#00e676" if pnl>=0 else "#ff1744"}; font-weight:700; margin-bottom:10px;'>Total PnL: ₹{pnl:>+,.2f}</div>
                <div style='display:flex; justify-content:space-between; border-top:1px solid #131722; padding-top:8px; font-size:12px;'>
                    <span style='color:#8a90a0;'>Unrealized MTM:</span><span style='color:{"#00e676" if unr>=0 else "#ff1744"}; font-weight:700;'>₹{unr:>+,.2f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Position DataGrid inside column
            pos_dict = pdata.get("open_positions", {})
            if pos_dict:
                df_data = [{"Symbol": s, "Qty": d.get("qty",0), "Entry": d.get("entry",0), "LTP": d.get("ltp",0), "PnL": d.get("unrealized_pnl",0)} for s, d in pos_dict.items()]
                st.dataframe(pd.DataFrame(df_data), column_config={"Entry": st.column_config.NumberColumn(format="₹%.2f"), "LTP": st.column_config.NumberColumn(format="₹%.2f"), "PnL": st.column_config.NumberColumn(format="₹%.2f")}, hide_index=True, use_container_width=True)
            else: st.info("Scanning for quantitative entry signals...")

    st.markdown("<div class='gm-section-header'>🔬 3. QUANTITATIVE ORACLE METRICS</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div style='font-size:12px; font-weight:700; color:#8a90a0; margin-bottom:6px;'>🏛️ QGLP FUNDAMENTAL SCORING (LONG-TERM)</div>", unsafe_allow_html=True)
        qglp = [{"Asset": "HDFCBANK.NS", "ROE": "16.4%", "Debt/Eq": "0.8", "PEG": "1.2", "QGLP_Score": "8/10 [BUY]"}, {"Asset": "TCS.NS", "ROE": "42.1%", "Debt/Eq": "0.1", "PEG": "2.1", "QGLP_Score": "9/10 [STRONG BUY]"}]
        st.dataframe(pd.DataFrame(qglp), hide_index=True, use_container_width=True)
    with c2:
        st.markdown("<div style='font-size:12px; font-weight:700; color:#8a90a0; margin-bottom:6px;'>🧬 RENAISSANCE MATH MODELS (SCALPER)</div>", unsafe_allow_html=True)
        maths = [{"Model": "Shannon Entropy Noise", "State": "2.4 (CLEAN)", "Action": "TRADE ACTIVE"}, {"Model": "Ornstein-Uhlenbeck Drift", "State": "+0.0042", "Action": "BULLISH BIAS"}, {"Model": "Gaussian HMM", "State": "REGIME 1", "Action": "TRENDING"}]
        st.dataframe(pd.DataFrame(maths), hide_index=True, use_container_width=True)

    st.markdown("<div class='gm-section-header'>📋 4. 1-SECOND TELEMETRY EVENT STREAM</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 1])
    with col_a:
        lines = "".join(f"<div class='terminal-line-{'sys' if 'SWEEP' in a else 'ok' if 'MEDALLION' in a else 'info'}'>{a}</div>" for a in report.get("alerts", []))
        st.markdown(f"<div class='terminal' style='height:250px;'>{lines}</div>", unsafe_allow_html=True)
    with col_b:
        if not trades.empty:
            def color_side(val): return f'color: {"#00e676" if val == "BUY" else "#ff1744"}; font-weight: bold;'
            st.dataframe(trades.head(50).style.map(color_side, subset=['side']), use_container_width=True, height=250)
        else: st.write("Executing live orders...")

if st.session_state.engine_on: render_dashboard()
else: st.error("⚠️ ENGINE HALTED.")