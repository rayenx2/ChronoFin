"""
Ensemble model: LSTM for temporal patterns + XGBoost for feature-based regression.
Final prediction is a weighted blend (60% LSTM / 40% XGBoost).
Tracked with MLflow.
"""
import os
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
from loguru import logger
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from ml_model.mlflow_tracking import setup_tracking

FEATURES = [
    "open", "high", "low", "volume", "vwap",
    "rsi_14", "macd", "macd_signal", "bb_upper", "bb_lower",
    "atr_14", "return_1d", "return_5d", "day_of_week",
]
TARGET = "adjusted_close"
LOOKBACK = 60
MODEL_DIR = Path(os.getenv("MODEL_DIR", "./models"))


# ── LSTM architecture ──────────────────────────────────────────────────────────

class LSTMModel(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 128,
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


# ── Data helpers ───────────────────────────────────────────────────────────────

def make_sequences(data: np.ndarray, lookback: int):
    X, y = [], []
    for i in range(lookback, len(data)):
        X.append(data[i - lookback:i, :-1])   # all feature cols
        y.append(data[i, -1])                  # target col (last)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def _invert_target(scaled_preds: np.ndarray, scaler: MinMaxScaler,
                   n_features: int) -> np.ndarray:
    """Invert MinMax scaling on the target column only."""
    dummy = np.zeros((len(scaled_preds), n_features))
    dummy[:, -1] = scaled_preds
    return scaler.inverse_transform(dummy)[:, -1]


# ── Training ───────────────────────────────────────────────────────────────────

def train_for_symbol(df: pd.DataFrame, symbol: str) -> dict:
    import mlflow
    import mlflow.sklearn
    import mlflow.pytorch

    setup_tracking()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    sym_df = df[df["symbol"] == symbol].dropna(subset=FEATURES + [TARGET])
    sym_df = sym_df.sort_values("date").reset_index(drop=True)

    if len(sym_df) < LOOKBACK + 20:
        raise ValueError(f"Insufficient data for {symbol}: {len(sym_df)} rows")

    split_idx = int(len(sym_df) * 0.85)
    train_df = sym_df.iloc[:split_idx]
    test_df  = sym_df.iloc[split_idx:]

    feature_cols = FEATURES + [TARGET]
    scaler = MinMaxScaler()
    train_scaled = scaler.fit_transform(train_df[feature_cols].values)
    test_scaled  = scaler.transform(test_df[feature_cols].values)

    X_train, y_train = make_sequences(train_scaled, LOOKBACK)
    X_test,  y_test  = make_sequences(test_scaled,  LOOKBACK)

    with mlflow.start_run(run_name=f"ensemble_{symbol}"):
        mlflow.log_param("symbol", symbol)
        mlflow.log_param("lookback", LOOKBACK)
        mlflow.log_param("train_rows", len(X_train))
        mlflow.log_param("test_rows",  len(X_test))

        # ── LSTM training ──
        device = "cuda" if torch.cuda.is_available() else "cpu"
        lstm = LSTMModel(input_size=len(FEATURES)).to(device)
        optimizer = torch.optim.Adam(lstm.parameters(), lr=1e-3, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)
        criterion = nn.HuberLoss()

        loader = DataLoader(
            TensorDataset(torch.FloatTensor(X_train).to(device),
                          torch.FloatTensor(y_train).to(device)),
            batch_size=32, shuffle=True,
        )

        best_loss, patience_count = float("inf"), 0
        for epoch in range(100):
            lstm.train()
            epoch_loss = 0.0
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = criterion(lstm(xb), yb)
                loss.backward()
                nn.utils.clip_grad_norm_(lstm.parameters(), 1.0)
                optimizer.step()
                epoch_loss += loss.item()
            scheduler.step(epoch_loss)

            if epoch_loss < best_loss:
                best_loss = epoch_loss
                patience_count = 0
                torch.save(lstm.state_dict(), MODEL_DIR / f"lstm_{symbol}_best.pt")
            else:
                patience_count += 1
                if patience_count >= 10:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break

            if epoch % 20 == 0:
                logger.info(f"{symbol} LSTM epoch {epoch:3d} | loss={epoch_loss:.6f}")

        # Load best weights
        lstm.load_state_dict(torch.load(MODEL_DIR / f"lstm_{symbol}_best.pt"))
        lstm.eval()
        with torch.no_grad():
            lstm_preds_scaled = lstm(
                torch.FloatTensor(X_test).to(device)
            ).cpu().numpy()

        # ── XGBoost training ──
        X_train_flat = X_train.reshape(len(X_train), -1)
        X_test_flat  = X_test.reshape(len(X_test),  -1)

        xgb = XGBRegressor(
            n_estimators=500, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
            early_stopping_rounds=20, eval_metric="mae", random_state=42,
        )
        xgb.fit(
            X_train_flat, y_train,
            eval_set=[(X_test_flat, y_test)],
            verbose=False,
        )
        xgb_preds_scaled = xgb.predict(X_test_flat)

        # ── Ensemble blend ──
        blend_scaled = 0.6 * lstm_preds_scaled + 0.4 * xgb_preds_scaled
        n_features   = len(feature_cols)

        preds  = _invert_target(blend_scaled, scaler, n_features)
        actual = _invert_target(y_test,       scaler, n_features)

        mae  = mean_absolute_error(actual, preds)
        rmse = float(np.sqrt(mean_squared_error(actual, preds)))
        r2   = r2_score(actual, preds)
        mape = float(np.mean(np.abs((actual - preds) / actual)) * 100)

        mlflow.log_metrics({"mae": mae, "rmse": rmse, "r2": r2, "mape": mape})
        mlflow.pytorch.log_model(lstm, f"lstm_{symbol}")
        mlflow.sklearn.log_model(xgb,  f"xgb_{symbol}")

        # Persist artifacts
        with open(MODEL_DIR / f"scaler_{symbol}.pkl", "wb") as f:
            pickle.dump(scaler, f)
        xgb.save_model(str(MODEL_DIR / f"xgb_{symbol}.json"))

        logger.success(
            f"{symbol} | MAE={mae:.2f}  RMSE={rmse:.2f}  R²={r2:.4f}  MAPE={mape:.2f}%"
        )
        return {
            "symbol": symbol, "mae": mae, "rmse": rmse, "r2": r2, "mape": mape,
            "lstm": lstm, "xgb": xgb, "scaler": scaler,
        }


def train_all(symbols: list[str], processed_path: str = "./data/processed") -> list[dict]:
    df = pd.read_parquet(processed_path)
    results = []
    for sym in symbols:
        try:
            result = train_for_symbol(df, sym)
            results.append(result)
        except Exception as e:
            logger.error(f"Training failed for {sym}: {e}")
    return results


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    results = train_all(["AAPL", "MSFT", "GOOGL"])
    for r in results:
        print(f"{r['symbol']}: MAE={r['mae']:.2f}, R²={r['r2']:.4f}")
