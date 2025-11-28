# src/shuffler/tests/test_shuffle.py
from shuffler.shuffle_engine import fisher_yates, anti_repeat_shuffle

def test_fy_preserves_items():
    a = list(range(100))
    out = fisher_yates(a)
    assert set(out) == set(a)
    assert len(out) == len(a)

def test_anti_repeat_artist():
    tracks = []
    for i in range(10):
        tracks.append({"name": f"t{i}", "artists":[{"id":"same"}] if i%2==0 else [{"id":f"a{i}"}]})
    out = anti_repeat_shuffle(tracks, repeat_window=1)
    # check no adjacent same artist
    for i in range(len(out)-1):
        a1 = out[i]["artists"][0]["id"]
        a2 = out[i+1]["artists"][0]["id"]
        assert a1 != a2 or (a1 == a2 and a1 != "same")

