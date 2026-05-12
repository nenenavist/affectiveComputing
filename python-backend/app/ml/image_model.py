import base64
import binascii
import math
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.schemas import Emotion


ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "emotion_cnn.pth"

RAW_CLASSES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
CLASS_TO_APP_EMOTION: Dict[str, Emotion] = {
    "angry": "angry",
    "disgust": "angry",
    "fear": "neutral",
    "happy": "happy",
    "neutral": "neutral",
    "sad": "sad",
    "surprise": "happy",
}
EMOTION_ORDER: list[Emotion] = ["happy", "sad", "angry", "neutral"]
NEUTRAL_PRIOR: Dict[Emotion, float] = {
    "happy": 0.16,
    "sad": 0.16,
    "angry": 0.13,
    "neutral": 0.55,
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
        self.face_detector, self.cv2 = self._build_face_detector()

    @staticmethod
    def _build_face_detector():
        try:
            import cv2  # type: ignore

            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(cascade_path)
            if detector.empty():
                return None, None
            return detector, cv2
        except Exception:
            return None, None

    def _extract_face(self, image) -> Tuple[object, bool]:
        import numpy as np

        if self.face_detector is None or self.cv2 is None:
            return self._center_crop(image), False

        gray = np.asarray(image.convert("L"))
        min_side = min(gray.shape[0], gray.shape[1])
        min_size = max(30, min_side // 9)
        for neighbors in (4, 3, 2):
            faces = self.face_detector.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=neighbors,
                minSize=(min_size, min_size),
            )
            if len(faces) > 0:
                break

        if len(faces) == 0:
            return self._center_crop(image), False

        x, y, width, height = max(faces, key=lambda item: int(item[2]) * int(item[3]))
        pad = int(max(width, height) * 0.18)
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(image.width, x + width + pad)
        bottom = min(image.height, y + height + pad)
        return image.crop((left, top, right, bottom)), True

    @staticmethod
    def _center_crop(image):
        # For a typical selfie the face occupies the upper-center portion.
        w, h = image.width, image.height
        side = max(64, int(min(w, h) * 0.65))
        left = max(0, (w - side) // 2)
        top = max(0, int(h * 0.05))
        right = min(w, left + side)
        bottom = min(h, top + side)
        return image.crop((left, top, right, bottom))

    def _predict_probabilities(self, image_data_url: str) -> Optional[Dict[Emotion, float]]:
        import numpy as np
        from PIL import Image

        payload = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url

        try:
            image_bytes = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return None

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except OSError:
            return None

        face, has_face = self._extract_face(image)
        # Convert to grayscale WITHOUT histogram equalisation or autocontrast:
        # the CNN was trained on raw grayscale pixel values; modifying the
        # distribution beforehand degrades recognition quality.
        grayscale = face.convert("L").resize((144, 128), Image.LANCZOS)

        array = np.asarray(grayscale, dtype="float32") / 255.0
        image_std = float(np.std(array))
        # Two augmentations: original + horizontal mirror.  Brightness
        # variations were removed because they shift the distribution the
        # CNN was trained on.
        augmentations = [array, np.fliplr(array)]
        batch = self.torch.from_numpy(np.stack(augmentations, axis=0)).unsqueeze(1)

        with self.torch.no_grad():
            logits = self.model(batch)
            # Temperature 1.05 — barely any softening, preserves sharp peaks.
            probabilities = self.torch.softmax(logits / 1.05, dim=1).mean(dim=0)

        app_probabilities: Dict[Emotion, float] = {emotion: 0.0 for emotion in EMOTION_ORDER}
        for index, raw_class in enumerate(RAW_CLASSES):
            app_emotion = CLASS_TO_APP_EMOTION[raw_class]
            app_probabilities[app_emotion] += float(probabilities[index].item())

        total = sum(app_probabilities.values())
        if total <= 0:
            return None

        normalized = {
            emotion: app_probabilities[emotion] / total
            for emotion in EMOTION_ORDER
        }
        return self._calibrate_probabilities(normalized, has_face=has_face, image_std=image_std)

    @staticmethod
    def _calibrate_probabilities(
        probabilities: Dict[Emotion, float],
        *,
        has_face: bool,
        image_std: float,
    ) -> Dict[Emotion, float]:
        top_values = sorted(probabilities.values(), reverse=True)
        top = top_values[0]
        second = top_values[1] if len(top_values) > 1 else 0.0
        margin = top - second
        entropy = -sum(value * math.log(value + 1e-8) for value in probabilities.values()) / math.log(
            len(probabilities)
        )

        # Calibration: blend toward neutral prior only when the model is
        # genuinely uncertain.  Previous values (0.55 / 0.62) were far too
        # aggressive and crushed every image signal.
        blend_ratio = min(0.18, 0.03 + entropy * 0.13)
        if not has_face:
            blend_ratio = max(blend_ratio, 0.22)   # was 0.55 — the main bug
        if image_std < 0.07:
            blend_ratio = max(blend_ratio, 0.30)   # was 0.62
        if top < 0.30 and margin < 0.07:
            blend_ratio = max(blend_ratio, 0.24)

        blended = {
            emotion: probabilities[emotion] * (1.0 - blend_ratio)
            + NEUTRAL_PRIOR[emotion] * blend_ratio
            for emotion in EMOTION_ORDER
        }
        total = sum(blended.values()) or 1.0
        return {emotion: blended[emotion] / total for emotion in EMOTION_ORDER}

    def predict(self, image_data_url: str) -> Optional[Emotion]:
        probabilities = self._predict_probabilities(image_data_url)
        if not probabilities:
            return None
        return max(probabilities, key=probabilities.get)

    def predict_weights(self, image_data_url: str) -> Dict[Emotion, float]:
        probabilities = self._predict_probabilities(image_data_url)
        if not probabilities:
            return {emotion: 0.0 for emotion in EMOTION_ORDER}
        return {emotion: round(probabilities[emotion], 4) for emotion in EMOTION_ORDER}


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


def detect_image_emotion_weights(image: Optional[str]) -> Dict[Emotion, float]:
    if not image:
        return {emotion: 0.0 for emotion in EMOTION_ORDER}

    model = get_image_model()
    if not model:
        return {emotion: 0.0 for emotion in EMOTION_ORDER}

    return model.predict_weights(image)
