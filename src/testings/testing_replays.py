import json

with open("data/replays/0022300061.json") as f:
    data = json.load(f)

events = data["events"]
#print every 40th event to get a spread across the whole game
for e in events[::40]:
    print(f"time: {e['seconds_elapsed']:.0f}s score_diff: {e['score_diff']:.0f}  "f"win_prob: {e['win_probability']:.3f}  {e['description']}")