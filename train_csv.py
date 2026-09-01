import pandas as pd
import numpy as np
# Importing directly from your backend file
from backend_ai_bot import (
    MasterConfig,
    DarwinEngine,
    QuantMath,
    SniperEngine,
    MonteCarloEngine,
    Backtester
)

def load_and_prep_csv(csv_path: str, symbol: str = None) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    
    # 1. Standardize column names
    df.columns = [c.capitalize() for c in df.columns]
    
    # 2. Filter symbol if combined dataset
    if "Symbol" in df.columns and symbol:
        df = df[df["Symbol"] == symbol]
        
    # 3. Sort chronologically
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        
    # 4. Ensure numeric OHLCV
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        
    return df.dropna()

def run_historical_training(csv_path: str, generations: int = 40):
    cfg = MasterConfig()
    darwin = DarwinEngine()
    quant = QuantMath()
    sniper = SniperEngine()
    mc = MonteCarloEngine(simulations=500)
    
    # Load dataset
    df = load_and_prep_csv(csv_path)
    print(f"Loaded {len(df):,} bars of historical data.")
    
    # Split: Train (80%) vs Out-of-Sample Test (20%)
    split_idx = int(len(df) * 0.80)
    train_df = df.iloc[:split_idx].reset_index(drop=True)
    test_df = df.iloc[split_idx:].reset_index(drop=True)
    
    best_fitness = -float("inf")
    best_dna = dict(darwin.dna)
    
    print("\n" + "="*50)
    print("  🧬 STARTING HISTORICAL DARWIN EVOLUTION")
    print("="*50)
    
    for gen in range(1, generations + 1):
        bt = Backtester(cfg, darwin, quant, sniper, mc)
        res = bt.run(train_df, label=f"GEN_{gen}")
        
        # Fitness penalizes high trade frequency with poor win-rate
        fitness = res["total_pnl"] * (res["win_rate"] ** 1.5)
        
        if fitness > best_fitness:
            best_fitness = fitness
            best_dna = dict(darwin.dna)
            print(f"⭐ New Best Strategy DNA Found (Gen {gen}) | Fitness: {fitness:,.2f}")
        else:
            darwin.mutate(fitness)
            
    # Out-of-Sample Final Validation
    print("\n" + "="*50)
    print("  🔬 OUT-OF-SAMPLE TEST VALIDATION (20% Holdout)")
    print("="*50)
    darwin.dna = best_dna
    bt_validator = Backtester(cfg, darwin, quant, sniper, mc)
    test_res = bt_validator.run(test_df, label="FINAL_HOLDOUT_TEST")
    
    print("\nOptimal Hyperparameters to insert into MasterConfig / DarwinEngine:")
    print(best_dna)
    return best_dna

if __name__ == "__main__":
    # Point this to your local CSV path
    run_historical_training("indian_market_1990_2025.csv", generations=30)