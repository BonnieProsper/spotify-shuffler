# app/shuffle/models.py
"""
Simple models used by the shuffle engine and UI.

Spotify Web API returns several slightly different shapes depending on endpoint:
- playlist tracks endpoint returns items like {"track": { ...track object... }, "added_at": "...", ...}
- audio-features endpoint returns plain track-like dicts keyed by feature names

This module provides small Track dataclass that normalizes what's useful:
- id, uri, name, artists (list of dicts), popularity, duration_ms, raw (original payload)
It intentionally keeps a light footprint, enough structure to avoid messy indexing,
but not so strict that an ORM or Pydantic model is needed.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Iterable, Optional


@dataclass
class Track:
    """
    Minimal representation of a track used across the app.
    The 'raw' field keeps the original Spotify payload for fields we don't normalize yet.
    """
    id: Optional[str]
    uri: Optional[str]
    name: str
    artists: List[Dict[str, Any]]
    popularity: Optional[int] = None
    duration_ms: Optional[int] = None
    album: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # small sanity fixes so we don't have to guard everywhere
        if self.artists is None:
            self.artists = []

    # ----------------------
    # convenience accessors
    # ----------------------
    def main_artist_name(self) -> str:
        if not self.artists:
            return "Unknown"
        return self.artists[0].get("name") or "Unknown"

    def artist_ids(self) -> List[str]:
        return [a.get("id") for a in self.artists if a.get("id")]

    def to_spotify_uri(self) -> Optional[str]:
        return self.uri

    def to_dict(self) -> Dict[str, Any]:
        # provide a plain-serializable dict useful for local caches/debugging
        d = {
            "id": self.id,
            "uri": self.uri,
            "name": self.name,
            "artists": [{"id": a.get("id"), "name": a.get("name")} for a in self.artists],
            "popularity": self.popularity,
            "duration_ms": self.duration_ms,
        }
        return d

    # factory methods -----------------------------------------------------
    @classmethod
    def from_spotify_item(cls, item: Dict[str, Any]) -> "Track":
        """
        Accepts one of:
         - item from playlists/{id}/tracks -> e.g. {"track": {...}, "added_at": "..."}
         - track object (already inside 'track') -> {...}
         - audio-features like objects (partial)
        Returns a Track instance.
        """
        # if envelope (playlist item)
        track_obj = item.get("track") if isinstance(item, dict) and "track" in item else item

        if track_obj is None:
            # defensive: weird empty track object
            return cls(id=None, uri=None, name="(Unknown)", artists=[], raw=item)

        # some endpoints include only a subset, be defensive
        track_id = track_obj.get("id")
        uri = track_obj.get("uri")
        name = track_obj.get("name") or track_obj.get("title") or "(Unknown)"
        artists = track_obj.get("artists") or []
        popularity = track_obj.get("popularity")
        duration_ms = track_obj.get("duration_ms")
        album = track_obj.get("album")

        return cls(
            id=track_id,
            uri=uri,
            name=name,
            artists=artists,
            popularity=popularity,
            duration_ms=duration_ms,
            album=album,
            raw=track_obj,
        )

    @classmethod
    def from_audio_features(cls, feat_obj: Dict[str, Any]) -> "Track":
        """
        When you call audio-features, you sometimes want to combine features with track objects.
        This helper creates a Track-like object with feature fields merged into raw.
        """
        # naive mapping: some features include 'id' and 'duration_ms' but not name/artist
        return cls(
            id=feat_obj.get("id"),
            uri=None,
            name=feat_obj.get("id") or "(Unknown)",
            artists=[],
            popularity=None,
            duration_ms=feat_obj.get("duration_ms"),
            album=None,
            raw=feat_obj,
        )


@dataclass
class Playlist:
    id: Optional[str]
    name: str
    owner_id: Optional[str] = None
    tracks: List[Track] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def add_track(self, t: Track):
        self.tracks.append(t)

    def track_uris(self) -> List[str]:
        return [t.to_spotify_uri() for t in self.tracks if t.to_spotify_uri()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "tracks": [t.to_dict() for t in self.tracks],
        }


# -------------------------
# small helpers
# -------------------------
def normalize_tracks(items: Iterable[Dict[str, Any]]) -> List[Track]:
    """
    Given an iterable of Spotify playlist items (or raw tracks),
    return a list of Track objects.
    """
    out = []
    for it in items:
        try:
            tr = Track.from_spotify_item(it)
            out.append(tr)
        except Exception:
            # defensive: preserve raw item in case of odd payloads
            out.append(Track(id=None, uri=None, name="(Unknown)", artists=[], raw=it))
    return out


def playlist_from_spotify_payload(payload: Dict[str, Any]) -> Playlist:
    """
    Builds a playlist model from a Spotify playlist object (or from a 'playlist' endpoint)
    expecting keys like: id, name, owner, tracks (could be paginated).
    Intentionally permissive.
    """
    pid = payload.get("id")
    name = payload.get("name") or "(Unnamed)"
    owner = None
    if payload.get("owner"):
        owner = payload["owner"].get("id")

    # handle case where payload already contains 'tracks' as a list of items
    raw_tracks = []
    tracks_field = payload.get("tracks")
    if isinstance(tracks_field, dict) and "items" in tracks_field:
        raw_tracks = tracks_field["items"]
    elif isinstance(tracks_field, list):
        raw_tracks = tracks_field
    else:
        # sometimes get payloads with no tracks: leave empty
        raw_tracks = []

    tracks = normalize_tracks(raw_tracks)
    return Playlist(id=pid, name=name, owner_id=owner, tracks=tracks, raw=payload)
