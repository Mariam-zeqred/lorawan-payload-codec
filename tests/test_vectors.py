"""The committed vector files are what the C and JavaScript tests read, so they must match the
Python encoder exactly, and every vector must round-trip through Python."""

import json

from lorawan_payload_codec import frames, vectors
from lorawan_payload_codec.compact import Reading


def test_committed_vectors_are_fresh():
    built = vectors.build()
    assert vectors.JSON_OUT.read_text() == vectors.render_json(built), "run: make vectors"
    assert vectors.C_OUT.read_text() == vectors.render_c(built), "run: make vectors"


def test_vectors_round_trip_and_cover_the_edges():
    vs = json.loads(vectors.JSON_OUT.read_text())
    assert len(vs) == 35 + len(vectors.EDGE_CASES)
    for v in vs:
        r = Reading(**v["input"])
        for fmt in frames.FORMATS:
            fport, payload = frames.encode(r, fmt)
            assert payload.hex() == v[fmt]["hex"]
            assert frames.decode(fport, payload).as_dict() == v[fmt]["decoded"]
        # compact is exact to 0.01 degC; CayenneLPP temperature is rounded to 0.1 degC
        assert v["compact"]["decoded"]["temperature_c"] == round(r.temperature_c, 2)
        assert abs(v["cayenne"]["decoded"]["temperature_c"] - r.temperature_c) <= 0.05 + 1e-9
    assert any(v["input"]["door_open"] for v in vs)
    assert any(v["input"]["alarm_code"] == 31 for v in vs)
    assert any(v["input"]["temperature_c"] < 0 for v in vs)
