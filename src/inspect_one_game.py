"""
This pulls one game's play-by-play events and print it out so it's possible to manually verify it matches what actually happened in that game 

usage: python3 src/inspect_one_game.py --game-id 0022300061
"""

#allows --game-id to be passed from command line 
import argparse 

import pandas as pd 
#raw play-by-play data as JSON-like response
from nba_api.stats.endpoints import playbyplayv3 

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id",default="0022300061", help="An NBA game_id, e.g. 0022300061 (find one on nba.com/games)",
    )
    args = parser.parse_args()

    pbp = playbyplayv3.PlayByPlayV3(game_id=args.game_id)
    
    #converts response into pandas DataFrame
    df = pbp.get_data_frames()[0] 

    print(f"Total events: {len(df)}")
    print("\nColumns available:")
    print(list(df.columns))

    display_cols = ["actionNumber", "period", "clock", "scoreHome","scoreAway", "location", "description"]

    print("\nFirst 10 events:")
    print(df[display_cols].head(10))
    
    print("\nLast 10 events (end of game -- final score should match reality):")
    print(df[display_cols].tail(10))
    
    # basic sanity checks
    assert df["period"].min() >= 1, "Period should never be less than 1"
    
    # scoreHome/scoreAway are empty strings for non-scoring events, not NaN,
    # so check for non-empty instead of non-null
    non_empty_scores = df[df["scoreHome"] != ""]
    print(f"\nEvents with a recorded score: {len(non_empty_scores)} / {len(df)}")
    print("Sanity checks passed.")


if __name__ == "__main__":
    main()