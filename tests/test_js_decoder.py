"""Runs decoder/test_decoder.js with node (skipped when node is absent; CI has it)."""

import shutil
import subprocess

import pytest

from lorawan_payload_codec import vectors


def test_js_decoder_matches_python_on_every_vector():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not on PATH; `make test-js` needs it")
    out = subprocess.run(
        [node, str(vectors.ROOT / "decoder" / "test_decoder.js")], capture_output=True, text=True
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert " 0 failed" in out.stdout
