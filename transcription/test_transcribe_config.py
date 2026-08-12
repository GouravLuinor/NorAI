"""
test_transcribe_config.py — Unit tests for whisper model config (ROADMAP P1.7).

The default transcription model is now "small" (was "base"), driven by the
NORAI_WHISPER_MODEL env var, and models are cached per size. The module reads
the env var at import time, so each check runs in a subprocess with an isolated
environment. Run:
    python transcription/test_transcribe_config.py
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = str(Path(__file__).parent.parent)


def _import_transcribe(extra_env=None):
    env = dict(os.environ)
    env.pop("NORAI_WHISPER_MODEL", None)
    env.pop("NORAI_WHISPER_VAD_FILTER", None)
    env.pop("NORAI_WHISPER_BEAM_SIZE", None)
    if extra_env:
        env.update(extra_env)
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import transcription.transcribe as t\n"
        "print(t.DEFAULT_MODEL_SIZE)\n"
        "print(len(t._MODEL_CACHE))\n"
        "print(t.DEFAULT_VAD_FILTER)\n"
        "print(t.DEFAULT_BEAM_SIZE)\n"
    ) % ROOT
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env
    )


def test_default_model_is_small():
    r = _import_transcribe()
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == "small", f"default model expected 'small', got {lines[0]!r}"
    assert lines[1] == "0", "model cache should start empty"
    assert lines[2] == "True", f"VAD filter should default on, got {lines[2]!r}"
    assert lines[3] == "1", f"beam_size should default to 1, got {lines[3]!r}"
    print("PASS test_default_model_is_small")


def test_env_override_takes_effect():
    r = _import_transcribe(
        {"NORAI_WHISPER_MODEL": "tiny", "NORAI_WHISPER_VAD_FILTER": "false",
         "NORAI_WHISPER_BEAM_SIZE": "3"}
    )
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == "tiny"
    assert lines[2] == "False", "VAD override should apply"
    assert lines[3] == "3", "beam_size override should apply"
    print("PASS test_env_override_takes_effect")


if __name__ == "__main__":
    test_default_model_is_small()
    test_env_override_takes_effect()
    print("\nAll tests passed.")
