"""
Idea: Pull one completed game's events, run every moment through FastAPI endpoint, and save the resulting win probability curve

usuage: python3 src/replay_game.py --game-id <game_id>
"""

import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests
from nba_api.stats.endpoints import playbyplayv3

#same clock-parsing from build_features
from build_features import parse_clock_to_seconds, period_length_seconds


REPLAYS_DIR = Path(__file__).resolve().parent.parent / "data" / "replays"
API_URL = "http://localhost:8000/predict" #!!!change when deployed


"""
Pull events for one game directly (not from data/raw and this keeps the script usable for any game, even ones that haven't been bulk-fetched)
"""
def fetch_game(game_id: str) -> pd.DataFrame:
    pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
    return pbp.get_data_frames()[0]


"""
Same feature-building logic as build_features.py, but this time also keep the 'description' text for each event -- useful later for annotating the frontend chart with what actually happened at each point
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

        rows.append({
            "seconds_elapsed": seconds_elapsed,
            "seconds_remaining": seconds_remaining,
            "score_diff": row["scoreHome"] - row["scoreAway"],
            "score_home": row["scoreHome"],
            "score_away": row["scoreAway"],
            "description": row["description"],
        })

    return rows

"""
Call the live FastAPI endpoint for a single game moment
"""
def get_win_probability(score_diff: float, seconds_remaining: float) -> float:
    response = requests.post(
        API_URL,
        json={"score_diff": score_diff, "seconds_remaining": seconds_remaining},
    )
    response.raise_for_status()  #crash loudly if the API returns an error
    return response.json()["win_probability"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", required=True, help="e.g. 0022300061")
    args = parser.parse_args()

    print(f"Fetching play-by-play for game {args.game_id}...")
    raw_df = fetch_game(args.game_id)
    print(f"Got {len(raw_df)} events")

    print("Building features...")
    rows = build_replay_rows(raw_df)

    print(f"Calling live API for {len(rows)} moments...")
    for i, row in enumerate(rows):
        row["win_probability"] = get_win_probability(
            row["score_diff"], row["seconds_remaining"]
        )
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(rows)} done")

    final = rows[-1]
    print(f"\nFinal score: home {int(final['score_home'])} - "
          f"away {int(final['score_away'])}")
    print(f"Final win probability (home): {final['win_probability']}")

    REPLAYS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPLAYS_DIR / f"{args.game_id}.json"
    with open(out_path, "w") as f:
        json.dump({"game_id": args.game_id, "events": rows}, f, indent=2)

    print(f"\nSaved replay to {out_path}")


if __name__ == "__main__":
    main()