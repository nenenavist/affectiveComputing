"""Train a strong text-emotion classifier.

Pipeline:
1. Load two public emotion datasets that together cover EN and RU:
     • dair-ai/emotion  (~20k EN tweets, 6-class)
     • cedr             (~9k RU sentences, 5-class)
2. Map their labels to our 4 emotions (happy / sad / angry / neutral).
3. Encode every sentence with a multilingual sentence-transformer
   (paraphrase-multilingual-MiniLM-L12-v2 — 118 MB, supports 50+ languages).
4. Train a calibrated Logistic Regression on top of the embeddings.
5. Save the classifier + encoder name to artifacts/text_classifier.joblib.

Usage:
    cd python-backend && source venv/bin/activate
    pip install -r requirements.txt          # ensure deps
    python -m app.ml.train_text_model

Output:
    app/ml/artifacts/text_classifier.joblib
    app/ml/artifacts/text_encoder.txt
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
CLASSIFIER_PATH = ARTIFACTS_DIR / "text_classifier.joblib"
ENCODER_NAME_PATH = ARTIFACTS_DIR / "text_encoder.txt"

ENCODER_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

EMOTIONS = ["happy", "sad", "angry", "neutral"]


# ── Dataset loaders ────────────────────────────────────────────────────────

def _load_dair_emotion() -> Tuple[List[str], List[str]]:
    """English emotion dataset (joy/sadness/anger/fear/love/surprise → our 4)."""
    from datasets import load_dataset

    _logger.info("Loading dair-ai/emotion …")
    ds = load_dataset("dair-ai/emotion", "split")

    label_map = {
        # dair-ai/emotion label index → our 4 classes
        # 0=sadness, 1=joy, 2=love, 3=anger, 4=fear, 5=surprise
        0: "sad", 1: "happy", 2: "happy", 3: "angry", 4: "neutral", 5: "neutral",
    }

    texts, labels = [], []
    for split in ("train", "validation", "test"):
        if split not in ds:
            continue
        for row in ds[split]:
            label = label_map.get(int(row["label"]))
            if label is None:
                continue
            text = (row.get("text") or "").strip()
            if not text:
                continue
            texts.append(text)
            labels.append(label)
    _logger.info("  → %d examples from dair-ai/emotion.", len(texts))
    return texts, labels


def _load_cedr() -> Tuple[List[str], List[str]]:
    """Russian emotion dataset CEDR (5-class)."""
    from datasets import load_dataset

    _logger.info("Loading CEDR (Russian) …")
    try:
        ds = load_dataset("cedr", "main")
    except Exception as exc:
        _logger.warning("Could not load CEDR (%s). Skipping Russian dataset.", exc)
        return [], []

    # CEDR has multi-label "labels" list with indices to:
    # 0=joy, 1=sadness, 2=surprise, 3=fear, 4=anger
    label_map = {0: "happy", 1: "sad", 2: "neutral", 3: "neutral", 4: "angry"}

    texts, labels = [], []
    for split in ("train", "test", "validation"):
        if split not in ds:
            continue
        for row in ds[split]:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            row_labels = row.get("labels") or []
            mapped_labels = [label_map[int(x)] for x in row_labels if int(x) in label_map]

            if not mapped_labels:
                texts.append(text)
                labels.append("neutral")
                continue

            for emotion in mapped_labels:
                texts.append(text)
                labels.append(emotion)

    _logger.info("  → %d examples from CEDR.", len(texts))
    return texts, labels


def _balance_classes(texts: List[str], labels: List[str], cap: int = 5000) -> Tuple[List[str], List[str]]:
    """Down-sample over-represented classes so each has ≤ `cap` examples."""
    import random
    random.seed(42)

    by_class: Dict[str, List[str]] = {e: [] for e in EMOTIONS}
    for text, label in zip(texts, labels):
        if label in by_class:
            by_class[label].append(text)

    out_texts, out_labels = [], []
    for emotion, items in by_class.items():
        if len(items) > cap:
            items = random.sample(items, cap)
        out_texts.extend(items)
        out_labels.extend([emotion] * len(items))
        _logger.info("  %s: %d examples", emotion, len(items))

    return out_texts, out_labels


# ── Encoder ────────────────────────────────────────────────────────────────

EMBED_CACHE_PATH = ARTIFACTS_DIR / "text_embeddings_cache.npz"


def _encode(texts: List[str], labels: List[str]):
    import hashlib
    import numpy as np

    # Cache key: hash of all texts so any corpus change invalidates the cache.
    key_source = "\n".join(texts).encode("utf-8")
    cache_key = hashlib.md5(key_source).hexdigest()

    if EMBED_CACHE_PATH.exists():
        try:
            cached = np.load(EMBED_CACHE_PATH, allow_pickle=True)
            if str(cached.get("key", "")) == cache_key:
                _logger.info("Loaded embeddings from cache (%d vectors).", len(cached["X"]))
                return cached["X"]
        except Exception as exc:
            _logger.warning("Could not read cache (%s) — re-encoding.", exc)

    from sentence_transformers import SentenceTransformer

    _logger.info("Loading encoder: %s", ENCODER_NAME)
    encoder = SentenceTransformer(ENCODER_NAME)
    _logger.info("Encoding %d texts …", len(texts))
    embeddings = encoder.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    embeddings = np.asarray(embeddings, dtype="float32")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(EMBED_CACHE_PATH, X=embeddings, key=cache_key)
    _logger.info("Cached embeddings to %s", EMBED_CACHE_PATH)
    return embeddings


# ── Training ───────────────────────────────────────────────────────────────

def _train_classifier(X, y):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.1, stratify=y, random_state=42
    )
    _logger.info("Train/val: %d / %d", len(X_train), len(X_val))

    clf = LogisticRegression(
        C=2.0,
        class_weight="balanced",
        max_iter=2000,
        solver="lbfgs",
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    val_acc = clf.score(X_val, y_val)
    _logger.info("Validation accuracy: %.3f", val_acc)

    proba = clf.predict_proba(X_val)
    pred = np.argmax(proba, axis=1)
    classes = list(clf.classes_)
    confusion: Dict[str, Dict[str, int]] = {e: {f: 0 for f in EMOTIONS} for e in EMOTIONS}
    for true_label, pred_idx in zip(y_val, pred):
        confusion[true_label][classes[pred_idx]] += 1

    _logger.info("Confusion (rows=true, cols=pred):")
    header = "  true\\pred  " + "  ".join(f"{c:>8s}" for c in EMOTIONS)
    _logger.info(header)
    for emotion in EMOTIONS:
        row_counts = [confusion[emotion][p] for p in EMOTIONS]
        _logger.info("  %8s  %s", emotion, "  ".join(f"{c:>8d}" for c in row_counts))

    return clf


def _save(clf) -> None:
    import joblib

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, CLASSIFIER_PATH)
    ENCODER_NAME_PATH.write_text(ENCODER_NAME, encoding="utf-8")
    _logger.info("Saved classifier: %s", CLASSIFIER_PATH)
    _logger.info("Saved encoder name: %s", ENCODER_NAME_PATH)


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    en_texts, en_labels = _load_dair_emotion()
    ru_texts, ru_labels = _load_cedr()
    texts = en_texts + ru_texts
    labels = en_labels + ru_labels
    _logger.info("Total raw examples: %d", len(texts))

    if not texts:
        _logger.error("No training data available — aborting.")
        sys.exit(1)

    _logger.info("Balancing classes (cap=4000 per class) …")
    texts, labels = _balance_classes(texts, labels, cap=4000)
    _logger.info("Final corpus: %d examples", len(texts))

    embeddings = _encode(texts, labels)
    clf = _train_classifier(embeddings, labels)
    _save(clf)
    _logger.info("Done. Run the backend — the new classifier will be picked up automatically.")


if __name__ == "__main__":
    main()
