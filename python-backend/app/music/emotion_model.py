from functools import lru_cache
from typing import List, Tuple

from app.schemas import Emotion


EMOTION_ORDER: List[Emotion] = ["happy", "sad", "angry", "neutral"]


class MusicEmotionNet:
    def __init__(self) -> None:
        import torch
        from torch import nn

        self.torch = torch
        self.model = nn.Sequential(
            nn.Linear(4, 8),
            nn.Tanh(),
            nn.Linear(8, 4),
        )
        self._train()
        self.model.eval()

    def _train(self) -> None:
        import torch
        from torch import nn

        training_rows = [
            ([0.8, 0.8, 0.0, 0.0], 0),
            ([0.7, 0.5, 0.0, 0.0], 0),
            ([-0.8, -0.4, 0.0, 0.9], 1),
            ([-0.6, -0.3, 0.0, 0.7], 1),
            ([-0.7, 0.9, 0.9, 0.0], 2),
            ([-0.4, 0.8, 0.8, 0.0], 2),
            ([0.0, -0.8, 0.0, 0.0], 3),
            ([0.1, -0.5, 0.0, 0.2], 3),
        ]
        x = torch.tensor([row[0] for row in training_rows], dtype=torch.float32)
        y = torch.tensor([row[1] for row in training_rows], dtype=torch.long)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.04)
        criterion = nn.CrossEntropyLoss()

        for _ in range(220):
            optimizer.zero_grad()
            loss = criterion(self.model(x), y)
            loss.backward()
            optimizer.step()

    def predict(self, features: List[float]) -> Tuple[Emotion, float]:
        tensor = self.torch.tensor([features], dtype=self.torch.float32)
        with self.torch.no_grad():
            probabilities = self.torch.softmax(self.model(tensor), dim=1)[0]
            score, index = self.torch.max(probabilities, dim=0)

        return EMOTION_ORDER[int(index.item())], round(float(score.item()), 4)


@lru_cache(maxsize=1)
def get_music_emotion_model() -> MusicEmotionNet:
    return MusicEmotionNet()
