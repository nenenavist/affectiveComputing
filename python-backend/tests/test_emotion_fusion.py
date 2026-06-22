"""Unit tests for adaptive text+image emotion fusion."""

import math

from app.ml.emotion_service import _fuse_modalities, _normalize


def _peaked(emotion, peak):
    """Build a weight dict with `peak` mass on `emotion`, rest spread evenly."""
    others = [e for e in ("happy", "sad", "angry", "neutral") if e != emotion]
    rest = (1.0 - peak) / len(others)
    weights = {e: rest for e in others}
    weights[emotion] = peak
    return weights


def _sums_to_one(weights):
    return math.isclose(sum(weights.values()), 1.0, abs_tol=0.01)


def test_image_more_confident_than_text_dominates():
    # Image very confident "happy", text weakly "sad".
    text = _peaked("sad", 0.34)
    image = _peaked("happy", 0.88)
    fused = _fuse_modalities(text, image)
    assert _sums_to_one(fused)
    assert max(fused, key=fused.get) == "happy"
    assert fused["happy"] > fused["sad"]


def test_text_more_confident_than_image_dominates():
    text = _peaked("angry", 0.9)
    image = _peaked("happy", 0.33)
    fused = _fuse_modalities(text, image)
    assert _sums_to_one(fused)
    assert max(fused, key=fused.get) == "angry"
    assert fused["angry"] > fused["happy"]


def test_matching_emotions_reinforce():
    text = _peaked("sad", 0.7)
    image = _peaked("sad", 0.65)
    fused = _fuse_modalities(text, image)
    assert _sums_to_one(fused)
    assert max(fused, key=fused.get) == "sad"
    # Agreement should push the shared emotion at least as high as either input.
    assert fused["sad"] >= max(text["sad"], image["sad"]) - 0.01


def test_neutral_does_not_silence_confident_non_neutral():
    # Text confidently "angry", image is neutral-ish.
    text = _peaked("angry", 0.82)
    image = _peaked("neutral", 0.6)
    fused = _fuse_modalities(text, image)
    assert _sums_to_one(fused)
    assert max(fused, key=fused.get) == "angry"
    assert fused["angry"] > fused["neutral"]


def test_normalize_sums_to_one():
    weights = {"happy": 2.0, "sad": 1.0, "angry": 1.0, "neutral": 0.0}
    normalized = _normalize(weights)
    assert _sums_to_one(normalized)
    assert math.isclose(normalized["happy"], 0.5, abs_tol=0.01)
