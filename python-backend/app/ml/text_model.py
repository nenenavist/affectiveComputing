import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from app.schemas import Emotion


TEXT_ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "text_sentiment.joblib"

KEYWORDS: Dict[Emotion, List[str]] = {
    "happy": [
        "happy",
        "great",
        "good",
        "excited",
        "joy",
        "love",
        "amazing",
        "calm",
        "рад",
        "счаст",
        "хорош",
        "люблю",
        "восторг",
        "спокой",
    ],
    "sad": [
        "sad",
        "tired",
        "lonely",
        "hurt",
        "cry",
        "bad",
        "down",
        "empty",
        "груст",
        "устал",
        "одинок",
        "плохо",
        "плак",
        "тоск",
    ],
    "angry": [
        "angry",
        "mad",
        "furious",
        "stress",
        "annoyed",
        "hate",
        "rage",
        "зл",
        "бесит",
        "стресс",
        "ненавиж",
        "ярость",
        "раздраж",
    ],
    "neutral": [
        "okay",
        "fine",
        "normal",
        "neutral",
        "usual",
        "average",
        "норм",
        "обычно",
        "нейтраль",
        "ровно",
    ],
}

SENTIMENT_TO_EMOTION: Dict[int, Emotion] = {
    -1: "sad",
    0: "neutral",
    1: "happy",
}


@lru_cache(maxsize=1)
def get_text_pipeline():
    if not TEXT_ARTIFACT_PATH.exists():
        return None

    try:
        import joblib

        return joblib.load(TEXT_ARTIFACT_PATH)
    except Exception:
        return None


def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[^\w\sа-яё]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_text_emotion(text: str) -> Optional[Emotion]:
    cleaned = clean_text(text)

    if not cleaned:
        return None

    pipeline = get_text_pipeline()
    if pipeline:
        try:
            prediction = int(pipeline.predict([cleaned])[0])
            return SENTIMENT_TO_EMOTION.get(prediction, "neutral")
        except Exception:
            pass

    scores = {
        emotion: sum(1 for keyword in keywords if keyword in cleaned)
        for emotion, keywords in KEYWORDS.items()
    }
    emotion, score = max(scores.items(), key=lambda item: item[1])

    return emotion if score > 0 else None
