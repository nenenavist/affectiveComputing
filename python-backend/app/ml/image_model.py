"""Image emotion recognition powered by a pretrained Vision Transformer.

We use `dima806/facial_emotions_image_detection` — a ViT model fine-tuned
on FER+ (and several other facial-emotion datasets), reaching ~91 % accuracy
on FER+ vs the ~75 % we got with our custom CNN.  It handles real-world
selfies (varied lighting, color, angle) MUCH better than the small CNN
trained on 48×48 grayscale FER-2013 images.

First-time model download is ~88 MB and is cached under
~/.cache/huggingface/.  Subsequent runs are instant.
"""
from __future__ import annotations

import base64
import binascii
import logging
import math
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.schemas import Emotion


HF_MODEL_ID = "dima806/facial_emotions_image_detection"

# The HF model uses these label IDs.  We map them to our 4-class app
# emotion taxonomy.
HF_LABEL_TO_APP: Dict[str, Emotion] = {
    "angry": "angry",
    "anger": "angry",
    "disgust": "angry",
    "fear": "neutral",
    "happy": "happy",
    "happiness": "happy",
    "sad": "sad",
    "sadness": "sad",
    "surprise": "happy",  # surprise reads as positive
    "neutral": "neutral",
    "contempt": "angry",
}

EMOTION_ORDER: List[Emotion] = ["happy", "sad", "angry", "neutral"]
NEUTRAL_PRIOR: Dict[Emotion, float] = {
    "happy": 0.18,
    "sad": 0.18,
    "angry": 0.14,
    "neutral": 0.50,
}

# Fallback weights to the legacy CNN (artifacts/emotion_cnn.pth) if the HF
# model cannot be loaded for any reason.
LEGACY_ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "emotion_cnn.pth"

_logger = logging.getLogger(__name__)


class ImageEmotionModel:
    def __init__(self) -> None:
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        self.torch = torch

        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        _logger.info("Loading HuggingFace image model %s on %s …", HF_MODEL_ID, self.device)
        self.processor = AutoImageProcessor.from_pretrained(HF_MODEL_ID)
        self.model = AutoModelForImageClassification.from_pretrained(HF_MODEL_ID)
        self.model.eval()
        self.model.to(self.device)

        self.id2label: Dict[int, str] = {
            int(idx): str(label).lower().strip()
            for idx, label in self.model.config.id2label.items()
        }

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
        pad = int(max(width, height) * 0.20)
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(image.width, x + width + pad)
        bottom = min(image.height, y + height + pad)
        return image.crop((left, top, right, bottom)), True

    @staticmethod
    def _center_crop(image):
        w, h = image.width, image.height
        side = max(64, int(min(w, h) * 0.7))
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
        face_array = np.asarray(face, dtype="uint8")
        image_std = float(np.std(face_array.astype("float32") / 255.0))

        # Test-time augmentation: original + horizontal mirror.
        images_for_batch = [face, face.transpose(Image.FLIP_LEFT_RIGHT)]

        try:
            inputs = self.processor(images=images_for_batch, return_tensors="pt")
        except Exception as error:
            _logger.warning("Image processor failed: %s", error)
            return None

        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with self.torch.no_grad():
            logits = self.model(**inputs).logits
            probabilities = self.torch.softmax(logits, dim=1).mean(dim=0).detach().cpu().numpy()

        app_probabilities: Dict[Emotion, float] = {e: 0.0 for e in EMOTION_ORDER}
        for raw_index, probability in enumerate(probabilities):
            raw_label = self.id2label.get(raw_index)
            app_emotion = HF_LABEL_TO_APP.get(raw_label) if raw_label else None
            if not app_emotion:
                continue
            app_probabilities[app_emotion] += float(probability)

        total = sum(app_probabilities.values())
        if total <= 0:
            return None

        normalized = {e: app_probabilities[e] / total for e in EMOTION_ORDER}
        return self._calibrate_probabilities(
            normalized, has_face=has_face, image_std=image_std
        )

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
        entropy = (
            -sum(value * math.log(value + 1e-8) for value in probabilities.values())
            / math.log(len(probabilities))
        )

        # ViT predictions are typically much sharper than CNN.  We blend toward
        # neutral ONLY when the model is genuinely uncertain or no face was
        # detected.  Numbers chosen to preserve strong predictions.
        blend_ratio = min(0.10, 0.02 + entropy * 0.08)
        if not has_face:
            blend_ratio = max(blend_ratio, 0.30)
        if image_std < 0.06:
            blend_ratio = max(blend_ratio, 0.35)
        if top < 0.32 and margin < 0.06:
            blend_ratio = max(blend_ratio, 0.18)

        blended = {
            emotion: probabilities[emotion] * (1.0 - blend_ratio)
            + NEUTRAL_PRIOR[emotion] * blend_ratio
            for emotion in EMOTION_ORDER
        }
        total = sum(blended.values()) or 1.0
        return {e: blended[e] / total for e in EMOTION_ORDER}

    def predict(self, image_data_url: str) -> Optional[Emotion]:
        probabilities = self._predict_probabilities(image_data_url)
        if not probabilities:
            return None
        return max(probabilities, key=probabilities.get)

    def predict_weights(self, image_data_url: str) -> Dict[Emotion, float]:
        probabilities = self._predict_probabilities(image_data_url)
        if not probabilities:
            return {emotion: 0.0 for emotion in EMOTION_ORDER}
        return {e: round(probabilities[e], 4) for e in EMOTION_ORDER}


@lru_cache(maxsize=1)
def get_image_model() -> Optional[ImageEmotionModel]:
    try:
        return ImageEmotionModel()
    except Exception as error:
        _logger.warning(
            "Could not load HuggingFace image model (%s). "
            "Image emotion detection will be disabled.",
            error,
        )
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
