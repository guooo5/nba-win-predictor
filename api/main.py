"""
Idea: FastAPI to load trained XGBoost model and show a single endpoint: 
    - POST /predict -> takes current game state and returns win probability 
    - GET  /replay/{game_id} -> full game, win probability cruve
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from nba_api.stats.endpoints import playbyplayv3
from pydantic import BaseModel

# from build_features import parse_clock_to_seconds, period_length_seconds

#add src/ to python's import search path manually, able ot reuse exact same feature building that model was trained on 
import importlib.util
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
_build_features_path = SRC_DIR / "build_features.py"

spec = importlib.util.spec_from_file_location("build_features", _build_features_path)
build_features = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_features)

parse_clock_to_seconds = build_features.parse_clock_to_seconds
period_length_seconds = build_features.period_length_seconds

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" /"xgboost_model.json"

#load the model once, when service starts up 
model = xgb.XGBClassifier()
model.load_model(MODEL_PATH)

app = FastAPI(title="NBA Win Probability API")

#cors allows next.js to call this api from browser 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],#!!!!!!!tighten this to actual frontend URL before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

#pydantic model: defines what shape of data /predict expects 
class GameState(BaseModel):
    score_diff: float
    seconds_remaining: float

@app.get("/")
def health_check():
    #endpoint to confirm the service is alive. Visit in a browser
    return {"status": "ok", "message": "NBA win probability API is running"}


@app.post("/predict")
def predict(game_state: GameState):
    """
    Takes the current game state and returns the home team's win probability
    """
    #model expects a 2D array: one row, with columns in the same order
    features = np.array([[game_state.score_diff, game_state.seconds_remaining]])

    #predict_proba returns [[prob_loss, prob_win]], so take prob_win
    win_probability = model.predict_proba(features)[0][1]

    return {
        "score_diff": game_state.score_diff,
        "seconds_remaining": game_state.seconds_remaining,
        "win_probability": round(float(win_probability), 4),
    }


"""
Same logic as replay_game.py's version
    - turns raw events into a list of per-event feature dicts, w/o probabilities yet
"""    
def build_replay_rows(df: pd.DataFrame) -> list[dict]:

    df = df.copy()
    df["scoreHome"] = pd.to_numeric(df["scoreHome"].replace("", pd.NA)).ffill().fillna(0)
    df["scoreAway"] = pd.to_numeric(df["scoreAway"].replace("", pd.NA)).ffill().fillna(0)
    df["clock_seconds"] = df["clock"].apply(parse_clock_to_seconds)

    max_period = df["period"].max()
    total_game_seconds = sum(period_length_seconds(p) for p in range(1, max_period + 1))

    rows = []
    for _, row in df.iterrows():
        period = row["period"]
        elapsed_before = sum(period_length_seconds(p) for p in range(1, period))
        elapsed_in_period = period_length_seconds(period) - row["clock_seconds"]
        seconds_elapsed = elapsed_before + elapsed_in_period
        seconds_remaining = total_game_seconds - seconds_elapsed
        
        clock_seconds_left = row["clock_seconds"]
        minutes = int(clock_seconds_left // 60)
        seconds = int(clock_seconds_left % 60)
        
        rows.append({
            "seconds_elapsed": seconds_elapsed,
            "seconds_remaining": seconds_remaining,
            "score_diff": row["scoreHome"] - row["scoreAway"],
            "score_home": row["scoreHome"],
            "score_away": row["scoreAway"],
            "description": row["description"],
            "period": int(period),
            "clock": f"{minutes}:{seconds:02d}",
        })
    return rows



def get_team_tricodes(df: pd.DataFrame) -> tuple[str, str]:
    """
    Figure out the home and away team abbreviations (e.g. 'GSW', 'SAC')
    directly from the play-by-play data -- each event is tagged with
    which team it belongs to (teamTricode) and which side (location:
    'h' for home, 'v' for away).
    """
    home_rows = df[df["location"] == "h"]["teamTricode"].dropna()
    away_rows = df[df["location"] == "v"]["teamTricode"].dropna()

    home_team = home_rows.iloc[0] if not home_rows.empty else "HOME"
    away_team = away_rows.iloc[0] if not away_rows.empty else "AWAY"
    return home_team, away_team


"""
Fetch one game's events, compute a win probability for every moment in the game, and return the full curve for the frontend to animate
"""
@app.get("/replay/{game_id}")
def get_replay(game_id: str):
    try:
        pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
        raw_df = pbp.get_data_frames()[0]
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch game from nba_api")

    if raw_df.empty:
        raise HTTPException(status_code=404, detail=f"No play-by-play found for game {game_id}")

    home_team, away_team = get_team_tricodes(raw_df)
    rows = build_replay_rows(raw_df)

    features = np.array([[r["score_diff"], r["seconds_remaining"]] for r in rows])
    probs = model.predict_proba(features)[:, 1]

    for row, prob in zip(rows, probs):
        row["win_probability"] = round(float(prob), 4)

    return {
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "events": rows,
    }