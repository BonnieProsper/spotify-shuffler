# src/shuffler/cli.py
"""
Small CLI for demo: fetch playlist, shuffle, optionally create new playlist
"""

import json
import os
from typing import List

from shuffler.spotify_client import SpotifyClient
from shuffler.shuffle_engine import anti_repeat_shuffle

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_playlist.json")


def load_local_sample() -> List[dict]:
    with open(SAMPLE_PATH, "r", encoding="utf8") as fh:
        return json.load(fh)


def main():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_use_api = bool(client_id)  # simple toggle: set env var to use real API
    if client_use_api:
        sc = SpotifyClient(client_id=client_id)
        try:
            sc.start_pkce_flow()
        except Exception as e:
            print("Auth failed. Falling back to local sample:", e)
            tracks = load_local_sample()
        else:
            pl_id = input("Enter playlist id or uri: ").strip()
            tracks = sc.get_playlist_tracks(pl_id)
    else:
        print("No SPOTIFY_CLIENT_ID found - using local sample.")
        tracks = load_local_sample()

    # tracks are Spotify track objects, use id/uri/name/artists
    shuffled = anti_repeat_shuffle(tracks, repeat_window=4, avoid_same_artist=True)

    # preview
    for i, t in enumerate(shuffled[:30], 1):
        art = t.get("artists", [{}])[0].get("name", "Unknown")
        print(f"{i:02d}. {t.get('name')} — {art}")

    # optionally create playlist (only if using API)
    if client_use_api:
        create = input("Create new playlist with this order? (y/N): ").lower() == "y"
        if create:
            me = sc._get(SPOTIFY_API + "/me")
            new = sc.create_playlist(me["id"], "Shuffled — custom")
            uris = [t["uri"] for t in shuffled]
            sc.add_tracks_to_playlist(new["id"], uris)
            print("Created playlist:", new["external_urls"].get("spotify"))
    else:
        out = {"shuffled": shuffled}
        with open("shuffled_preview.json", "w", encoding="utf8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print("Wrote shuffled_preview.json")
