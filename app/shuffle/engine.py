# src/shuffler/shuffle_engine.py
"""shuffle utils: fisher-yates, weighted, anti-repeat heuristics"""

import random
from collections import deque, defaultdict
from typing import List, Dict, Any, Iterable, Tuple


def fisher_yates(arr: List) -> List:
    """In-place Fisher-Yates. Returns new list and keeps caller safe."""
    a = arr[:]  # copy
    n = len(a)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)
        a[i], a[j] = a[j], a[i]
    return a


def weighted_sample_no_replace(items: List[Tuple[Any, float]]) -> List[Any]:
    """
    Weighted sampling without replacement.
    items: list of (item, weight)
    simple (to be extended), works by repeatedly sampling with weights.
    For large lists, optimize later.
    """
    pool = items[:]
    out = []
    while pool:
        total = sum(w for _, w in pool)
        r = random.random() * total
        upto = 0.0
        for idx, (it, w) in enumerate(pool):
            upto += w
            if r <= upto:
                out.append(it)
                pool.pop(idx)
                break
    return out


def anti_repeat_shuffle(tracks: List[Dict], repeat_window=3, avoid_same_artist=True) -> List[Dict]:
    """
    Shuffle while avoiding same artist within 'repeat_window'.
    Simple approach (to be extended): do fisher-yates, then try to repair conflicts by swapping.
    """
    if not tracks:
        return []

    a = fisher_yates(tracks)
    if not avoid_same_artist or repeat_window <= 0:
        return a

    # helper to get artist key (first artist id or name)
    def artist_key(t):
        art = t.get("artists") or []
        if art:
            return art[0].get("id") or art[0].get("name")
        return None

    # attempt to fix conflicts
    max_iters = len(a) * 3
    iters = 0
    while iters < max_iters:
        conflict_found = False
        for i in range(len(a)):
            # check window: positions (i+1 .. i+repeat_window)
            for j in range(i + 1, min(len(a), i + 1 + repeat_window)):
                if artist_key(a[i]) and artist_key(a[i]) == artist_key(a[j]):
                    # try swap j with a random later position where it won't conflict
                    swapped = False
                    for k in range(j + 1, len(a)):
                        if artist_key(a[k]) != artist_key(a[i]) and all(
                            artist_key(a[k]) != artist_key(a[x]) for x in range(k - repeat_window, k)
                            if 0 <= x < len(a)
                        ):
                            a[j], a[k] = a[k], a[j]
                            swapped = True
                            break
                    if not swapped:
                        # as a fallback, swap j with i-1 (if this exists)
                        if i - 1 >= 0:
                            a[j], a[i - 1] = a[i - 1], a[j]
                    conflict_found = True
            # continue scanning
        if not conflict_found:
            break
        iters += 1
    return a
