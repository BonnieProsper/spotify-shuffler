# tests/test_models.py
from app.shuffle.models import Track, normalize_tracks, playlist_from_spotify_payload

SAMPLE_ITEM = {
    "track": {
        "id": "track123",
        "uri": "spotify:track:track123",
        "name": "Test Song",
        "artists": [{"id": "art1", "name": "Artist One"}],
        "popularity": 42,
        "duration_ms": 210000,
    }
}

def test_from_spotify_item():
    t = Track.from_spotify_item(SAMPLE_ITEM)
    assert t.id == "track123"
    assert t.uri == "spotify:track:track123"
    assert t.name == "Test Song"
    assert t.main_artist_name() == "Artist One"
    assert t.popularity == 42

def test_normalize_tracks_and_playlist():
    tracks = normalize_tracks([SAMPLE_ITEM])
    assert len(tracks) == 1
    pl_payload = {"id": "pl1", "name": "My Playlist", "owner": {"id": "me"}, "tracks": {"items": [SAMPLE_ITEM]}}
    pl = playlist_from_spotify_payload(pl_payload)
    assert pl.id == "pl1"
    assert pl.owner_id == "me"
    assert len(pl.tracks) == 1
    assert pl.tracks[0].name == "Test Song"
