"""
local_embedding.py — on-box embeddings for the tutor index (EmbeddingGemma 300M, 4-bit ONNX).

Why local: the free Gemini embedding tier allows 100 requests/min plus a daily
cap, and a lecture needs ~3.5 index docs per minute of video (a 52-min lecture
is ~180), so indexing was the first thing to run out. On this model a lecture
costs CPU instead: ~0.45 s per doc on one core, no quota, no 429 waits.

Measured on the tutor/evals question sets (transcript window hit@4, hybrid
retrieval): English .83 vs .85 for gemini-embedding-2, romanized Hinglish
.79 vs .87. See docs/PROJECT_PROGRESS.md ("Local embeddings").

Prompt formats (EmbeddingGemma model card):
    Documents:  "title: none | text: {content}"
    Queries:    "task: search result | query: {content}"

The model files (~210 MB) download once into NORAI_EMBED_MODEL_DIR (default
.models/ at the repo root). The Docker image fetches them at build time:
    python -m tutor.local_embedding --download
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy as np

LOCAL_MODEL = "embeddinggemma-300m-q4"
LOCAL_DIMS = 768
_REPO = "onnx-community/embeddinggemma-300m-ONNX"
_REVISION = "5090578d9565bb06545b4552f76e6bc2c93e4a66"
_FILES = ("onnx/model_q4.onnx", "onnx/model_q4.onnx_data", "tokenizer.json")
_MAX_TOKENS = 512   # index docs are ~150 tokens; note sections stay well under this
_BATCH = 16
_PREFIX = {"document": "title: none | text: ", "query": "task: search result | query: "}

_lock = threading.Lock()
_model: tuple | None = None  # (onnxruntime.InferenceSession, tokenizers.Tokenizer)


def model_dir() -> Path:
    default = Path(__file__).resolve().parent.parent / ".models"
    return Path(os.environ.get("NORAI_EMBED_MODEL_DIR", default)) / LOCAL_MODEL


def download() -> Path:
    """Fetch the model files if missing (idempotent). Returns the model dir."""
    from huggingface_hub import hf_hub_download

    root = model_dir()
    for name in _FILES:
        if not (root / name).is_file():
            hf_hub_download(_REPO, name, revision=_REVISION, local_dir=root)
    return root


def _load():
    """One session per process, shared by indexing and queries."""
    global _model
    with _lock:
        if _model is None:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            root = download()
            opts = ort.SessionOptions()
            # One thread by default: on the 1-vCPU box the index build shares
            # the core with uvicorn (NORAI_EMBED_THREADS to override).
            opts.intra_op_num_threads = int(os.environ.get("NORAI_EMBED_THREADS", "1"))
            opts.inter_op_num_threads = 1
            session = ort.InferenceSession(str(root / "onnx/model_q4.onnx"), opts,
                                           providers=["CPUExecutionProvider"])
            tok = Tokenizer.from_file(str(root / "tokenizer.json"))
            tok.enable_truncation(_MAX_TOKENS)
            tok.enable_padding(pad_id=tok.token_to_id("<pad>"), pad_token="<pad>")
            _model = (session, tok)
        return _model


class LocalEmbeddingFunction:
    """list[str] -> L2-normalised 768-d vectors, same call shape as
    GeminiEmbeddingFunction (role "document" for indexing, "query" for retrieval)."""

    model = LOCAL_MODEL
    dims = LOCAL_DIMS

    def __init__(self, role: str = "document") -> None:
        if role not in _PREFIX:
            raise ValueError(f"role must be 'document' or 'query', got {role!r}")
        self._prefix = _PREFIX[role]

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        session, tok = _load()
        texts = [self._prefix + t for t in input]
        # Batch similar lengths together so padding stays small.
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = np.zeros((len(texts), LOCAL_DIMS), dtype=np.float32)
        for b in range(0, len(order), _BATCH):
            idx = order[b:b + _BATCH]
            enc = tok.encode_batch([texts[i] for i in idx])
            feed = {
                "input_ids": np.asarray([e.ids for e in enc], dtype=np.int64),
                "attention_mask": np.asarray([e.attention_mask for e in enc], dtype=np.int64),
            }
            out[idx] = session.run(["sentence_embedding"], feed)[0]
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (out / norms).tolist()


if __name__ == "__main__":
    import sys

    if "--download" in sys.argv:
        print(download())
    else:
        print("Usage: python -m tutor.local_embedding --download")
