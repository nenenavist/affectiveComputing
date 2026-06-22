"""Fine-tune the emotion CNN on FER-2013 for maximum recognition quality.

Usage (from the python-backend directory with venv active):

    pip install datasets pandas tqdm torchvision        # one-time
    python -m app.ml.train_image_model

How dataset loading works (tries in order):
    1. Local file  ./fer2013.csv  (if present, skip download).
    2. HuggingFace datasets hub:  Jeneral/fer-2013  (NO login required).
    3. Kaggle API (only if KAGGLE_USERNAME / KAGGLE_KEY env vars set).

After training, the new weights are saved to
    app/ml/artifacts/emotion_cnn.pth
replacing the existing file.
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.ml.emotion_cnn import FER_RAW_CLASSES, FER_TO_APP, EmotionCNN

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "emotion_cnn.pth"
CSV_FILENAME = "fer2013.csv"

FER_CLASSES = FER_RAW_CLASSES
APP_EMOTIONS = ["happy", "sad", "angry", "neutral"]

INPUT_H = 48
INPUT_W = 48
BATCH_SIZE = 128
EPOCHS = 40
LR = 4e-4
PATIENCE = 8
WEIGHT_DECAY = 1e-4
LABEL_SMOOTHING = 0.05


def _fer_label_to_app(label_index: int) -> str:
    return FER_TO_APP[FER_CLASSES[label_index]]


# ── Utilities ──────────────────────────────────────────────────────────────

def _load_from_csv(csv_path: Path) -> Tuple[List, List, List, List]:
    """Parse fer2013.csv → (train_pixels, train_labels, val_pixels, val_labels)."""
    train_px, train_lb, val_px, val_lb = [], [], [], []

    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            label = int(row["emotion"])
            pixels = list(map(int, row["pixels"].split()))
            usage = row.get("Usage", "Training")
            if usage == "Training":
                train_px.append(pixels)
                train_lb.append(label)
            elif usage == "PublicTest":
                val_px.append(pixels)
                val_lb.append(label)

    if not val_lb:
        _logger.warning("No PublicTest rows found — using all non-Training rows for validation.")
        with open(csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                label = int(row["emotion"])
                pixels = list(map(int, row["pixels"].split()))
                usage = row.get("Usage", "Training")
                if usage != "Training":
                    val_px.append(pixels)
                    val_lb.append(label)

    _logger.info(
        "FER-2013 loaded from CSV: %d train / %d val samples.", len(train_lb), len(val_lb)
    )
    return train_px, train_lb, val_px, val_lb


def _load_from_huggingface() -> Tuple[List, List, List, List]:
    """Download FER-2013 from Hugging Face hub (no auth required)."""
    try:
        from datasets import load_dataset
    except ImportError:
        _logger.error(
            "Hugging Face `datasets` package is required.\n"
            "  → pip install datasets"
        )
        sys.exit(1)

    candidates = [
        ("AutumnQiu/fer2013", {}),
        ("abhilash88/fer2013-enhanced", {}),
        ("Jeneral/fer2013", {"revision": "refs/convert/parquet"}),
    ]

    ds = None
    last_error: Optional[Exception] = None
    for repo, kwargs in candidates:
        _logger.info("Trying HuggingFace dataset: %s %s", repo, kwargs or "")
        try:
            ds = load_dataset(repo, **kwargs)
            _logger.info("  ✓ Loaded %s", repo)
            break
        except Exception as exc:
            last_error = exc
            _logger.warning("  ✗ %s failed: %s", repo, exc)
            continue

    if ds is None:
        raise RuntimeError(
            f"No HuggingFace mirror could be loaded. Last error: {last_error}"
        )

    sample = ds[list(ds.keys())[0]][0]
    _logger.info("Sample row keys: %s", list(sample.keys()))

    pixel_keys = ("pixels", "Pixels", "img_pixels")
    image_keys = ("image", "img", "img_bytes", "image_bytes", "image_raw")
    label_keys = ("emotion", "label", "labels", "class", "y")

    def _detect_key(row, candidates):
        for key in candidates:
            if key in row and row[key] is not None:
                return key
        return None

    detected_pixel_key = _detect_key(sample, pixel_keys)
    detected_image_key = _detect_key(sample, image_keys)
    detected_label_key = _detect_key(sample, label_keys)

    if not detected_label_key or (not detected_pixel_key and not detected_image_key):
        raise RuntimeError(
            f"Cannot detect FER-2013 columns in {list(sample.keys())}."
        )

    from PIL import Image as _PILImage

    def _extract_row(row) -> Optional[Tuple[List[int], int]]:
        label = row.get(detected_label_key)
        if label is None:
            return None

        if detected_pixel_key:
            pixels_field = row.get(detected_pixel_key)
            if isinstance(pixels_field, str):
                pixels = list(map(int, pixels_field.split()))
            elif isinstance(pixels_field, (list, tuple)):
                pixels = [int(v) for v in pixels_field]
            else:
                pixels = None
            if pixels is not None and len(pixels) >= 48 * 48:
                return pixels, int(label)

        if detected_image_key:
            image_field = row.get(detected_image_key)
            try:
                if isinstance(image_field, _PILImage.Image):
                    img = image_field
                elif isinstance(image_field, (bytes, bytearray)):
                    from io import BytesIO
                    img = _PILImage.open(BytesIO(image_field))
                elif isinstance(image_field, dict) and "bytes" in image_field:
                    from io import BytesIO
                    img = _PILImage.open(BytesIO(image_field["bytes"]))
                else:
                    img = _PILImage.open(image_field)
                img = img.convert("L").resize((48, 48))
                return list(img.getdata()), int(label)
            except Exception:
                return None

        return None

    def _split_to_lists(split):
        pixels_list, labels_list = [], []
        skipped = 0
        for row in split:
            extracted = _extract_row(row)
            if extracted is None:
                skipped += 1
                continue
            pixels_list.append(extracted[0])
            labels_list.append(extracted[1])
        if skipped:
            _logger.warning("Skipped %d rows that could not be decoded.", skipped)
        return pixels_list, labels_list

    available_splits = list(ds.keys())
    _logger.info("Splits available: %s", available_splits)

    train_split_name = "train" if "train" in available_splits else available_splits[0]
    train_px, train_lb = _split_to_lists(ds[train_split_name])

    label_counts = {}
    for label in train_lb:
        label_counts[label] = label_counts.get(label, 0) + 1
    if len(label_counts) < 4:
        raise RuntimeError(
            f"Dataset {repo} has suspicious labels (only {len(label_counts)} classes): {label_counts}"
        )

    val_split_name = None
    for candidate in ("valid", "validation", "test"):
        if candidate in available_splits:
            val_split_name = candidate
            break

    if val_split_name:
        val_px, val_lb = _split_to_lists(ds[val_split_name])
    else:
        from sklearn.model_selection import train_test_split

        train_px, val_px, train_lb, val_lb = train_test_split(
            train_px,
            train_lb,
            test_size=0.1,
            stratify=train_lb,
            random_state=42,
        )

    _logger.info(
        "FER-2013 loaded from HF: %d train / %d val samples.", len(train_lb), len(val_lb)
    )
    return train_px, train_lb, val_px, val_lb


def _load_from_kaggle() -> Tuple[List, List, List, List]:
    _logger.info("Trying Kaggle API …")
    try:
        import kaggle  # noqa: F401
        os.system("kaggle datasets download -d msambare/fer2013 --unzip -p .")
    except Exception as exc:
        _logger.error("Kaggle download failed: %s", exc)
        sys.exit(1)
    csv_path = Path(CSV_FILENAME)
    if not csv_path.exists():
        _logger.error("fer2013.csv not found after Kaggle download.")
        sys.exit(1)
    return _load_from_csv(csv_path)


def _load_dataset() -> Tuple[List, List, List, List]:
    csv_path = Path(CSV_FILENAME)
    if csv_path.exists():
        _logger.info("Found %s locally – using it.", CSV_FILENAME)
        return _load_from_csv(csv_path)

    try:
        return _load_from_huggingface()
    except Exception as exc:
        _logger.warning("HuggingFace download failed: %s", exc)

    _logger.info("Trying Kaggle as last fallback …")
    try:
        return _load_from_kaggle()
    except SystemExit:
        pass

    _logger.error(
        "\n%s\n"
        "All automatic download paths failed.\n"
        "Manual fallback:\n"
        "  1. Download fer2013.csv from one of these mirrors:\n"
        "     • https://www.kaggle.com/datasets/deadskull7/fer2013\n"
        "     • https://github.com/oarriaga/face_classification\n"
        "  2. Place it in the python-backend/ directory.\n"
        "  3. Re-run:  python -m app.ml.train_image_model\n"
        "%s",
        "=" * 70,
        "=" * 70,
    )
    sys.exit(1)


# ── Dataset ────────────────────────────────────────────────────────────────

def _build_dataset(pixel_rows: List, labels: List, augment: bool):
    import numpy as np
    from torch.utils.data import Dataset
    from torchvision import transforms

    base_tf = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((INPUT_H, INPUT_W)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5]),
    ])

    aug_tf = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((INPUT_H, INPUT_W)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(8),
        transforms.ColorJitter(brightness=0.10, contrast=0.10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5]),
    ])

    class FERDataset(Dataset):
        def __init__(self, pixels, labels, transform):
            self.pixels = pixels
            self.labels = labels
            self.transform = transform

        def __len__(self):
            return len(self.labels)

        def __getitem__(self, idx):
            arr = np.array(self.pixels[idx], dtype=np.uint8).reshape(48, 48)
            x = self.transform(arr)
            y = self.labels[idx]
            return x, y

    tf = aug_tf if augment else base_tf
    return FERDataset(pixel_rows, labels, tf)


def _class_weights(train_labels: List[int], device, num_classes: int = 7):
    import numpy as np
    import torch

    counts = np.bincount(train_labels, minlength=num_classes).astype(float)
    counts = np.maximum(counts, 1.0)
    total = counts.sum()
    weights = total / (num_classes * counts)
    return torch.tensor(weights, dtype=torch.float32).to(device)


def _evaluate_app_accuracy(model, data_loader, device):
    """7-class model accuracy mapped to our 4 app emotions."""
    import torch

    model.eval()
    correct = 0
    total = 0
    confusion: Dict[str, Dict[str, int]] = {
        emotion: {pred: 0 for pred in APP_EMOTIONS} for emotion in APP_EMOTIONS
    }

    with torch.no_grad():
        for xb, yb in data_loader:
            xb, yb = xb.to(device), yb.to(device)
            logits = model(xb)
            pred_indices = logits.argmax(1)
            for true_index, pred_index in zip(yb.tolist(), pred_indices.tolist()):
                true_app = _fer_label_to_app(true_index)
                pred_app = _fer_label_to_app(pred_index)
                confusion[true_app][pred_app] += 1
                if true_app == pred_app:
                    correct += 1
                total += 1

    return correct / max(total, 1), confusion


# ── Training loop ──────────────────────────────────────────────────────────

def _train() -> None:
    import torch
    from torch.utils.data import DataLoader

    train_px, train_lb, val_px, val_lb = _load_dataset()

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    _logger.info("Training on %s", device)

    train_ds = _build_dataset(train_px, train_lb, augment=True)
    val_ds = _build_dataset(val_px, val_lb, augment=False)

    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_dl = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = EmotionCNN(num_classes=7).to(device)

    if os.environ.get("WARM_START") == "1" and ARTIFACT_PATH.exists():
        try:
            state = torch.load(ARTIFACT_PATH, map_location="cpu")
            model.load_state_dict(state, strict=False)
            _logger.info("Partial warm start from %s (strict=False).", ARTIFACT_PATH)
        except Exception as exc:
            _logger.warning("Could not load existing weights (%s); training from scratch.", exc)
    else:
        _logger.info("Training from scratch.")

    class_weights = _class_weights(train_lb, device)
    criterion = torch.nn.CrossEntropyLoss(
        weight=class_weights,
        label_smoothing=LABEL_SMOOTHING,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    best_app_acc = 0.0
    best_raw_acc = 0.0
    patience_counter = 0

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        for xb, yb in train_dl:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            total_loss += loss.item() * len(yb)
            correct += (logits.argmax(1) == yb).sum().item()
            total += len(yb)
        train_acc = correct / total

        model.eval()
        v_correct = 0
        v_total = 0
        with torch.no_grad():
            for xb, yb in val_dl:
                xb, yb = xb.to(device), yb.to(device)
                logits = model(xb)
                v_correct += (logits.argmax(1) == yb).sum().item()
                v_total += len(yb)
        val_acc = v_correct / max(v_total, 1)
        app_acc, confusion = _evaluate_app_accuracy(model, val_dl, device)

        scheduler.step()
        _logger.info(
            "Epoch %02d/%02d  train_acc=%.3f  val_acc=%.3f  app_acc=%.3f  lr=%.2e",
            epoch, EPOCHS, train_acc, val_acc, app_acc,
            optimizer.param_groups[0]["lr"],
        )

        improved = app_acc > best_app_acc or (app_acc == best_app_acc and val_acc > best_raw_acc)
        if improved:
            best_app_acc = app_acc
            best_raw_acc = val_acc
            patience_counter = 0
            ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), ARTIFACT_PATH)
            _logger.info(
                "  ✓ New best app_acc=%.3f raw_acc=%.3f — saved to %s",
                best_app_acc, best_raw_acc, ARTIFACT_PATH,
            )
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                _logger.info(
                    "Early stopping at epoch %d (no improvement for %d epochs).",
                    epoch, PATIENCE,
                )
                break

    _logger.info("Training complete. Best app accuracy: %.3f (raw: %.3f)", best_app_acc, best_raw_acc)
    _logger.info("Model saved to: %s", ARTIFACT_PATH)


if __name__ == "__main__":
    _train()
