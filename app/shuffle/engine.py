# app/shuffle/engine.py
"""
Shuffle engine that works with Track dataclass.

Design notes:
- Primary input: List[Track]
- Backwards compatible: accepts raw spotify-style dicts too (attempts to normalize)
- Provides:
    - fisher_yates() for true uniform shuffle
    - weighted shuffle (based on Track.popularity)
    - artist-gap enforcement (min_artist_gap)
"""

from typing import List, Iterable, Union, Optional
import random
from collections import defaultdict

# local import (relative path expected in package)
from app.shuffle.models import Track, normalize_tracks


TrackLike = Union[Track, dict]


class ShuffleEngine:
    def __init__(self, *, min_artist_gap: int = 3, weighted: bool = False, rng_seed: Optional[int] = None):
        """
        min_artist_gap: minimum spacing between tracks that share the same main artist
        weighted: whether to use popularity-biased ordering before applying constraints
        rng_seed: optional seed for deterministic behavior (for tests)
        """
        self.min_artist_gap = max(0, int(min_artist_gap))
        self.weighted = bool(weighted)
        if rng_seed is not None:
            random.seed(rng_seed)

    # -----------------------
    # public entry
    # -----------------------
    def run(self, items: Iterable[TrackLike]) -> List[Track]:
        """
        Main entry point. Returns a list of Track objects in new order.

        Accepts either:
          - Iterable[Track] (preferred)
          - Iterable[spotify playlist item dicts] (fallback, uses normalize_tracks)
        """
        # permissive about input shape
        tracks = self._ensure_tracks(items)

        if not tracks:
            return []

        if self.weighted:
            shuffled = self._weighted_shuffle(tracks)
        else:
            shuffled = self._fisher_yates(tracks)

        # enforce artist spacing and other constraints
        out = self._enforce_artist_gap(shuffled, gap=self.min_artist_gap)
        return out

    # -----------------------
    # input handling
    # -----------------------
    def _ensure_tracks(self, items: Iterable[TrackLike]) -> List[Track]:
        # check: if first element is a Track then assume whole iterable is Tracks
        items = list(items)
        if not items:
            return []
        first = items[0]
        if isinstance(first, Track):
            # assume all Tracks (duck-typing)
            return [it for it in items]  # shallow copy
        # else assume raw spotify payloads -> normalize
        return normalize_tracks(items)

    # -----------------------
    # shuffles
    # -----------------------
    def _fisher_yates(self, tracks: List[Track]) -> List[Track]:
        """Classic in-place Fisher-Yates, returns a new list copy."""
        arr = list(tracks)
        for i in range(len(arr) - 1, 0, -1):
            j = random.randint(0, i)
            arr[i], arr[j] = arr[j], arr[i]
        return arr

    def _weighted_shuffle(self, tracks: List[Track]) -> List[Track]:
        """
        Lightweight weighted approach.
        - Uses Track.popularity (0-100) if present.
        - Higher popularity slightly increases chance to appear earlier.
        Not a perfect weighted permutation algorithm but chosen bc its simple and explainable. 
        Could be altered or changed according to (user) preference. 
        """
        scored = []
        for t in tracks:
            pop = t.popularity if isinstance(t.popularity, int) else 50
            # combine deterministic factor with randomness
            score = random.random() * (120 - pop)  # lower score = earlier
            scored.append((score, t))
        scored.sort(key=lambda x: x[0])
        return [t for _, t in scored]

    # -----------------------
    # constraints
    # -----------------------
    def _enforce_artist_gap(self, tracks: List[Track], gap: int) -> List[Track]:
        """
        Post-process to reduce occurrences of same artist too close together.
        Strategy:
        - Walk through shuffled list, place items into result.
        - If an item's main artist was seen within 'gap' positions, attempt to insert it later
          at the first safe position (greedy).
        - If no safe position exists, append to the end (best effort).
        """
        if gap <= 0:
            return tracks[:]

        res: List[Track] = []
        # last index seen for each artist id (use first artist id if available)
        last_seen: dict = {}

        for t in tracks:
            artist = self._main_artist_id(t)
            if artist is None:
                # treat unknown artists as unique so don't over-constrain
                res.append(t)
                continue

            last = last_seen.get(artist)
            if last is None or (len(res) - last) >= gap:
                # safe to append
                last_seen[artist] = len(res)
                res.append(t)
                continue

            # conflict: need to find a later safe slot
            insert_at = self._find_safe_spot(res, last_seen, artist, gap)
            if insert_at >= len(res):
                # no safe spot found — just append to end
                last_seen[artist] = len(res)
                res.append(t)
            else:
                res.insert(insert_at, t)
                # update last_seen indices: for simplicity, reset this artist, and shift others if needed
                # shortcut: recompute last_seen for the artists we care about
                # (not the most optimized, but ok for playlists up to few thousands)
                self._recompute_last_seen(res, last_seen)

        return res

    def _find_safe_spot(self, arr: List[Track], last_seen: dict, artist: str, gap: int) -> int:
        """
        Find first index >= 0 where placing the track would satisfy the gap.
        We try scanning from current length down to length (i.e after last items).
        """
        # try positions after current end first (fast path)
        for i in range(len(arr)):
            # placing at i means the last occurrence must be at <= i - gap
            last = last_seen.get(artist)
            if last is None or (i - last) >= gap:
                # ensure that placing here doesn't violate other artists constraints:
                # for the artist at this spot (if any), verify that this insertion
                # will not break its own gap relative to its previous occurrences 
                return i
        # if nothing sensible found, return end
        return len(arr)

    def _recompute_last_seen(self, arr: List[Track], last_seen: dict):
        """Recompute last_seen mapping for the current result array."""
        last_seen.clear()
        for idx, t in enumerate(arr):
            aid = self._main_artist_id(t)
            if aid is not None:
                last_seen[aid] = idx

    # -----------------------
    # helpers
    # -----------------------
    @staticmethod
    def _main_artist_id(t: Track) -> Optional[str]:
        """
        Get the primary artist id for a Track, if available.
        Falls back to artist name if no id present (keeps behavior stable).
        """
        if isinstance(t, Track):
            artists = t.artists or []
            if not artists:
                return None
            aid = artists[0].get("id")
            if aid:
                return aid
            # fallback to name
            return artists[0].get("name")
        # defensive: not expected
        return None
