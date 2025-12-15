# app/play_demo.py
"""
A tiny demo showing how the Player connects analytics and shuffle.
Run this locally even without Spotify credentials bc it uses examples/sample_playlist.json.
"""

import json
import os
from app.player.player import Player
from app.analytics import Analytics
from app.shuffle.engine import ShuffleEngine
from app.shuffle.models import normalize_tracks

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_playlist.json")


def load_sample():
    with open(SAMPLE, "r", encoding="utf8") as fh:
        data = json.load(fh)
    # expected to be a list of playlist item dicts
    return data


def main():
    items = load_sample()
    tracks = normalize_tracks(items)

    analytics = Analytics()
    player = Player(analytics=analytics, time_scale=0.05)  # speed up for demo

    engine = ShuffleEngine(min_artist_gap=3, weighted=False, rng_seed=42)
    shuffled = engine.run(tracks)

    print("Starting demo playback (type s, p, q + Enter to control)...")
    player.play_playlist(shuffled)

    # after playback show top analytics
    print("\nTop plays:", analytics.most_played(limit=5))
    print("\nHottest tracks:", analytics.hottest_tracks(limit=5))


if __name__ == "__main__":
    main()
