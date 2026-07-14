"""
Fetch historical play-by-play data and save incrementally to disk as Parquet files (a file per game)

avoids holding more than one game's raw data in memory at a time
    - rate limting is required or stats.nba.com will block you

Usage:
    python3 src/fetch_data.py --season 2023-24 --max-games 50
"""

import argparse 
import time 
from pathlib import Path

import pandas as pd 
from nba_api.stats.endpoints import leaguegamefinder, playbyplayv3

#figures out path to data/raw/ relative to script itself 
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

#avoids getting rate-limited/blocked
SLEEP_SECONDS = 0.6 


"""
Idea: pull the list of unique game IDs for a given season, e.g. '2023-24'. Uses LeagueGameFinder from nba api to filtered to regular season games.

return: basic info or every game in a season, not full plays but like game IDs
"""
def get_season_game_ids(season: str) -> list[str]:
    
    finder = leaguegamefinder.LeagueGameFinder(season_nullable=season, season_type_nullable="Regular Season",)
    
    games_df = finder.get_data_frames()[0]
    
    #since each game appears twice - dedupe on GAME_ID
    game_ids = games_df["GAME_ID"].unique().tolist()
    print(f"Found {len(game_ids)} games for season {season}")
    return game_ids


"""
Idea: fetch play-by-play for a single game and save it as a Parquet file

Return: True on sucess, False if game was skipped (already exists or fetch failed)
"""
def fetch_and_save_game(game_id: str) -> bool:
    out_path = RAW_DIR / f"{game_id}.parquet"
    if out_path.exists():
        #already fetched, skip. makes it resumable
        return False  
    try:
        pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
        df = pbp.get_data_frames()[0]
    except Exception as e:
        print(f"  failed on game {game_id}: {e}")
        return False
    
    
    if df.empty:
        print(f"no play-by-play data for game {game_id}, skipping")
        return False

    df.to_parquet(out_path, index=False)
    return True

"""
idea: get thelist of game IDS, trim to --max-games for testing, then loop through calling fetch_and_save_game() on each one, with a 0.6 second sleep time pause between every call to prevent rate-limited by nba api
"""
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2023-24", help="e.g. 2023-24")
    parser.add_argument("--max-games", type=int, default=None, help="Limit number of games pulled (useful for a quick first test run)",)
    
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    game_ids = get_season_game_ids(args.season)
    if args.max_games:
        game_ids = game_ids[: args.max_games]

    fetched = 0
    for i, game_id in enumerate(game_ids, start=1):
        success = fetch_and_save_game(game_id)
        if success:
            fetched += 1
        #prints progres update every 10 games
        if i % 10 == 0:
            print(f"Processed {i}/{len(game_ids)} games ({fetched} newly fetched)")
        time.sleep(SLEEP_SECONDS)

    print(f"Done. Newly fetched {fetched} games. Raw files in {RAW_DIR}")


if __name__ == "__main__":
    main()
    
    