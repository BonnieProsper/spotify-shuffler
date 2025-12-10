# app/shuffle/engine.py
import random
from typing import List, Dict


class ShuffleEngine:
    """
    Takes raw Spotify track objects (as dicts) and returns a new order.
    Uses a mix of true shuffle + simple constraints (artist spacing etc).
    """

    def __init__(self, *, min_artist_gap=3, weighted=False):
        self.min_artist_gap = min_artist_gap
        self.weighted = weighted

    
    def run(self, tracks: List[Dict]):
        """
        Main shuffle entry point.
        Converts tracks -> shuffles -> applies spacing rules.
        """
        if not tracks:
            return []

        # copy list so original isnt mutated
        working = list(tracks)

        if self.weighted:
            working = self._weighted_shuffle(working)
        else:
            working = self._fisher_yates(working)

        fixed = self._apply_artist_gap(working)
        return fixed

    # -----------------------------------------------------
    # Shuffle Implementations
    # -----------------------------------------------------

    def _fisher_yates(self, items):
        """
        Classic Fisher–Yates shuffle.
        Actually random (unlike Spotify).
        """
        arr = list(items)

        # simple f-y implementation
        for i in range(len(arr) - 1, 0, -1):
            j = random.randint(0, i)
            arr[i], arr[j] = arr[j], arr[i]

        return arr

    def _weighted_shuffle(self, items):
        """
        Weighted shuffle based on track popularity (or any score).
        Higher popularity = slightly higher chance earlier.
        """
        # Note: real implementation could use softmax etc (future change?)

        def weight(t):
            pop = t.get("track", {}).get("popularity")
            return pop if isinstance(pop, int) else 50

        # sort by random/weight mix
        scored = []
        for t in items:
            w = weight(t)
            scored.append((random.random() * (120 - w), t))

        scored.sort(key=lambda x: x[0])
        return [x[1] for x in scored]

    # -----------------------------------------------------
    # Constraint Logic
    # -----------------------------------------------------

    def _apply_artist_gap(self, items):
        """
        Ensures you don't get 2 songs from the same artist too close.
        Pushes conflicts forward slightly.
        """
        result = []
        last_seen = {}  # artist -> last index

        for t in items:
            artist = self._main_artist(t)

            if artist not in last_seen:
                last_seen[artist] = len(result)
                result.append(t)
                continue

            # if artist appeared too recently, push track further down
            gap = len(result) - last_seen[artist]

            if gap >= self.min_artist_gap:
                last_seen[artist] = len(result)
                result.append(t)
            else:
                # find next safe spot
                insert_at = self._find_safe_index(result, last_seen, artist)
                result.insert(insert_at, t)
                last_seen[artist] = insert_at

        return result

    def _find_safe_index(self, arr, last_seen, artist):
        """
        Finds a position where placing the track won't violate spacing.
        """
        for i in range(len(arr)):
            if artist not in last_seen:
                return i
            if i - last_seen[artist] >= self.min_artist_gap:
                return i
        return len(arr)


    @staticmethod
    def _main_artist(track):
        # Spotify structure: track -> artists -> [ dicts ]
        artists = track.get("track", {}).get("artists", [])
        if artists:
            return artists[0].get("name") or "Unknown"
        return "Unknown"
