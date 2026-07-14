"""
Idea: train logistic regression baseline to predict home team win probability from (score_diff, seconds_remaining). 
    - split by game_id to avoid data leakage 
    - score_diff / sqrt(seconds_remaining + 1) to scale importance of a lead by how little time is left to erase it
usage: python3 src/train.py
"""

from pathlib import Path 

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss
from sklearn.model_selection import train_test_split

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def main():
    #loads the rows built from building features, each row has a game moment with score_diff, time_remaining, and final outcome 
    df = pd.read_parquet(PROCESSED_DIR / "training_data.parquet")
    print(f"Loaded {len(df)} rows from {df['gameId'].nunique()} games")
    
    #interacton feature: lead value scaled by how much time is left 
    df["score_time_interaction"] = df["score_diff"] / np.sqrt(df["seconds_remaining"] + 1)
    
    feature_cols = ["score_diff", "seconds_remaining", "score_time_interaction"]
    
    #split by game
    unique_games = df["gameId"].unique().tolist()
    #80% games to train and 20 for testing
    train_games, test_games = train_test_split(unique_games, test_size=0.2,random_state=42)
    
    train_df = df[df["gameId"].isin(train_games)]
    print(f"Train: {len(train_df)} rows from {len(train_games)} games")
    
    test_df = df[df["gameId"].isin(test_games)]
    print(f"Test: {len(test_df)} rows from {len(test_games)} games")
    
    X_train, y_train = train_df[feature_cols], train_df["home_win"]
    X_test, y_test = test_df[feature_cols], test_df["home_win"]
    
    #train 
    model = LogisticRegression()
    model.fit(X_train, y_train)
    
    #evaluate 
    #predict_proba returns two columns: prob. of losing and winning. we grab teh probabilty home team winning col
    probs = model.predict_proba(X_test)[:, 1] #probabilty of home_win == 1
    
    #measures uncertainity of probabilites, heavily penalize confident & wrong predictions
    loss = log_loss(y_test, probs)
    print(f"\nLog loss: {loss:.4f}")
    
    #accuracy of binary classification (MSE of probability predictions)
    brier = brier_score_loss(y_test, probs)
    print(f"Brier score: {brier:.4f}")
    
    #check the learned weights 
    print("\nLearned coefficients:")
    for name, coef in zip(feature_cols, model.coef_[0]):
        #score_diff and interaction should be positive 
        #bigger home lead should mean higher win probabilty 
        print(f"{name}: {coef:.4f}")
    
    #calibration check 
    calibration_df = pd.DataFrame({"predicted": probs, "actual": y_test.values})
    calibration_df["bucket"] = pd.cut(calibration_df["predicted"], bins=10)
    calibration = calibration_df.groupby("bucket", observed=True)["actual"].agg(["mean", "count"])
    print("\nCalibration (predicted bucket vs actual win rate):")
    print(calibration)
    
    # save the model 
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODELS_DIR / "logistic_baseline.pkl"
    joblib.dump(model, out_path)
    print(f"\nModel saved to {out_path}")

if __name__ == "__main__":
    main()
    
    
    