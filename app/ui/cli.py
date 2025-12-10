# app/ui/cli.py
import argparse
import sys

from app.settings import Settings
from app.auth import AuthManager
from app.spotify.client import SpotifyClient
from app.shuffle.engine import ShuffleEngine


def main():
    parser = argparse.ArgumentParser(
        description="Custom Spotify Shuffler"
    )

    parser.add_argument("--playlist", "-p", help="Playlist ID to shuffle")
    parser.add_argument("--weighted", action="store_true", help="Use weighted shuffle")
    parser.add_argument("--min-gap", type=int, default=3,
                        help="Min gap between same artist (default=3)")
    parser.add_argument("--dry", action="store_true",
                        help="Don't write playlist back to Spotify")

    args = parser.parse_args()

    settings = Settings()

    # --- auth ---
    auth = AuthManager(settings)
    try:
        token = auth.load_token()
    except Exception:
        print("No cached token. Running OAuth...")
        token = auth.oauth_login()

    client = SpotifyClient(settings, token)

    # --- fetch playlist ---
    if not args.playlist:
        print("No playlist specified. Use --playlist <id>")
        sys.exit(1)

    print(f"Fetching playlist {args.playlist}...")
    tracks = client.get_playlist_tracks(args.playlist)

    if not tracks:
        print("Playlist empty or not found.")
        sys.exit(1)

    print(f"Loaded {len(tracks)} tracks.")

    # --- shuffle engine ---
    engine = ShuffleEngine(
        min_artist_gap=args.min_gap,
        weighted=args.weighted,
    )

    print("Shuffling...")
    shuffled = engine.run(tracks)

    print("First 5 tracks after shuffle:")
    for t in shuffled[:5]:
        name = t.get("track", {}).get("name")
        artist = t.get("track", {}).get("artists", [{}])[0].get("name")
        print(f"  • {name} — {artist}")

    # --- write back to Spotify ---
    if args.dry:
        print("Dry run. Not writing playlist.")
        return

    print("Writing shuffled order back to Spotify...")

    # Spotify needs only track URIs for reordering
    uris = [t["track"]["uri"] for t in shuffled]

    # Make a new playlist rather than destroy the original
    new_name = "Shuffled — " + (args.playlist or "Unknown")
    new_playlist = client.make_new_playlist(new_name)
    client.add_tracks(new_playlist["id"], uris)

    print(f"Done. New playlist created: {new_playlist['external_urls']['spotify']}")


if __name__ == "__main__":
    main()
