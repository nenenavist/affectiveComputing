from typing import Iterable, List


TAG_WEIGHTS = {
    "happy": (1.0, 0.6, 0.0, 0.0),
    "joy": (1.0, 0.6, 0.0, 0.0),
    "fun": (0.9, 0.7, 0.0, 0.0),
    "dance": (0.8, 0.9, 0.0, 0.0),
    "disco": (0.8, 0.8, 0.0, 0.0),
    "pop": (0.6, 0.5, 0.0, 0.0),
    "summer": (0.8, 0.5, 0.0, 0.0),
    "sad": (-0.9, -0.4, 0.0, 1.0),
    "melancholy": (-0.8, -0.3, 0.0, 1.0),
    "melancholic": (-0.8, -0.3, 0.0, 1.0),
    "depressing": (-1.0, -0.5, 0.0, 1.0),
    "rain": (-0.5, -0.3, 0.0, 0.7),
    "acoustic": (0.0, -0.4, 0.0, 0.2),
    "ambient": (0.0, -0.7, 0.0, 0.2),
    "chill": (0.2, -0.6, 0.0, 0.1),
    "calm": (0.2, -0.8, 0.0, 0.0),
    "relax": (0.3, -0.8, 0.0, 0.0),
    "angry": (-0.8, 0.8, 1.0, 0.0),
    "rage": (-0.9, 0.9, 1.0, 0.0),
    "metal": (-0.3, 0.9, 0.8, 0.0),
    "hard rock": (-0.2, 0.8, 0.7, 0.0),
    "punk": (-0.3, 0.8, 0.7, 0.0),
    "industrial": (-0.3, 0.7, 0.7, 0.0),
    "noise": (-0.5, 0.8, 0.8, 0.0),
    "instrumental": (0.0, -0.1, 0.0, 0.0),
    "classical": (0.0, -0.4, 0.0, 0.2),
    "jazz": (0.1, -0.1, 0.0, 0.1),
}


def normalize_tags(tags: Iterable[str]) -> List[str]:
    return [tag.strip().lower() for tag in tags if tag and tag.strip()]


def extract_music_features(title: str, artist: str, tags: Iterable[str]) -> List[float]:
    tokens = normalize_tags(tags)
    text = f"{title} {artist}".lower()
    for keyword in TAG_WEIGHTS:
        if keyword in text and keyword not in tokens:
            tokens.append(keyword)

    if not tokens:
        return [0.0, 0.0, 0.0, 0.0]

    totals = [0.0, 0.0, 0.0, 0.0]
    hits = 0

    for tag in tokens:
        for keyword, weights in TAG_WEIGHTS.items():
            if keyword in tag:
                totals = [current + weight for current, weight in zip(totals, weights)]
                hits += 1

    if hits == 0:
        return [0.0, 0.0, 0.0, 0.0]

    return [max(-1.0, min(1.0, value / hits)) for value in totals]
