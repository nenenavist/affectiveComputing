"""Fusion of text- and image-based emotion signals into final weights.

Public API (kept stable for the rest of the backend):
    detect_emotion(request)         -> dominant Emotion
    detect_emotion_weights(request) -> normalized EmotionWeights (sums ~1.0)

Adaptive fusion:
    * Each modality gets a confidence score from peak probability, top-1/top-2
      margin and entropy.
    * Confidence is turned into a reliability weight; the more reliable
      modality contributes more.  A clearly more reliable modality dominates.
    * Agreeing modalities reinforce each other; conflicting ones are blended by
      reliability (never a blind 50/50).
    * A neutral signal does not drown out a confident non-neutral one.
"""
import logging
import math
from typing import Tuple

from app.ml.image_model import detect_image_emotion_weights
from app.ml.text_model import detect_text_emotion_weights
from app.schemas import Emotion, EmotionWeights, MoodRequest


EMOTIONS: list[Emotion] = ["happy", "sad", "angry", "neutral"]
NEUTRAL_PRIOR: EmotionWeights = {"happy": 0.16, "sad": 0.16, "angry": 0.12, "neutral": 0.56}

# How sharply a reliability gap translates into a share gap. Higher → the more
# reliable modality dominates faster.
_SHARE_SHARPEN = 2.3
# Neutral is the "absence of signal" class: when a modality's dominant emotion
# is neutral, its reliability is discounted so it cannot mute a confident
# non-neutral reading from the other modality.
_NEUTRAL_RELIABILITY_DISCOUNT = 0.55

_logger = logging.getLogger(__name__)


def detect_emotion(request: MoodRequest) -> Emotion:
    weights = detect_emotion_weights(request)
    return max(weights, key=weights.get)


def detect_emotion_weights(request: MoodRequest) -> EmotionWeights:
    text_weights = detect_text_emotion_weights(request.text)
    image_weights = detect_image_emotion_weights(request.image)
    has_text_signal = bool(request.text.strip()) and sum(text_weights.values()) > 0
    has_image_signal = bool(request.image) and sum(image_weights.values()) > 0

    if has_text_signal and has_image_signal:
        return _fuse_modalities(text_weights, image_weights)

    if has_text_signal:
        return _stabilize_single_signal(text_weights)

    if has_image_signal:
        return _stabilize_single_signal(image_weights)

    return {"happy": 0.0, "sad": 0.0, "angry": 0.0, "neutral": 1.0}


def _normalize(weights: EmotionWeights) -> EmotionWeights:
    total = sum(max(value, 0.0) for value in weights.values())
    if total <= 0:
        return {"happy": 0.0, "sad": 0.0, "angry": 0.0, "neutral": 1.0}

    return {emotion: round(max(weights.get(emotion, 0.0), 0.0) / total, 4) for emotion in EMOTIONS}


def _signal_confidence(weights: EmotionWeights) -> float:
    """Confidence in [0.05, 0.95] from peak probability, margin and entropy."""
    normalized = _normalize(weights)
    values = [normalized[emotion] for emotion in EMOTIONS]
    sorted_values = sorted(values, reverse=True)
    peak = sorted_values[0]
    margin = sorted_values[0] - sorted_values[1]
    entropy = -sum(value * math.log(value + 1e-9) for value in values) / math.log(len(values))
    certainty = 1.0 - entropy
    confidence = 0.14 + peak * 0.46 + margin * 0.30 + certainty * 0.10
    return min(max(confidence, 0.05), 0.95)


def _modality_reliability(weights: EmotionWeights, *, other_is_confident_non_neutral: bool) -> float:
    """Reliability weight used to split contribution between modalities.

    Built on top of confidence, but a neutral-dominant signal is discounted so
    a confident non-neutral reading from the other modality wins.
    """
    confidence = _signal_confidence(weights)
    dominant = max(_normalize(weights), key=_normalize(weights).get)
    reliability = confidence
    if dominant == "neutral" and other_is_confident_non_neutral:
        reliability *= _NEUTRAL_RELIABILITY_DISCOUNT
    return max(reliability, 1e-4)


def _reliability_shares(text_reliability: float, image_reliability: float) -> Tuple[float, float]:
    text_sharp = text_reliability ** _SHARE_SHARPEN
    image_sharp = image_reliability ** _SHARE_SHARPEN
    total = text_sharp + image_sharp
    if total <= 0:
        return 0.5, 0.5
    return text_sharp / total, image_sharp / total


def _fuse_modalities(text_weights: EmotionWeights, image_weights: EmotionWeights) -> EmotionWeights:
    text_norm = _normalize(text_weights)
    image_norm = _normalize(image_weights)
    text_dominant = max(text_norm, key=text_norm.get)
    image_dominant = max(image_norm, key=image_norm.get)

    text_conf = _signal_confidence(text_norm)
    image_conf = _signal_confidence(image_norm)

    text_non_neutral_conf = text_dominant != "neutral" and text_conf >= 0.45
    image_non_neutral_conf = image_dominant != "neutral" and image_conf >= 0.45

    text_reliability = _modality_reliability(
        text_norm, other_is_confident_non_neutral=image_non_neutral_conf
    )
    image_reliability = _modality_reliability(
        image_norm, other_is_confident_non_neutral=text_non_neutral_conf
    )
    text_share, image_share = _reliability_shares(text_reliability, image_reliability)

    if text_dominant == image_dominant:
        fused = {
            e: text_norm[e] * text_share + image_norm[e] * image_share
            for e in EMOTIONS
        }
        # Agreement reinforcement scaled by how confident the weaker modality is.
        agreement_boost = min(0.14, 0.05 + min(text_conf, image_conf) * 0.14)
        fused[text_dominant] = min(fused[text_dominant] + agreement_boost, 0.97)
        result = _maybe_prior(fused, text_conf, image_conf)
    else:
        # Conflict: lift both to a common peak so neither wins just by being
        # peakier, then blend by reliability shares.
        target_peak = 0.74
        text_scaled = {e: text_norm[e] * (target_peak / max(text_norm[text_dominant], 1e-6)) for e in EMOTIONS}
        image_scaled = {e: image_norm[e] * (target_peak / max(image_norm[image_dominant], 1e-6)) for e in EMOTIONS}
        fused = {
            e: text_scaled[e] * text_share + image_scaled[e] * image_share
            for e in EMOTIONS
        }
        result = _maybe_prior(fused, text_conf, image_conf)

    _logger.info(
        "Fusion: text=%s(conf=%.2f) image=%s(conf=%.2f) shares=(%.2f/%.2f) -> %s",
        text_dominant, text_conf, image_dominant, image_conf,
        text_share, image_share, result,
    )
    return result


def _maybe_prior(fused: EmotionWeights, text_conf: float, image_conf: float) -> EmotionWeights:
    """Blend toward neutral prior only when BOTH modalities are weak."""
    if text_conf < 0.36 and image_conf < 0.36:
        return _blend_with_prior(fused, prior_share=0.18)
    return _normalize(fused)


def _blend_with_prior(weights: EmotionWeights, prior_share: float) -> EmotionWeights:
    share = min(max(prior_share, 0.0), 0.8)
    blended = {
        emotion: weights.get(emotion, 0.0) * (1.0 - share) + NEUTRAL_PRIOR[emotion] * share
        for emotion in EMOTIONS
    }
    return _normalize(blended)


def _stabilize_single_signal(weights: EmotionWeights) -> EmotionWeights:
    confidence = _signal_confidence(weights)
    if confidence >= 0.42:
        return _normalize(weights)

    prior_share = 0.14 + (0.42 - confidence) * 0.50
    return _blend_with_prior(weights, prior_share=prior_share)
