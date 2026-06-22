import math

from app.ml.image_model import detect_image_emotion_weights
from app.ml.text_model import detect_text_emotion_weights
from app.schemas import Emotion, EmotionWeights, MoodRequest


EMOTIONS: list[Emotion] = ["happy", "sad", "angry", "neutral"]
NEUTRAL_PRIOR: EmotionWeights = {"happy": 0.16, "sad": 0.16, "angry": 0.12, "neutral": 0.56}


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


def _fuse_modalities(text_weights: EmotionWeights, image_weights: EmotionWeights) -> EmotionWeights:
    """Fuse text and image signals with conflict awareness."""
    text_dominant = max(text_weights, key=text_weights.get)
    image_dominant = max(image_weights, key=image_weights.get)
    text_conf = _signal_confidence(text_weights)
    image_conf = _signal_confidence(image_weights)
    total_conf = text_conf + image_conf or 1.0

    if text_dominant == image_dominant:
        text_share = text_conf / total_conf
        image_share = 1.0 - text_share
        fused = {
            e: text_weights[e] * text_share + image_weights[e] * image_share
            for e in EMOTIONS
        }
        fused[text_dominant] = min(fused[text_dominant] + 0.10, 0.97)
        if text_conf < 0.38 and image_conf < 0.38:
            return _blend_with_prior(fused, prior_share=0.18)
        return _normalize(fused)

    if text_dominant != "neutral" and image_dominant == "neutral":
        # Explicit text ("мне грустно") beats a blank/neutral-looking face.
        text_share = 0.78
        if text_conf >= 0.58:
            text_share = 0.86
        elif image_conf > text_conf + 0.20:
            text_share = 0.66
        image_share = 1.0 - text_share
        return _normalize({
            e: text_weights[e] * text_share + image_weights[e] * image_share
            for e in EMOTIONS
        })

    if text_dominant == "neutral" and image_dominant != "neutral":
        image_share = 0.70
        if image_conf >= 0.58:
            image_share = 0.80
        elif text_conf > image_conf + 0.20:
            image_share = 0.55
        text_share = 1.0 - image_share
        return _normalize({
            e: text_weights[e] * text_share + image_weights[e] * image_share
            for e in EMOTIONS
        })

    # Conflict branch: scale both peaks to the same reference, then blend.
    TARGET_PEAK = 0.74
    text_peak = max(text_weights[text_dominant], 1e-6)
    image_peak = max(image_weights[image_dominant], 1e-6)

    text_scaled = {e: text_weights[e] * (TARGET_PEAK / text_peak) for e in EMOTIONS}
    image_scaled = {e: image_weights[e] * (TARGET_PEAK / image_peak) for e in EMOTIONS}

    conf_ratio = text_conf / total_conf
    text_share = 0.5 + (conf_ratio - 0.5) * 0.20   # range ≈ 0.40–0.60
    image_share = 1.0 - text_share

    fused = {
        e: text_scaled[e] * text_share + image_scaled[e] * image_share
        for e in EMOTIONS
    }

    if text_conf < 0.35 and image_conf < 0.35:
        return _blend_with_prior(fused, prior_share=0.16)

    return _normalize(fused)


def _signal_confidence(weights: EmotionWeights) -> float:
    normalized = _normalize(weights)
    values = [normalized[emotion] for emotion in EMOTIONS]
    peak = max(values)
    sorted_values = sorted(values, reverse=True)
    margin = peak - sorted_values[1]
    entropy = -sum(value * math.log(value + 1e-9) for value in values) / math.log(len(values))
    certainty = 1.0 - entropy
    confidence = 0.16 + peak * 0.48 + margin * 0.28 + certainty * 0.08
    return min(max(confidence, 0.05), 0.95)


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
