import base64
import binascii
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

from app.models import Emotion


ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "emotion_cnn.pth"

RAW_CLASSES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
CLASS_TO_APP_EMOTION: Dict[str, Emotion] = {
    "angry": "angry",
    "disgust": "angry",
    "fear": "neutral",
    "happy": "happy",
    "neutral": "neutral",
    "sad": "sad",
    "surprise": "happy",
}


class ImageEmotionModel:
    def __init__(self) -> None:
        import torch
        from torch import nn
        import torch.nn.functional as functional

        class EmotionCNN(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.conv1 = nn.Conv2d(1, 16, 3)
                self.conv2 = nn.Conv2d(16, 32, 3)
                self.conv3 = nn.Conv2d(32, 64, 3)
                self.pool = nn.MaxPool2d(2, 2)
                self.dropout = nn.Dropout(0.5)
                self.fc1 = nn.Linear(14336, 128)
                self.fc2 = nn.Linear(128, 7)

            def forward(self, x):  # type: ignore[no-untyped-def]
                x = self.pool(functional.relu(self.conv1(x)))
                x = self.pool(functional.relu(self.conv2(x)))
                x = self.pool(functional.relu(self.conv3(x)))
                x = torch.flatten(x, 1)
                x = self.dropout(functional.relu(self.fc1(x)))
                return self.fc2(x)

        self.torch = torch
        self.model = EmotionCNN()
        state = torch.load(ARTIFACT_PATH, map_location="cpu")
        self.model.load_state_dict(state)
        self.model.eval()

    def predict(self, image_data_url: str) -> Optional[Emotion]:
        import numpy as np
        from PIL import Image

        payload = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url

        try:
            image_bytes = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return None

        try:
            image = Image.open(BytesIO(image_bytes)).convert("L").resize((144, 128))
        except OSError:
            return None

        array = np.asarray(image, dtype="float32") / 255.0
        tensor = self.torch.from_numpy(array).unsqueeze(0).unsqueeze(0)

        with self.torch.no_grad():
            logits = self.model(tensor)
            class_index = int(self.torch.argmax(logits, dim=1).item())

        raw_class = RAW_CLASSES[class_index]
        return CLASS_TO_APP_EMOTION[raw_class]


@lru_cache(maxsize=1)
def get_image_model() -> Optional[ImageEmotionModel]:
    if not ARTIFACT_PATH.exists():
        return None

    try:
        return ImageEmotionModel()
    except Exception:
        return None


def detect_image_emotion(image: Optional[str]) -> Optional[Emotion]:
    if not image:
        return None

    model = get_image_model()
    if not model:
        return None

    return model.predict(image)
