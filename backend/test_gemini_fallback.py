"""
test_gemini_fallback.py — request timeout + 503 fallback in backend/gemini_client.py.

No API calls: fake clients stand in for google.genai.
Run directly: venv/bin/python backend/test_gemini_fallback.py
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GEMINI_API_KEY", "test-offline-key-dummy")

import config  # noqa: E402
from backend import gemini_client as gc  # noqa: E402

PRIMARY, FALLBACK = "primary-model", "fallback-model"


class Overloaded(Exception):
    code = 503

    def __str__(self):
        return "503 UNAVAILABLE. This model is currently experiencing high demand."


class FakeModels:
    """generate_content that fails with 503 for models in `down`, else answers."""

    def __init__(self, down=()):
        self.down = set(down)
        self.calls: list[str] = []
        self.other = "untouched"

    def generate_content(self, *, model, **kwargs):
        self.calls.append(model)
        if model in self.down:
            raise Overloaded()
        return SimpleNamespace(text=f"from {model}")


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _wrapper(down=(), after=2, cooldown=300.0):
    clock = Clock()
    models = FakeModels(down)
    breaker = gc._FallbackBreaker(after, cooldown, clock)
    return gc._ModelsWithFallback(models, PRIMARY, FALLBACK, breaker), models, clock


def _call(w, **kw):
    try:
        return w.generate_content(model=kw.pop("model", PRIMARY), contents="x", **kw)
    except Overloaded:
        return "503"


def test_is_unavailable():
    assert gc.is_unavailable(Overloaded())
    assert gc.is_unavailable(Exception("503 UNAVAILABLE. high demand"))
    assert not gc.is_unavailable(Exception("429 RESOURCE_EXHAUSTED"))
    assert not gc.is_unavailable(ValueError("empty response"))


def test_single_503_is_not_enough_to_switch():
    w, models, _ = _wrapper(down={PRIMARY})
    assert _call(w) == "503"          # first 503: surfaces to the retry policy
    assert models.calls == [PRIMARY]


def test_second_503_falls_back_in_the_same_call():
    w, models, _ = _wrapper(down={PRIMARY})
    assert _call(w) == "503"
    assert _call(w).text == f"from {FALLBACK}"   # 2nd consecutive 503 trips the breaker
    assert models.calls == [PRIMARY, PRIMARY, FALLBACK]


def test_open_breaker_skips_primary_then_recovers_after_cooldown():
    w, models, clock = _wrapper(down={PRIMARY}, cooldown=300)
    _call(w), _call(w)
    models.calls.clear()
    assert _call(w).text == f"from {FALLBACK}"
    assert models.calls == [FALLBACK]            # primary not even tried while open
    clock.t = 301
    models.down.clear()                          # primary is healthy again
    models.calls.clear()
    assert _call(w).text == f"from {PRIMARY}"
    assert models.calls == [PRIMARY]


def test_success_resets_the_failure_count():
    w, models, _ = _wrapper(down={PRIMARY})
    assert _call(w) == "503"
    models.down.clear()
    assert _call(w).text == f"from {PRIMARY}"    # success resets the streak
    models.down.add(PRIMARY)
    assert _call(w) == "503"                     # a lone 503 again does not switch
    assert FALLBACK not in models.calls


def test_non_503_errors_are_not_swallowed():
    class Boom(Exception):
        code = 400

    class M(FakeModels):
        def generate_content(self, *, model, **kw):
            self.calls.append(model)
            raise Boom("bad request")

    models = M()
    w = gc._ModelsWithFallback(models, PRIMARY, FALLBACK, gc._FallbackBreaker(2, 300, Clock()))
    for _ in range(3):
        try:
            w.generate_content(model=PRIMARY, contents="x")
            assert False, "should raise"
        except Boom:
            pass
    assert models.calls == [PRIMARY] * 3        # never rerouted


def test_other_models_and_cached_calls_pass_through():
    w, models, _ = _wrapper(down={PRIMARY, "other-model"})
    assert _call(w, model="other-model") == "503"                         # not the primary
    assert _call(w, config={"cached_content": "cachedContents/1"}) == "503"  # tied to a cache
    assert _call(w, config=SimpleNamespace(cached_content="cachedContents/1")) == "503"
    assert models.calls == ["other-model", PRIMARY, PRIMARY]


def test_other_attributes_delegate_to_the_sdk():
    w, models, _ = _wrapper()
    assert w.other == "untouched"


def test_get_client_sets_timeout_and_fallback():
    seen = {}

    class FakeClient:
        def __init__(self, api_key=None, http_options=None):
            seen["timeout_ms"] = http_options.timeout
            self.models = FakeModels()
            self.files = "files-api"

    orig_load, orig_primary = gc._load_genai, config.MODEL_NAME
    try:
        gc._load_genai = lambda: SimpleNamespace(Client=FakeClient)
        config.MODEL_NAME, config.FALLBACK_MODEL_NAME = "primary-x", "fallback-x"
        gc.reset_client()
        client = gc.get_client()
        assert seen["timeout_ms"] == int(config.GEMINI_REQUEST_TIMEOUT_SEC * 1000)
        assert isinstance(client.models, gc._ModelsWithFallback)
        assert client.files == "files-api"                 # rest of the SDK still reachable
        assert gc.get_client() is client                   # cached

        config.FALLBACK_MODEL_NAME = ""                    # fallback switched off: plain SDK models
        gc.reset_client()
        assert isinstance(gc.get_client().models, FakeModels)

        config.FALLBACK_MODEL_NAME = "primary-x"           # same as primary: nothing to fall back to
        gc.reset_client()
        assert isinstance(gc.get_client().models, FakeModels)
    finally:
        gc._load_genai, config.MODEL_NAME = orig_load, orig_primary
        config.FALLBACK_MODEL_NAME = "gemini-3.5-flash-lite"
        gc.reset_client()


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{'all passed' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
