"""Camera image emotion recognition.

Default runtime uses the local FER-2013 CNN artifact trained by
``app.ml.train_image_model``.  Set ``IMAGE_EMOTION_BACKEND=hf`` to use the
optional Hugging Face ViT backend instead.
"""
from __future__ import annotations

import base64
import binascii
import logging
import math
import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.ml.emotion_cnn import FER_RAW_CLASSES, FER_TO_APP, EmotionCNN
from app.ml_runtime_env import skip_image_emotion_model
from app.schemas import Emotion


HF_MODEL_ID = "dima806/facial_emotions_image_detection"
CNN_ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "emotion_cnn.pth"
CNN_INPUT_H = 48
CNN_INPUT_W = 48

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
CNN_RAW_CLASSES = FER_RAW_CLASSES
CNN_LABEL_TO_APP: Dict[str, Emotion] = FER_TO_APP  # type: ignore[assignment]
NEUTRAL_PRIOR: Dict[Emotion, float] = {
    "happy": 0.18,
    "sad": 0.18,
    "angry": 0.14,
    "neutral": 0.50,
}

_logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> bool:
    raw = os.getenv(name)
    return bool(raw and raw.strip().lower() in {"1", "true", "yes", "on"})


def _decode_image(image_data_url: str):
    """Decode a base64 data URL (or bare base64) into an RGB PIL image.

    Returns None on malformed input so callers can degrade gracefully.
    """
    from PIL import Image

    payload = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url
    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        return Image.open(BytesIO(image_bytes)).convert("RGB")
    except OSError:
        return None


def _enhance_face(image):
    """Normalize lighting/contrast so webcam frames look closer to training data.

    Autocontrast stretches the histogram (robust to dim/overexposed selfies);
    a small cutoff ignores extreme pixels. Falls back to the input on error.
    """
    try:
        from PIL import ImageOps

        return ImageOps.autocontrast(image, cutoff=2)
    except Exception:
        return image


def _log_image_prediction(backend: str, has_face: bool, weights: Dict[Emotion, float]) -> None:
    ordered = sorted(weights.items(), key=lambda item: item[1], reverse=True)
    top_emotion, top_value = ordered[0]
    second_value = ordered[1][1] if len(ordered) > 1 else 0.0
    _logger.info(
        "Image[%s]: face=%s top=%s(%.2f) margin=%.2f weights=%s",
        backend, has_face, top_emotion, top_value, top_value - second_value, weights,
    )


def _select_torch_device(torch):
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _build_cnn_model():
    return EmotionCNN(num_classes=7)


class ImageEmotionModel:
    def __init__(self) -> None:
        import torch

        self.torch = torch
        self.device = _select_torch_device(torch)

        _logger.info("Loading HuggingFace image model %s on %s …", HF_MODEL_ID, self.device)
        allow_download = _truthy_env("ALLOW_HF_DOWNLOAD")
        previous_offline = os.environ.get("HF_HUB_OFFLINE")
        hf_constants = None
        previous_hf_hub_offline = None
        try:
            from huggingface_hub import constants as hf_constants

            previous_hf_hub_offline = hf_constants.HF_HUB_OFFLINE
        except Exception:
            pass
        if not allow_download:
            os.environ["HF_HUB_OFFLINE"] = "1"
            if hf_constants is not None:
                hf_constants.HF_HUB_OFFLINE = True
        try:
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            self.processor = AutoImageProcessor.from_pretrained(
                HF_MODEL_ID,
                local_files_only=not allow_download,
            )
            self.model = AutoModelForImageClassification.from_pretrained(
                HF_MODEL_ID,
                local_files_only=not allow_download,
            )
        finally:
            if not allow_download:
                if previous_offline is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = previous_offline
                if hf_constants is not None and previous_hf_hub_offline is not None:
                    hf_constants.HF_HUB_OFFLINE = previous_hf_hub_offline
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

        image = _decode_image(image_data_url)
        if image is None:
            return None

        face, has_face = self._extract_face(image)
        face = _enhance_face(face)
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
        calibrated = self._calibrate_probabilities(
            normalized, has_face=has_face, image_std=image_std
        )
        _log_image_prediction("hf", has_face, calibrated)
        return calibrated

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

        # Blend toward neutral only for genuinely weak/low-information frames.
        # Haar detection often misses webcam faces, so missing `has_face` must
        # not flatten clear sad/angry predictions into neutral.
        blend_ratio = min(0.08, 0.02 + entropy * 0.06)
        if top >= 0.55 and margin >= 0.12:
            blend_ratio *= 0.35
        if not has_face:
            blend_ratio = max(blend_ratio, 0.10 if top >= 0.45 else 0.14)
        if image_std < 0.06:
            blend_ratio = max(blend_ratio, 0.22)
        if top < 0.30 and margin < 0.05:
            blend_ratio = max(blend_ratio, 0.14)

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


class LocalCnnImageEmotionModel:
    """Offline FER-2013 CNN backend trained by app.ml.train_image_model."""

    def __init__(self) -> None:
        import torch

        if not CNN_ARTIFACT_PATH.exists():
            raise FileNotFoundError(f"Local CNN artifact not found: {CNN_ARTIFACT_PATH}")

        self.torch = torch
        self.device = _select_torch_device(torch)
        self.model = _build_cnn_model()
        state = torch.load(CNN_ARTIFACT_PATH, map_location="cpu")
        self.model.load_state_dict(state)
        self.model.eval()
        self.model.to(self.device)
        self.face_detector, self.cv2 = ImageEmotionModel._build_face_detector()
        _logger.info("Loaded local CNN image model from %s on %s.", CNN_ARTIFACT_PATH, self.device)

    def _extract_face(self, image) -> Tuple[object, bool]:
        import numpy as np

        if self.face_detector is None or self.cv2 is None:
            return ImageEmotionModel._center_crop(image), False

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
            return ImageEmotionModel._center_crop(image), False

        x, y, width, height = max(faces, key=lambda item: int(item[2]) * int(item[3]))
        pad = int(max(width, height) * 0.20)
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(image.width, x + width + pad)
        bottom = min(image.height, y + height + pad)
        return image.crop((left, top, right, bottom)), True

    def _preprocess(self, image):
        import numpy as np

        # Grayscale + contrast normalize to match FER-2013 training conditions.
        gray = _enhance_face(image.convert("L")).resize((CNN_INPUT_W, CNN_INPUT_H))
        arr = np.asarray(gray, dtype="float32") / 255.0
        arr = (arr - 0.5) / 0.5
        return self.torch.from_numpy(arr).unsqueeze(0)

    def _predict_probabilities(self, image_data_url: str) -> Optional[Dict[Emotion, float]]:
        import numpy as np
        from PIL import Image

        image = _decode_image(image_data_url)
        if image is None:
            return None

        face, has_face = self._extract_face(image)
        face_array = np.asarray(face, dtype="uint8")
        image_std = float(np.std(face_array.astype("float32") / 255.0))
        batch = self.torch.stack([
            self._preprocess(face),
            self._preprocess(face.transpose(Image.FLIP_LEFT_RIGHT)),
        ]).to(self.device)

        with self.torch.no_grad():
            logits = self.model(batch).mean(dim=0)
            probabilities = self.torch.softmax(logits, dim=0).detach().cpu().numpy()

        app_probabilities: Dict[Emotion, float] = {e: 0.0 for e in EMOTION_ORDER}
        for raw_index, probability in enumerate(probabilities):
            raw_label = CNN_RAW_CLASSES[raw_index]
            app_probabilities[CNN_LABEL_TO_APP[raw_label]] += float(probability)

        total = sum(app_probabilities.values())
        if total <= 0:
            return None

        normalized = {e: app_probabilities[e] / total for e in EMOTION_ORDER}
        calibrated = ImageEmotionModel._calibrate_probabilities(
            normalized,
            has_face=has_face,
            image_std=image_std,
        )
        _log_image_prediction("cnn", has_face, calibrated)
        return calibrated

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
def get_image_model():
    if skip_image_emotion_model():
        _logger.info(
            "SKIP_IMAGE_EMOTION_MODEL / LIGHTWEIGHT_ML set — skipping image model.",
        )
        return None

    backend = os.getenv("IMAGE_EMOTION_BACKEND", "cnn").strip().lower()
    if backend in {"cnn", "local", "local_cnn"}:
        return _load_local_cnn_model()
    if backend not in {"hf", "vit", "huggingface"}:
        _logger.warning("Unknown IMAGE_EMOTION_BACKEND=%s; using local CNN.", backend)
        return _load_local_cnn_model()

    try:
        return ImageEmotionModel()
    except Exception as error:
        _logger.warning(
            "Could not load HuggingFace image model (%s). "
            "Falling back to local CNN.",
            error,
        )
        return _load_local_cnn_model()


def _load_local_cnn_model():
    try:
        return LocalCnnImageEmotionModel()
    except Exception as error:
        _logger.warning(
            "Could not load local CNN image model (%s). Image emotion detection will be disabled.",
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
