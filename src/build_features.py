"""
Idea: transform raw parquet files into processed & training ready dataframe 
    - one row per game event, columns: game_id, seconds_elapsed, seconds_remaining, period, score_diff, home_win 

usage: python3 src/build_features.py
"""

from pathlib import Path 
import re 

import pandas as pd 

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

REGULATION_PERIOD_SECONDS = 12 * 60  #12 minute quarters
OT_PERIOD_SECONDS = 5 * 60 #5 minute overtime periods 


"""
Convert nba api ISO 8601-style clock string (e.g. PT11M30.00S) into seconds remaining in the current period (as a float)
"""
def parse_clock_to_seconds(clock_str: str) -> float:

    match = re.match(r"PT(\d+)M(\d+\.?\d*)S", clock_str)
    if not match:
        return None
    minutes, seconds = match.groups()
    return int(minutes) * 60 + float(seconds)

"""
Regulation periods are 12 minutes
OT periods are 5 minutes
"""
def period_length_seconds(period: int) -> int:
    return REGULATION_PERIOD_SECONDS if period <= 4 else OT_PERIOD_SECONDS



def build_features_for_game(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    #forward-fill score
    #Replace "" (non scoring events) with NaN
    #then fill any remaining leading NaNs (before the first score) with 0
    df["scoreHome"] = pd.to_numeric(df["scoreHome"].replace("", pd.NA))
    df["scoreAway"] = pd.to_numeric(df["scoreAway"].replace("", pd.NA))
    df["scoreHome"] = df["scoreHome"].ffill().fillna(0)
    df["scoreAway"] = df["scoreAway"].ffill().fillna(0)

    #parse clock into seconds remaining in the period
    df["clock_seconds"] = df["clock"].apply(parse_clock_to_seconds)

    #compute seconds_elapsed and seconds_remaining across the whole game 
    max_period = df["period"].max()
    #total duration of this specific game (accounts for OT)
    total_game_seconds = sum(period_length_seconds(p) for p in range(1, max_period + 1))
    
    def compute_elapsed(row):
        period = row["period"]
        #seconds elapsed in all periods before this one
        elapsed_before_this_period = sum(period_length_seconds(p) for p in range(1, period))
        #this period's length minus time left on the clock = time elapsed in this period
        elapsed_in_this_period = period_length_seconds(period) - row["clock_seconds"]
        
        return elapsed_before_this_period + elapsed_in_this_period
    
    df["seconds_elapsed"] = df.apply(compute_elapsed, axis=1)
    df["seconds_remaining"] = total_game_seconds - df["seconds_elapsed"]


    #score differential (home perspective)
    df["score_diff"] = df["scoreHome"] - df["scoreAway"]

    #label: did the home team win this game?
    final_row = df.iloc[-1]
    home_win = int(final_row["scoreHome"] > final_row["scoreAway"])

    result = df[["gameId", "period", "seconds_elapsed", "seconds_remaining", "score_diff"]].copy()
    result["home_win"] = home_win

    return result


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    raw_files = list(RAW_DIR.glob("*.parquet"))
    print(f"Found {len(raw_files)} raw game files")

    all_processed = []
    skipped = 0

    for i, path in enumerate(raw_files, start=1):
        try:
            df = pd.read_parquet(path)
            processed = build_features_for_game(df)
            all_processed.append(processed)
        except Exception as e:
            print(f"  skipped {path.name}: {e}")
            skipped += 1

        #show progress for every 200 game processed
        if i % 200 == 0:
            print(f"Processed {i}/{len(raw_files)} games")

    combined = pd.concat(all_processed, ignore_index=True)
    out_path = PROCESSED_DIR / "training_data.parquet"
    combined.to_parquet(out_path, index=False)

    print(f"\nDone. {len(combined)} total rows from {len(all_processed)} games "f"({skipped} skipped).")
    print(f"Saved to {out_path}")
    print("\nSample rows:")
    print(combined.sample(5))


if __name__ == "__main__":
    main()