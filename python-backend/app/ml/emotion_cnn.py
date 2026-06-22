"""Shared FER-2013 CNN architecture for training and inference."""

from __future__ import annotations

import torch.nn as nn
import torch.nn.functional as F

# FER-2013 raw labels (index order must stay stable across train/infer).
FER_RAW_CLASSES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]

FER_TO_APP = {
    "angry": "angry",
    "disgust": "angry",
    "fear": "neutral",
    "happy": "happy",
    "neutral": "neutral",
    "sad": "sad",
    "surprise": "happy",
}


class EmotionCNN(nn.Module):
    """Deeper CNN with BatchNorm — better FER-2013 accuracy than the old 3-layer net."""

    def __init__(self, num_classes: int = 7) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.conv3 = nn.Conv2d(64, 128, 3, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        self.conv4 = nn.Conv2d(128, 256, 3, padding=1)
        self.bn4 = nn.BatchNorm2d(256)
        self.pool = nn.MaxPool2d(2, 2)
        self.adaptive_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(0.45)
        self.fc1 = nn.Linear(256, 256)
        self.fc2 = nn.Linear(256, num_classes)

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.pool(F.relu(self.bn3(self.conv3(x))))
        x = self.pool(F.relu(self.bn4(self.conv4(x))))
        x = self.adaptive_pool(x)
        x = x.flatten(1)
        x = self.dropout(F.relu(self.fc1(x)))
        return self.fc2(x)


def map_fer_logits_to_app_probs(logits, torch_module):
    """Collapse 7-class FER logits into 4 app emotions via softmax + label merge."""
    probs = torch_module.softmax(logits, dim=-1)
    app_probs = {emotion: 0.0 for emotion in ("happy", "sad", "angry", "neutral")}
    for index, raw_label in enumerate(FER_RAW_CLASSES):
        app_emotion = FER_TO_APP[raw_label]
        app_probs[app_emotion] += float(probs[index].item())
    return app_probs
