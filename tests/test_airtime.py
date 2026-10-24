"""The vendored airtime formula must still match The Things Network's published figures for a
10-byte payload at 125 kHz (same checks as in lora-link-budget)."""

import pytest

from lorawan_payload_codec.airtime import airtime


@pytest.mark.parametrize(
    ("sf", "expected_ms"),
    [(7, 61.696), (8, 113.152), (9, 205.824), (10, 370.688), (11, 823.296), (12, 1482.752)],
)
def test_ttn_reference_10_bytes(sf, expected_ms):
    assert airtime(10, sf, 125_000).total_ms == pytest.approx(expected_ms, abs=1e-6)


def test_node_frame_sizes():
    # the README table: 5-byte compact and 17-byte CayenneLPP frames at SF7 and SF12
    assert airtime(5, 7).total_ms == pytest.approx(51.456)
    assert airtime(17, 7).total_ms == pytest.approx(71.936)
    assert airtime(5, 12).total_ms == pytest.approx(1318.912)
    assert airtime(17, 12).total_ms == pytest.approx(1646.592)
