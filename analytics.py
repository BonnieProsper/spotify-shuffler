from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class TrackStats:
    """Lightweight container for metrics about a single track."""
    play_count: int = 0
    skip_count: int = 0
    total_listen_seconds: float = 0.0
    first_play: Optional[datetime] = None
    last_play: Optional[datetime] = None

    def record_play(self, seconds_listened: float, completed: bool) -> None:
        now = datetime.now()

        if self.first_play is None:
            self.first_play = now

        self.last_play = now
        self.total_listen_seconds += max(seconds_listened, 0)
        self.play_count += 1

        if not completed:
            self.skip_count += 1

    @property
    def average_listen_seconds(self) -> float:
        if self.play_count == 0:
            return 0.0
        return self.total_listen_seconds / self.play_count

    @property
    def completion_rate(self) -> float:
        if self.play_count == 0:
            return 0.0
        completed_plays = self.play_count - self.skip_count
        return completed_plays / self.play_count

    def heat_score(self) -> float:
        """
        Weighted score representing how 'hot' this track is for the user.
        Can tune these weights later.
        """
        if self.play_count == 0:
            return 0.0

        score = (
            self.play_count * 1.5 +
            (self.play_count - self.skip_count) * 2.0 +
            (self.last_play.timestamp() / 10_000_000)  # time influence
        )
        return round(score, 2)


class Analytics:
    """
    Central analytics hub. Tracks per-track behavior and provides aggregate stats.
    Will later feed into the shuffle engine for preference-aware shuffling.
    """

    def __init__(self):
        self._stats: Dict[str, TrackStats] = {}

    def track_started(self, track_id: str) -> None:
        """Called when a track begins playing."""
        # store the timestamp here, end-of-play events use it.
        self._ensure_track(track_id)
        self._stats[track_id]._current_start = datetime.now()

    def track_finished(self, track_id: str, completed: bool = True) -> None:
        """
        Called when a track ends or is skipped.
        'completed=False' means user skipped or force-changed track.
        """
        data = self._stats.get(track_id)
        if not data:
            return  # Should never happen, but avoid errors

        start_ts: Optional[datetime] = getattr(data, "_current_start", None)
        if start_ts is None:
            return

        seconds = (datetime.now() - start_ts).total_seconds()

        # Clean up the temp field
        delattr(data, "_current_start")

        data.record_play(seconds_listened=seconds, completed=completed)

    # -----------------------------
    # Query Helpers (What the CLI/GUI will show)
    # -----------------------------

    def get_stats(self, track_id: str) -> Optional[TrackStats]:
        return self._stats.get(track_id)

    def most_played(self, limit: int = 10):
        return sorted(
            self._stats.items(),
            key=lambda x: x[1].play_count,
            reverse=True
        )[:limit]

    def most_skipped(self, limit: int = 10):
        return sorted(
            self._stats.items(),
            key=lambda x: x[1].skip_count,
            reverse=True
        )[:limit]

    def hottest_tracks(self, limit: int = 10):
        return sorted(
            self._stats.items(),
            key=lambda x: x[1].heat_score(),
            reverse=True
        )[:limit]

    # -----------------------------
    # Internal
    # -----------------------------

    def _ensure_track(self, track_id: str) -> None:
        if track_id not in self._stats:
            self._stats[track_id] = TrackStats()
