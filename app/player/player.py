# app/player/player.py
"""
Simple player loop that drives Analytics.

Design goals:
- Work with Track objects (from app.shuffle.models) but also accept raw dicts.
- Simulate playback using track.duration_ms (falls back to a default).
- Allow interactive commands:
    - 's' to skip current track
    - 'p' to pause/resume
    - 'q' to quit playback
- Record analytics: track_started and track_finished (completed flag)
- time_scale: speeds up playback for demos/tests (e.g 0.1 plays 10x faster)
player.py is a simulation harness that represents playback timing and user interactions 
for analytics and shuffle logic, not a streaming audio player.
"""

from __future__ import annotations
import threading
import time
from queue import SimpleQueue, Empty
from typing import Iterable, List, Optional

from app.shuffle.models import Track, normalize_tracks
from app.analytics import Analytics


# sensible default if a track lacks duration_ms (3 minutes)
_DEFAULT_DURATION_MS = 180_000


class PlayerCommand:
    SKIP = "skip"
    PAUSE = "pause"
    RESUME = "resume"
    QUIT = "quit"


class Player:
    """
    Lightweight player that simulates playback timing and forwards analytics events.

    Usage:
      p = Player(analytics=Analytics(), time_scale=0.1)
      p.play_playlist(tracks)  # blocks until done or quit
    """

    def __init__(self, analytics: Analytics, time_scale: float = 1.0):
        self.analytics = analytics
        self.time_scale = float(time_scale) if time_scale and time_scale > 0 else 1.0
        self._cmd_q: SimpleQueue[str] = SimpleQueue()
        self._running = False
        self._lock = threading.Lock()
        self._paused = False

    # -------------------------
    # public control API
    # -------------------------
    def play_playlist(self, items: Iterable[Track]):
        """
        Play a sequence of tracks. This method blocks until the playlist completes
        or the user quits (by sending a quit command).
        """
        tracks = self._ensure_tracks(items)
        self._running = True

        # start command-listening thread (reads from stdin)
        cmd_thr = threading.Thread(target=self._command_input_loop, daemon=True)
        cmd_thr.start()

        try:
            for t in tracks:
                if not self._running:
                    break
                cont = self._play_single_track(t)
                if not cont:  # user requested quit
                    break
        finally:
            self._running = False
            # drain queue
            while not self._cmd_q.empty():
                try:
                    self._cmd_q.get_nowait()
                except Exception:
                    break

    def send_command(self, cmd: str):
        """Programmatic command injection (useful for tests)."""
        self._cmd_q.put(cmd)

    def stop(self):
        self.send_command(PlayerCommand.QUIT)

    # -------------------------
    # internals
    # -------------------------
    def _ensure_tracks(self, items: Iterable[Track]) -> List[Track]:
        items = list(items)
        if not items:
            return []
        if isinstance(items[0], Track):
            return items[:]  # copy
        return normalize_tracks(items)

    def _play_single_track(self, track: Track) -> bool:
        """
        Simulate a single track playback.
        Returns True to continue to next track, False to stop (quit).
        """
        dur_ms = track.duration_ms if getattr(track, "duration_ms", None) else _DEFAULT_DURATION_MS
        # scaled down for demos/tests
        dur_secs = (dur_ms / 1000.0) * self.time_scale

        # start analytics
        self.analytics.track_started(track.id or track.uri or "(unknown)")

        print(f"▶ Now playing: {track.name} — {track.main_artist_name()}  [{int(dur_secs)}s demo]")
        start = time.time()
        elapsed = 0.0

        while elapsed < dur_secs:
            # check for commands every 0.2s
            try:
                cmd = self._cmd_q.get(timeout=0.2)
            except Empty:
                cmd = None

            if cmd is not None:
                if cmd == PlayerCommand.SKIP:
                    # treat as incomplete play
                    print("→ Skipped.")
                    self.analytics.track_finished(track.id or track.uri or "(unknown)", completed=False)
                    return True
                if cmd == PlayerCommand.PAUSE:
                    with self._lock:
                        self._paused = True
                    print("|| paused (press 'p' to resume)")
                elif cmd == PlayerCommand.RESUME:
                    with self._lock:
                        self._paused = False
                    print("▶ resumed")
                elif cmd == PlayerCommand.QUIT:
                    print("⏹ stopping playback.")
                    # record partial listening as incomplete
                    self.analytics.track_finished(track.id or track.uri or "(unknown)", completed=False)
                    return False  # signal stop

            # paused state
            if self._paused:
                time.sleep(0.2)
                # don't advance elapsed while paused
                start += 0.2
                elapsed = time.time() - start
                continue

            # sleep a little to be responsive
            time.sleep(0.2)
            elapsed = time.time() - start

        # finished normally
        print("✓ Completed:", track.name)
        self.analytics.track_finished(track.id or track.uri or "(unknown)", completed=True)
        return True

    def _command_input_loop(self):
        """
        Simple thread that waits for single-character commands on stdin and
        pushes corresponding internal commands into the queue.

        Intentionally basic, to-do: for a GUI wire buttons to send_command().
        """
        # Small prompt printed once
        print("Controls: [s]kip  [p]ause/resume  [q]uit")
        try:
            while self._running:
                # user types a single character + Enter
                v = input().strip().lower()
                if not v:
                    continue
                if v == "s":
                    self._cmd_q.put(PlayerCommand.SKIP)
                elif v == "p":
                    # toggle pause/resume depending on state
                    with self._lock:
                        if self._paused:
                            self._cmd_q.put(PlayerCommand.RESUME)
                        else:
                            self._cmd_q.put(PlayerCommand.PAUSE)
                elif v == "q":
                    self._cmd_q.put(PlayerCommand.QUIT)
                    break
                else:
                    print("Unknown command. Use s/p/q.")
        except Exception:
            # pass exceptions from stdin thread to keep main playback robust
            pass
