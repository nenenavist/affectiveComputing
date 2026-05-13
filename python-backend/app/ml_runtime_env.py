"""Runtime toggles for ML (memory-constrained hosts, e.g. Railway ~512 MB).

Kept outside ``app.ml`` so importing flags does not execute ``app.ml``'s package
``__init__`` (which pulls emotion helpers) at app startup.
"""

from __future__ import annotations

import os


def _truthy(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def lightweight_ml() -> bool:
    """If true, skip heavy HF models (sentence-transformers + image ViT)."""
    return _truthy(os.getenv("LIGHTWEIGHT_ML"))


def skip_sentence_transformer() -> bool:
    """Skip MiniLM + joblib head; text mood uses TF-IDF + keywords only."""
    return lightweight_ml() or _truthy(os.getenv("SKIP_SENTENCE_TRANSFORMER"))


def skip_image_emotion_model() -> bool:
    """Skip HuggingFace ViT; image mood is disabled (neutral weights)."""
    return lightweight_ml() or _truthy(os.getenv("SKIP_IMAGE_EMOTION_MODEL"))
