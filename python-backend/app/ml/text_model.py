import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from app.schemas import Emotion


TEXT_ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "text_sentiment.joblib"
EMOTION_ORDER: List[Emotion] = ["happy", "sad", "angry", "neutral"]

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


class TextEmotionNet:
    def __init__(self) -> None:
        import torch
        from torch import nn

        self.torch = torch
        self.model = nn.Sequential(
            nn.Linear(4, 8),
            nn.ReLU(),
            nn.Linear(8, 4),
        )
        self._train()
        self.model.eval()

    def _train(self) -> None:
        import torch
        from torch import nn

        training_rows = [
            ([1.0, 0.0, 0.0, 0.0], 0),
            ([0.8, 0.0, 0.0, 0.2], 0),
            ([0.0, 1.0, 0.0, 0.0], 1),
            ([0.0, 0.8, 0.0, 0.2], 1),
            ([0.0, 0.0, 1.0, 0.0], 2),
            ([0.0, 0.0, 0.8, 0.2], 2),
            ([0.0, 0.0, 0.0, 1.0], 3),
            ([0.1, 0.1, 0.0, 0.8], 3),
        ]
        x = torch.tensor([row[0] for row in training_rows], dtype=torch.float32)
        y = torch.tensor([row[1] for row in training_rows], dtype=torch.long)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.05)
        criterion = nn.CrossEntropyLoss()

        for _ in range(160):
            optimizer.zero_grad()
            loss = criterion(self.model(x), y)
            loss.backward()
            optimizer.step()

    def predict(self, features: List[float]) -> Optional[Emotion]:
        if max(features) <= 0:
            return None

        tensor = self.torch.tensor([features], dtype=self.torch.float32)
        with self.torch.no_grad():
            probabilities = self.torch.softmax(self.model(tensor), dim=1)[0]
            score, index = self.torch.max(probabilities, dim=0)

        return EMOTION_ORDER[int(index.item())] if float(score.item()) >= 0.45 else None


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


def extract_text_features(cleaned: str) -> List[float]:
    scores = [
        sum(1 for keyword in KEYWORDS[emotion] if keyword in cleaned)
        for emotion in EMOTION_ORDER
    ]
    total = sum(scores)
    return [score / total for score in scores] if total else [0.0, 0.0, 0.0, 0.0]


@lru_cache(maxsize=1)
def get_text_emotion_model() -> TextEmotionNet:
    return TextEmotionNet()


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

    return get_text_emotion_model().predict(extract_text_features(cleaned))
