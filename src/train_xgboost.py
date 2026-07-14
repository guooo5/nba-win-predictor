"""
Idea: train an XGBoost model on same features and same training and testing split as logistic regression model. 

usage: python3 src/train_xgboost.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import log_loss, brier_score_loss
from sklearn.model_selection import train_test_split

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def main():
    df = pd.read_parquet(PROCESSED_DIR / "training_data.parquet")
    print(f"Loaded {len(df)} rows from {df['gameId'].nunique()} games")
    
    #using only raw features 
    feature_cols = ["score_diff", "seconds_remaining"]

    #same split logic as logistic regression
    unique_games = df["gameId"].unique().tolist()
    train_games, test_games = train_test_split(unique_games, test_size=0.2, random_state=42)

    train_df = df[df["gameId"].isin(train_games)]
    test_df = df[df["gameId"].isin(test_games)]

    X_train, y_train = train_df[feature_cols], train_df["home_win"]
    X_test, y_test = test_df[feature_cols], test_df["home_win"]

    #train 
    model = xgb.XGBClassifier(
        n_estimators=200, #how many trees to build, in sequence
        max_depth=4, #how deep each tree can go
        learning_rate=0.1, #how much each new tree is allowed to correct
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    #evaluate 
    probs = model.predict_proba(X_test)[:, 1]

    loss = log_loss(y_test, probs)
    brier = brier_score_loss(y_test, probs)

    print(f"\nLog loss: {loss:.4f}")
    print(f"Brier score: {brier:.4f}")

    #feature importance
    print("\nFeature importance:")
    for name, importance in zip(feature_cols, model.feature_importances_):
        print(f"  {name}: {importance:.4f}")

    #calibration check
    calibration_df = pd.DataFrame({"predicted": probs, "actual": y_test.values})
    calibration_df["bucket"] = pd.cut(calibration_df["predicted"], bins=10)
    calibration = calibration_df.groupby("bucket", observed=True)["actual"].agg(["mean", "count"])
    print("\nCalibration (predicted bucket vs actual win rate):")
    print(calibration)

    #save
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODELS_DIR / "xgboost_model.json"
    model.save_model(out_path)
    print(f"\nModel saved to {out_path}")


if __name__ == "__main__":
    main()