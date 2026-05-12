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
from typing import List, Optional, Tuple

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "emotion_cnn.pth"
CSV_FILENAME = "fer2013.csv"

# FER-2013 class labels match the RAW_CLASSES list in image_model.py.
FER_CLASSES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]

INPUT_H = 128
INPUT_W = 144
BATCH_SIZE = 64
EPOCHS = 45
LR = 5e-4
PATIENCE = 8      # early-stopping patience (epochs without val improvement)
WEIGHT_DECAY = 1e-4


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
            else:
                val_px.append(pixels)
                val_lb.append(label)

    _logger.info(
        "FER-2013 loaded from CSV: %d train / %d val samples.", len(train_lb), len(val_lb)
    )
    return train_px, train_lb, val_px, val_lb


def _load_from_huggingface() -> Tuple[List, List, List, List]:
    """Download FER-2013 from Hugging Face hub (no auth required).

    Tries multiple known mirrors so the script works even if the default one
    moves or is deprecated.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        _logger.error(
            "Hugging Face `datasets` package is required.\n"
            "  → pip install datasets"
        )
        sys.exit(1)

    # Each entry: (repo_id, kwargs).  The first that loads wins.
    # We start with auto-converted parquet branches (no scripts → modern API safe).
    candidates = [
        ("Jeneral/fer2013", {"revision": "refs/convert/parquet"}),
        ("AutumnQiu/fer2013", {}),
        ("abhilash88/fer2013-enhanced", {}),
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

    # Detect column names from the first row.
    sample = ds[list(ds.keys())[0]][0]
    _logger.info("Sample row keys: %s", list(sample.keys()))
    _logger.info(
        "Sample row types: %s",
        {k: type(v).__name__ for k, v in sample.items()},
    )

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
    _logger.info(
        "Detected: pixel=%s  image=%s  label=%s",
        detected_pixel_key, detected_image_key, detected_label_key,
    )

    if not detected_label_key or (not detected_pixel_key and not detected_image_key):
        raise RuntimeError(
            f"Cannot detect FER-2013 columns in {list(sample.keys())}. "
            "Open the dataset on HuggingFace and update pixel_keys/label_keys."
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
                    img = _PILImage.open(image_field)  # path-like
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

    val_split_name = None
    for candidate in ("test", "validation", "valid"):
        if candidate in available_splits:
            val_split_name = candidate
            break

    if val_split_name:
        val_px, val_lb = _split_to_lists(ds[val_split_name])
    else:
        # 90/10 hand-split
        cut = int(len(train_px) * 0.9)
        val_px, val_lb = train_px[cut:], train_lb[cut:]
        train_px, train_lb = train_px[:cut], train_lb[:cut]

    _logger.info(
        "FER-2013 loaded from HF: %d train / %d val samples.", len(train_lb), len(val_lb)
    )
    return train_px, train_lb, val_px, val_lb


def _load_from_kaggle() -> Tuple[List, List, List, List]:
    _logger.info("Trying Kaggle API …")
    try:
        import kaggle  # noqa: F401 – triggers credential setup
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
    """Top-level loader: try local CSV → HuggingFace → Kaggle."""
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
    import torch
    from torch.utils.data import Dataset
    from torchvision import transforms

    base_tf = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((INPUT_H, INPUT_W)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5]),
    ])

    # Milder augmentation than before — strong augmentation was making train_acc
    # look much lower than val_acc and slowed convergence.
    aug_tf = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((INPUT_H, INPUT_W)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(6),
        transforms.ColorJitter(brightness=0.12, contrast=0.12),
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


# ── Model ──────────────────────────────────────────────────────────────────

def _build_model():
    import torch.nn as nn
    import torch.nn.functional as F

    class EmotionCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = nn.Conv2d(1, 16, 3)
            self.conv2 = nn.Conv2d(16, 32, 3)
            self.conv3 = nn.Conv2d(32, 64, 3)
            self.pool = nn.MaxPool2d(2, 2)
            self.dropout = nn.Dropout(0.4)
            self.fc1 = nn.Linear(14336, 128)
            self.fc2 = nn.Linear(128, 7)

        def forward(self, x):
            x = self.pool(F.relu(self.conv1(x)))
            x = self.pool(F.relu(self.conv2(x)))
            x = self.pool(F.relu(self.conv3(x)))
            x = x.flatten(1)
            x = self.dropout(F.relu(self.fc1(x)))
            return self.fc2(x)

    return EmotionCNN()


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
    # num_workers=0 → run in the main process. This avoids pickling issues
    # with locally-defined dataset classes and works fine for FER-2013 size.
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_dl = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = _build_model().to(device)

    # Warm-start is intentionally DISABLED: re-using old weights with a
    # different RAW_CLASSES ordering would carry over the previous label
    # confusion.  Set WARM_START=1 in the env to force a warm start.
    if os.environ.get("WARM_START") == "1" and ARTIFACT_PATH.exists():
        try:
            state = torch.load(ARTIFACT_PATH, map_location="cpu")
            model.load_state_dict(state)
            _logger.info("Loaded existing weights from %s (warm start).", ARTIFACT_PATH)
        except Exception as exc:
            _logger.warning("Could not load existing weights (%s); training from scratch.", exc)
    else:
        _logger.info("Training from scratch (warm-start disabled).")

    # Class-balanced weights to handle FER-2013 imbalance.
    try:
        import numpy as np
        counts = np.bincount(train_lb, minlength=7).astype(float)
        class_weights = torch.tensor(1.0 / (counts + 1), dtype=torch.float32).to(device)
    except ImportError:
        class_weights = None

    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    best_val_acc = 0.0
    patience_counter = 0

    for epoch in range(1, EPOCHS + 1):
        # ── Train ──
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
            optimizer.step()
            total_loss += loss.item() * len(yb)
            correct += (logits.argmax(1) == yb).sum().item()
            total += len(yb)
        train_acc = correct / total

        # ── Validate ──
        model.eval()
        v_correct = 0
        v_total = 0
        with torch.no_grad():
            for xb, yb in val_dl:
                xb, yb = xb.to(device), yb.to(device)
                logits = model(xb)
                v_correct += (logits.argmax(1) == yb).sum().item()
                v_total += len(yb)
        val_acc = v_correct / v_total

        scheduler.step()
        _logger.info(
            "Epoch %02d/%02d  train_acc=%.3f  val_acc=%.3f  lr=%.2e",
            epoch, EPOCHS, train_acc, val_acc,
            optimizer.param_groups[0]["lr"],
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience_counter = 0
            ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), ARTIFACT_PATH)
            _logger.info("  ✓ New best (%.3f) — saved to %s", best_val_acc, ARTIFACT_PATH)
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                _logger.info("Early stopping at epoch %d (no improvement for %d epochs).", epoch, PATIENCE)
                break

    _logger.info("Training complete. Best val accuracy: %.3f", best_val_acc)
    _logger.info("Model saved to: %s", ARTIFACT_PATH)


if __name__ == "__main__":
    _train()
