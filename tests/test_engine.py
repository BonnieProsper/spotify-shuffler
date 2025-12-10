# tests/test_engine.py
from app.shuffle.engine import ShuffleEngine
from app.shuffle.models import Track

SAMPLE_TRACKS = [
    Track(id="t1", uri="u1", name="One", artists=[{"id": "a1", "name": "Artist A"}], popularity=30),
    Track(id="t2", uri="u2", name="Two", artists=[{"id": "a2", "name": "Artist B"}], popularity=40),
    Track(id="t3", uri="u3", name="Three", artists=[{"id": "a1", "name": "Artist A"}], popularity=20),
    Track(id="t4", uri="u4", name="Four", artists=[{"id": "a3", "name": "Artist C"}], popularity=10),
    Track(id="t5", uri="u5", name="Five", artists=[{"id": "a2", "name": "Artist B"}], popularity=50),
]


def test_fisher_yates_preserves_items():
    e = ShuffleEngine(rng_seed=1)
    out = e.run(SAMPLE_TRACKS)
    assert len(out) == len(SAMPLE_TRACKS)
    assert set(t.id for t in out) == set(t.id for t in SAMPLE_TRACKS)


def test_artist_gap_respected():
    # create a list with repeated artist a1 many times
    tracks = [
        Track(id=f"t{i}", uri=f"u{i}", name=f"t{i}", artists=[{"id": "A", "name": "A"}])
        if i % 2 == 0
        else Track(id=f"t{i}", uri=f"u{i}", name=f"t{i}", artists=[{"id": f"B{i}", "name": f"B{i}"}])
        for i in range(10)
    ]
    e = ShuffleEngine(min_artist_gap=3, rng_seed=42)
    out = e.run(tracks)
    # check distance between consecutive A artist placements
    positions = [i for i, t in enumerate(out) if (t.artists and t.artists[0].get("id") == "A")]
    # each consecutive difference must be >= 3
    for a, b in zip(positions, positions[1:]):
        assert (b - a) >= 3
