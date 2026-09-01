import os
import glob
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

def compute_vectorized_features(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized feature engineering for ultra-fast processing over decades of data."""
    # Price Momentum & Returns
    df['Ret_1d'] = df['Close'].pct_change(1)
    df['Ret_3d'] = df['Close'].pct_change(3)
    df['Ret_5d'] = df['Close'].pct_change(5)
    
    # Volatility
    df['Vol_10d'] = df['Ret_1d'].rolling(10).std()
    df['Vol_20d'] = df['Ret_1d'].rolling(20).std()
    
    # Simple Moving Average Distances
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['Dist_SMA20'] = (df['Close'] - df['SMA_20']) / df['SMA_20']
    df['Dist_SMA50'] = (df['Close'] - df['SMA_50']) / df['SMA_50']
    
    # Bollinger Bands (%B)
    df['BB_Upper'] = df['SMA_20'] + (2 * df['Close'].rolling(20).std())
    df['BB_Lower'] = df['SMA_20'] - (2 * df['Close'].rolling(20).std())
    df['BB_Pct'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
    
    # Vectorized RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9)
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    return df

def apply_labels(df: pd.DataFrame, horizon: int = 5, target_pct: float = 0.02) -> pd.DataFrame:
    """
    Binary Classification Label: 
    1 if the stock goes up by > target_pct within the next 'horizon' periods.
    0 otherwise.
    """
    # Calculate future maximum high over the next 'horizon' bars
    df['Future_High'] = df['High'].shift(-horizon).rolling(horizon).max()
    
    # Label 1 if future high exceeds our entry close by target percentage
    df['Target'] = np.where((df['Future_High'] - df['Close']) / df['Close'] > target_pct, 1, 0)
    
    return df

def prep_csv_for_ml(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    rename_map = {'datetime': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}
    df = df.rename(columns=rename_map)
    
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = compute_vectorized_features(df)
    df = apply_labels(df, horizon=5, target_pct=0.02) # Looking for a 2% swing trade in 5 days
    
    return df.dropna()

def train_xgboost_model(data_dir: str):
    csv_files = glob.glob(os.path.join(data_dir, "**", "*.csv"), recursive=True)
    csv_files = [f for f in csv_files if "logs" not in f]
    
    print(f"📥 Loading and extracting features from {len(csv_files)} files...")
    
    all_data = []
    # Sample files to prevent RAM overload (adjust based on your system)
    for file in np.random.choice(csv_files, size=min(20, len(csv_files)), replace=False):
        try:
            df = prep_csv_for_ml(file)
            all_data.append(df)
        except Exception:
            pass
            
    master_df = pd.concat(all_data, ignore_index=True)
    print(f"✅ Master Dataset built with {len(master_df):,} rows.")
    
    # Define feature matrix X and target y
    features = [
        'Ret_1d', 'Ret_3d', 'Ret_5d', 'Vol_10d', 'Vol_20d', 
        'Dist_SMA20', 'Dist_SMA50', 'BB_Pct', 'RSI_14'
    ]
    
    X = master_df[features]
    y = master_df['Target']
    
    # Chronological Split (No look-ahead bias)
    split_idx = int(len(master_df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print("🧠 Training XGBoost Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='logloss'
    )
    
    model.fit(X_train, y_train)
    
    # Evaluation
    predictions = model.predict(X_test)
    print("\n" + "═"*50)
    print("📊 MODEL EVALUATION (OUT OF SAMPLE)")
    print("═"*50)
    print(f"Accuracy: {accuracy_score(y_test, predictions):.2%}")
    print(classification_report(y_test, predictions))
    
    # Export the trained brain
    joblib.dump(model, "xgboost_trading_brain.pkl")
    print("💾 Model saved successfully as 'xgboost_trading_brain.pkl'")
    
    # Show feature importance
    importance = model.feature_importances_
    for f, i in zip(features, importance):
        print(f"Feature: {f:<15} Importance: {i:.4f}")

if __name__ == "__main__":
    # Point this to your directory containing the CSV files
    train_xgboost_model(data_dir="./")