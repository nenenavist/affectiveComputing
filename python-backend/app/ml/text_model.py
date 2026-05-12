import re
import math
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from app.schemas import Emotion

# ── Emoji → emotion mapping (strong explicit signal) ────────────────────────
EMOJI_EMOTION_MAP: Dict[str, Emotion] = {
    # happy
    "😊": "happy", "😄": "happy", "😃": "happy", "😁": "happy", "😆": "happy",
    "🥰": "happy", "😍": "happy", "🤩": "happy", "😸": "happy", "🎉": "happy",
    "❤": "happy", "💕": "happy", "💖": "happy", "💗": "happy", "💓": "happy",
    "😻": "happy", "🥳": "happy", "😎": "happy", "🤗": "happy", "☺": "happy",
    "✨": "happy", "🌟": "happy", "🎊": "happy", "🌈": "happy", "😏": "happy",
    # sad
    "😢": "sad", "😭": "sad", "😔": "sad", "😞": "sad", "💔": "sad",
    "😿": "sad", "🥺": "sad", "😥": "sad", "😓": "sad", "😪": "sad",
    "😑": "sad", "😶": "sad", "🥲": "sad", "😧": "sad", "😦": "sad",
    "😩": "sad", "😫": "sad", "🌧": "sad", "☁": "sad",
    # angry
    "😠": "angry", "😡": "angry", "🤬": "angry", "💢": "angry", "😤": "angry",
    "😾": "angry", "👊": "angry", "🔥": "angry", "💥": "angry", "⚡": "angry",
    "🤯": "angry", "😒": "angry",
    # neutral
    "😐": "neutral", "🤷": "neutral", "🙂": "neutral", "🤔": "neutral",
    "😌": "neutral", "😶": "neutral",
}
EMOJI_WEIGHT = 1.9   # emojis carry strong intentional signal


TEXT_ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "text_sentiment.joblib"
TRANSFORMER_CLF_PATH = Path(__file__).resolve().parent / "artifacts" / "text_classifier.joblib"
TRANSFORMER_ENCODER_PATH = Path(__file__).resolve().parent / "artifacts" / "text_encoder.txt"
EMOTION_ORDER: List[Emotion] = ["happy", "sad", "angry", "neutral"]

WEIGHTED_KEYWORDS: Dict[Emotion, Dict[str, float]] = {
    "happy": {
        "happy": 1.5,
        "joy": 1.5,
        "love": 1.4,
        "amazing": 1.4,
        "great": 1.2,
        "good": 1.0,
        "excited": 1.3,
        "smile": 1.1,
        "calm": 0.7,
        "fun": 1.2,
        "win": 1.1,
        "celebrate": 1.4,
        "рад": 1.5,
        "счаст": 1.6,
        "хорош": 1.0,
        "люблю": 1.3,
        "восторг": 1.5,
        "улыб": 1.1,
        "побед": 1.2,
    },
    "sad": {
        "sad": 1.6,
        "tired": 1.1,
        "lonely": 1.4,
        "hurt": 1.3,
        "cry": 1.4,
        "bad": 0.9,
        "down": 1.0,
        "empty": 1.4,
        "depressed": 1.7,
        "hopeless": 1.5,
        "lost": 1.0,
        "miss": 1.1,
        "груст": 1.6,
        "устал": 1.2,
        "одинок": 1.5,
        "плохо": 1.1,
        "плак": 1.4,
        "тоск": 1.5,
        "депресс": 1.7,
        "скучаю": 1.1,
        "тревог": 1.2,
        "выгор": 1.4,
        "разбит": 1.3,
    },
    "angry": {
        "angry": 1.6,
        "mad": 1.4,
        "furious": 1.7,
        "stress": 1.3,
        "annoyed": 1.2,
        "hate": 1.5,
        "rage": 1.6,
        "irritated": 1.1,
        "frustrated": 1.3,
        "pissed": 1.5,
        "зл": 1.5,
        "бесит": 1.6,
        "стресс": 1.3,
        "ненавиж": 1.6,
        "ярост": 1.6,
        "раздраж": 1.2,
        "взбешен": 1.7,
        "злюсь": 1.5,
        "агресс": 1.5,
        "бомбит": 1.6,
        "кип": 1.3,
    },
    "neutral": {
        "okay": 0.9,
        "fine": 0.9,
        "normal": 1.0,
        "neutral": 1.2,
        "usual": 0.9,
        "average": 0.9,
        "meh": 1.0,
        "норм": 1.0,
        "обычно": 0.9,
        "нейтраль": 1.2,
        "ровно": 1.0,
        "спокой": 1.1,
        "фокус": 1.0,
        "стабиль": 1.0,
    },
}

NEGATIONS = {
    "not",
    "no",
    "never",
    "without",
    "isn't",
    "wasn't",
    "don't",
    "doesn't",
    "didn't",
    "can't",
    "cannot",
    "won't",
    "shouldn't",
    "couldn't",
    "wouldn't",
    "нет",
    "не",
    "ни",
}

INTENSIFIERS = {
    "very": 1.4,
    "really": 1.3,
    "so": 1.2,
    "super": 1.4,
    "extremely": 1.6,
    "totally": 1.3,
    "completely": 1.4,
    "absolutely": 1.4,
    "очень": 1.4,
    "сильно": 1.3,
    "крайне": 1.5,
    "совсем": 1.2,
    "ужасно": 1.4,
}

CONTRAST_TOKENS = {
    "but",
    "however",
    "though",
    "yet",
    "но",
    "однако",
    "зато",
    "хотя",
}

SENTIMENT_TO_EMOTION: Dict[int, Emotion] = {-1: "sad", 0: "neutral", 1: "happy"}
PIPELINE_LABEL_TO_EMOTION: Dict[str, Emotion] = {
    "happy": "happy",
    "sad": "sad",
    "angry": "angry",
    "neutral": "neutral",
    "positive": "happy",
    "negative": "sad",
}

TRAINING_CORPUS: Sequence[Tuple[str, Emotion]] = (
    # ── HAPPY ────────────────────────────────────────────────────────────────
    ("i am happy and energetic today", "happy"),
    ("feeling amazing and excited", "happy"),
    ("this day is great i am smiling", "happy"),
    ("я сегодня очень рада и вдохновлена", "happy"),
    ("чувствую восторг и мотивацию", "happy"),
    ("настроение отличное и легкое", "happy"),
    ("мне спокойно и хорошо", "happy"),
    ("feeling relaxed and grateful", "happy"),
    ("love this vibe and sunshine", "happy"),
    ("party mood dance energy", "happy"),
    ("i feel joyful but still calm", "happy"),
    ("у меня радость и прилив сил", "happy"),
    ("я довольна и спокойна", "happy"),
    ("best day ever everything is perfect", "happy"),
    ("celebrating and feeling on top of the world", "happy"),
    ("so grateful and blessed right now", "happy"),
    ("full of energy and positive vibes", "happy"),
    ("i could not be happier life is good", "happy"),
    ("laughing and smiling all day", "happy"),
    ("fell in love it is wonderful", "happy"),
    ("achieved my goal proud and happy", "happy"),
    ("summer vibes sunshine happiness", "happy"),
    ("in love with life and everything around me", "happy"),
    ("радостно и тепло на душе", "happy"),
    ("чувствую любовь и благодарность", "happy"),
    ("нереально круто всё получилось", "happy"),
    ("я улыбаюсь без причины просто хорошо", "happy"),
    ("лёгкость и радость весь день", "happy"),
    ("позитив зашкаливает жизнь прекрасна", "happy"),
    ("мне классно и весело сегодня", "happy"),
    ("ура победа так счастлива", "happy"),
    ("сердце поёт от радости", "happy"),
    ("наслаждаюсь каждым моментом", "happy"),
    ("получила подарок безумно рада", "happy"),
    ("влюблена и это лучшее чувство", "happy"),
    ("всё складывается идеально", "happy"),
    ("сегодня лучший день недели", "happy"),
    ("прекрасное настроение хочу петь", "happy"),
    ("полна сил и вдохновения", "happy"),
    ("overjoyed absolutely wonderful feeling", "happy"),
    ("thrilled and delighted with everything", "happy"),
    ("life feels magical today", "happy"),
    ("so much joy and gratitude", "happy"),
    ("feeling loved and appreciated", "happy"),
    ("happiness is everywhere today", "happy"),
    ("smiling from ear to ear", "happy"),
    ("everything is going my way", "happy"),
    # ── SAD ──────────────────────────────────────────────────────────────────
    ("i feel sad and lonely", "sad"),
    ("i am tired and empty", "sad"),
    ("heartbroken and down today", "sad"),
    ("мне грустно и одиноко", "sad"),
    ("очень устала и хочется плакать", "sad"),
    ("тоскливо и ничего не радует", "sad"),
    ("feeling depressed and hopeless", "sad"),
    ("день тяжелый и печальный", "sad"),
    ("everything feels pointless", "sad"),
    ("i miss someone and it hurts", "sad"),
    ("я уставшая и разбитая сегодня", "sad"),
    ("вроде нормально но внутри тревожно", "sad"),
    ("i feel anxious and low", "sad"),
    ("crying without a reason", "sad"),
    ("feel like nobody cares about me", "sad"),
    ("lost and broken inside", "sad"),
    ("melancholy and nostalgia all around", "sad"),
    ("grieving and missing better times", "sad"),
    ("exhausted soul weary and blue", "sad"),
    ("nothing excites me anymore", "sad"),
    ("overwhelmed and feeling low", "sad"),
    ("loneliness is crushing me", "sad"),
    ("tears keep falling can not stop", "sad"),
    ("empty hollow and without joy", "sad"),
    ("мне грустно без причины", "sad"),
    ("плохо на душе хочется исчезнуть", "sad"),
    ("всё кажется серым и бессмысленным", "sad"),
    ("тоска и одиночество гложут изнутри", "sad"),
    ("нет сил и желания что-либо делать", "sad"),
    ("слёзы сами текут не знаю почему", "sad"),
    ("тревога и печаль не отступают", "sad"),
    ("чувствую себя никому не нужной", "sad"),
    ("грусть накрыла с головой", "sad"),
    ("потерялась в себе и не могу найти выход", "sad"),
    ("всё рухнуло и стало пусто", "sad"),
    ("нет настроения совсем ничего не хочу", "sad"),
    ("устала от всего и хочется покоя", "sad"),
    ("мне больно и обидно", "sad"),
    ("ощущение пустоты и бессилия", "sad"),
    ("скучаю и на сердце тяжело", "sad"),
    ("чувствую себя сломленной", "sad"),
    ("депрессия накрыла и не отпускает", "sad"),
    ("разочарована и опустошена", "sad"),
    ("sad crying tears running down", "sad"),
    ("broken and miserable", "sad"),
    ("deeply unhappy nothing works out", "sad"),
    ("feel like giving up", "sad"),
    ("drained and despondent", "sad"),
    ("so disappointed and let down", "sad"),
    # ── ANGRY ────────────────────────────────────────────────────────────────
    ("i am angry and frustrated", "angry"),
    ("so mad and irritated right now", "angry"),
    ("this is infuriating and stressful", "angry"),
    ("я злая и меня все бесит", "angry"),
    ("очень раздражен и на пределе", "angry"),
    ("в ярости и не могу успокоиться", "angry"),
    ("rage and pressure all day", "angry"),
    ("ненавижу этот день", "angry"),
    ("i feel explosive and tense", "angry"),
    ("extremely annoyed and upset", "angry"),
    ("я злюсь и закипаю от стресса", "angry"),
    ("меня бомбит от этой ситуации", "angry"),
    ("furious beyond words right now", "angry"),
    ("seething with anger can not calm down", "angry"),
    ("hateful and bitter about everything", "angry"),
    ("boiling with frustration", "angry"),
    ("fed up with all the nonsense", "angry"),
    ("so much anger building inside", "angry"),
    ("pissed off and want to break things", "angry"),
    ("outraged and absolutely furious", "angry"),
    ("all this unfairness makes me livid", "angry"),
    ("агрессия просто зашкаливает", "angry"),
    ("всё бесит и раздражает по мелочам", "angry"),
    ("закипаю от злости каждый день", "angry"),
    ("терпение на исходе взрываюсь изнутри", "angry"),
    ("хочется всё разнести вдребезги", "angry"),
    ("злость и обида душат меня", "angry"),
    ("ярость кипит внутри не остановить", "angry"),
    ("меня не ценят и это бесит", "angry"),
    ("готова взорваться от несправедливости", "angry"),
    ("ненависть переполняет всё внутри", "angry"),
    ("стресс и злоба на всё вокруг", "angry"),
    ("раздражение накопилось до предела", "angry"),
    ("в бешенстве и ничего не могу поделать", "angry"),
    ("взбешена и злюсь на всех", "angry"),
    ("angry irritated done with everything", "angry"),
    ("total frustration and rage today", "angry"),
    ("snapping at everyone so angry", "angry"),
    ("madness and stress overwhelming me", "angry"),
    ("hostile and tense all day", "angry"),
    ("grinding teeth with pure rage", "angry"),
    # ── NEUTRAL ──────────────────────────────────────────────────────────────
    ("i feel neutral and normal", "neutral"),
    ("just okay nothing special", "neutral"),
    ("usual day calm and steady", "neutral"),
    ("обычный день без эмоций", "neutral"),
    ("нормально ровное состояние", "neutral"),
    ("спокойно работаю как обычно", "neutral"),
    ("meh just routine and focus", "neutral"),
    ("все стабильно и без перепадов", "neutral"),
    ("nothing bad nothing great", "neutral"),
    ("нейтральное ровное настроение", "neutral"),
    ("я спокойна и в рабочем фокусе", "neutral"),
    ("все стабильно и просто обычно", "neutral"),
    ("i am balanced and focused", "neutral"),
    ("just another regular day", "neutral"),
    ("no strong feelings today just existing", "neutral"),
    ("work done coffee had nothing particular", "neutral"),
    ("calm and collected moving forward", "neutral"),
    ("steady pace nothing exciting", "neutral"),
    ("keeping it simple and stable", "neutral"),
    ("not happy not sad somewhere in between", "neutral"),
    ("feeling indifferent about most things", "neutral"),
    ("day passes by without highs or lows", "neutral"),
    ("composed and functioning normally", "neutral"),
    ("всё в норме как обычно", "neutral"),
    ("ничего особенного просто день", "neutral"),
    ("в рабочем режиме без эмоций", "neutral"),
    ("спокойствие и ровное состояние", "neutral"),
    ("всё идёт своим чередом", "neutral"),
    ("нет ни плохого ни хорошего", "neutral"),
    ("день как день без лишних переживаний", "neutral"),
    ("занимаюсь делами и всё нормально", "neutral"),
    ("ровное настроение ничего не тревожит", "neutral"),
    ("стабильно без резких скачков", "neutral"),
    ("всё под контролем и нет стресса", "neutral"),
    ("нейтрально и без эмоций сейчас", "neutral"),
    ("working steadily not feeling much", "neutral"),
    ("neutral mood no complaints", "neutral"),
    ("going through the motions today", "neutral"),
    ("routine as usual nothing special", "neutral"),
    ("fine and unbothered", "neutral"),
    ("average day average energy", "neutral"),
)


@lru_cache(maxsize=1)
def get_text_pipeline():
    if not TEXT_ARTIFACT_PATH.exists():
        return _build_local_text_pipeline()

    try:
        import joblib

        loaded = joblib.load(TEXT_ARTIFACT_PATH)
        if loaded:
            return loaded
        return _build_local_text_pipeline()
    except Exception:
        return _build_local_text_pipeline()


@lru_cache(maxsize=1)
def get_transformer_classifier():
    """Load the strong transformer-based classifier (encoder + sklearn head).

    Returns (encoder, classifier) or None if the artifact does not exist or
    the dependencies are missing.  Once loaded the result is cached, so
    subsequent calls are O(1).
    """
    if not TRANSFORMER_CLF_PATH.exists() or not TRANSFORMER_ENCODER_PATH.exists():
        return None

    try:
        import joblib
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None

    try:
        encoder_name = TRANSFORMER_ENCODER_PATH.read_text(encoding="utf-8").strip()
        encoder = SentenceTransformer(encoder_name)
        classifier = joblib.load(TRANSFORMER_CLF_PATH)
        return encoder, classifier
    except Exception:
        return None


def _transformer_emotion_weights(text: str) -> Optional[Dict[Emotion, float]]:
    bundle = get_transformer_classifier()
    if bundle is None or not text.strip():
        return None

    encoder, classifier = bundle
    try:
        embedding = encoder.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        probabilities = classifier.predict_proba(embedding)[0]
        classes = list(classifier.classes_)
    except Exception:
        return None

    weights: Dict[Emotion, float] = {emotion: 0.0 for emotion in EMOTION_ORDER}
    for index, label in enumerate(classes):
        emotion = PIPELINE_LABEL_TO_EMOTION.get(str(label).lower().strip())
        if not emotion:
            continue
        weights[emotion] += float(probabilities[index])

    total = sum(weights.values())
    if total <= 0:
        return None
    return {emotion: weights[emotion] / total for emotion in EMOTION_ORDER}


def _build_local_text_pipeline():
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline
        from sklearn.svm import LinearSVC
    except Exception:
        return None

    examples = [clean_text(text) for text, _emotion in TRAINING_CORPUS]
    labels = [emotion for _text, emotion in TRAINING_CORPUS]
    if not examples:
        return None

    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    analyzer="char_wb",
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            ("clf", LinearSVC(C=1.2, class_weight="balanced", random_state=42)),
        ]
    )

    pipeline.fit(examples, labels)
    return pipeline


def detect_emoji_scores(text: str) -> Dict[Emotion, float]:
    """Extract emotion signal from emojis before the text is cleaned."""
    scores: Dict[Emotion, float] = {e: 0.0 for e in EMOTION_ORDER}
    for char in text:
        emotion = EMOJI_EMOTION_MAP.get(char)
        if emotion:
            scores[emotion] += EMOJI_WEIGHT
    return scores


def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[^\w\sа-яё']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def score_keywords(cleaned: str) -> Dict[Emotion, float]:
    """Score emotions by weighted keyword match with intensifier and negation support."""

    tokens = cleaned.split()
    scores: Dict[Emotion, float] = {emotion: 0.0 for emotion in EMOTION_ORDER}
    contrast_index = next((index for index, token in enumerate(tokens) if token in CONTRAST_TOKENS), -1)

    for index, token in enumerate(tokens):
        prev_token = tokens[index - 1] if index > 0 else ""
        prev_prev_token = tokens[index - 2] if index > 1 else ""
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        clause_multiplier = 1.0
        if contrast_index >= 0:
            clause_multiplier = 1.22 if index > contrast_index else 0.82

        is_negated = prev_token in NEGATIONS or prev_prev_token in NEGATIONS or next_token in NEGATIONS
        intensifier = INTENSIFIERS.get(prev_token, 1.0)
        if prev_prev_token in INTENSIFIERS:
            intensifier *= 1.06

        for emotion, keyword_map in WEIGHTED_KEYWORDS.items():
            for keyword, weight in keyword_map.items():
                if keyword not in token:
                    continue

                value = weight * intensifier * clause_multiplier
                if is_negated:
                    scores[emotion] -= value * 0.6
                else:
                    scores[emotion] += value

    return scores


def normalize_emotion_weights(scores: Dict[Emotion, float]) -> Dict[Emotion, float]:
    values = list(scores.values())
    temperature = 1.15
    stabilized = [value / temperature for value in values]
    peak = max(stabilized)
    exp_values = [math.exp(value - peak) for value in stabilized]
    total = sum(exp_values)

    if total <= 0:
        return {emotion: 0.0 for emotion in EMOTION_ORDER}

    return {
        emotion: round(exp_values[index] / total, 4)
        for index, emotion in enumerate(EMOTION_ORDER)
    }


def renormalize_distribution(weights: Dict[Emotion, float]) -> Dict[Emotion, float]:
    positives = {emotion: max(weights.get(emotion, 0.0), 0.0) for emotion in EMOTION_ORDER}
    total = sum(positives.values())
    if total <= 0:
        return {emotion: 0.0 for emotion in EMOTION_ORDER}
    return {emotion: round(positives[emotion] / total, 4) for emotion in EMOTION_ORDER}


def _predict_pipeline_emotion(pipeline, cleaned: str) -> Optional[Emotion]:
    if not pipeline:
        return None

    try:
        raw_prediction = str(pipeline.predict([cleaned])[0]).lower().strip()
    except Exception:
        return None

    if raw_prediction in PIPELINE_LABEL_TO_EMOTION:
        return PIPELINE_LABEL_TO_EMOTION[raw_prediction]

    if raw_prediction in {"-1", "0", "1"}:
        return SENTIMENT_TO_EMOTION.get(int(raw_prediction), "neutral")

    return None


def _pipeline_emotion_weights(pipeline, cleaned: str) -> Optional[Dict[Emotion, float]]:
    if not pipeline:
        return None

    try:
        classes = [str(item).lower().strip() for item in pipeline.classes_]
        decision = pipeline.decision_function([cleaned])[0]
    except Exception:
        predicted = _predict_pipeline_emotion(pipeline, cleaned)
        if not predicted:
            return None
        fallback = {emotion: 0.05 for emotion in EMOTION_ORDER}
        fallback[predicted] = 0.85
        return renormalize_distribution(fallback)

    if not isinstance(decision, (list, tuple)):
        try:
            import numpy as np

            decision_values = np.asarray(decision).reshape(-1).tolist()
        except Exception:
            decision_values = [float(decision)]
    else:
        decision_values = [float(value) for value in decision]

    if len(classes) == 2 and len(decision_values) == 1:
        margin = decision_values[0]
        decision_values = [-margin, margin]
    elif len(decision_values) != len(classes):
        predicted = _predict_pipeline_emotion(pipeline, cleaned)
        if not predicted:
            return None
        fallback = {emotion: 0.0 for emotion in EMOTION_ORDER}
        fallback[predicted] = 1.0
        return renormalize_distribution(fallback)

    mapped_scores = {emotion: 0.0 for emotion in EMOTION_ORDER}
    for index, label in enumerate(classes):
        emotion = PIPELINE_LABEL_TO_EMOTION.get(label)
        if emotion is None and label in {"-1", "0", "1"}:
            emotion = SENTIMENT_TO_EMOTION.get(int(label), "neutral")
        if emotion:
            mapped_scores[emotion] += float(decision_values[index])

    return normalize_emotion_weights(mapped_scores)


def detect_text_emotion(text: str) -> Optional[Emotion]:
    cleaned = clean_text(text)
    if not cleaned:
        return None

    weights = detect_text_emotion_weights(text)
    if max(weights.values()) <= 0:
        return None

    return max(weights, key=weights.get)


def detect_text_emotion_weights(text: str) -> Dict[Emotion, float]:
    """Detect emotion weights from text.

    Signal priority (when available):
        1. Strong transformer classifier (multilingual MiniLM + LogReg, ~70 %)
        2. Local TF-IDF pipeline (~15 %)
        3. Keyword heuristics (~10 %)
        4. Emoji signal (overlay, up to 30 %)

    If the transformer artifact is missing, falls back to the previous
    keyword + TF-IDF approach.
    """
    emoji_scores = detect_emoji_scores(text)
    has_emoji = any(v > 0 for v in emoji_scores.values())

    cleaned = clean_text(text)
    if not cleaned and not has_emoji:
        return {emotion: 0.0 for emotion in EMOTION_ORDER}

    keyword_scores = score_keywords(cleaned) if cleaned else {e: 0.0 for e in EMOTION_ORDER}
    keyword_weights = normalize_emotion_weights(keyword_scores)

    pipeline_weights = (
        _pipeline_emotion_weights(get_text_pipeline(), cleaned) if cleaned else None
    )

    transformer_weights = _transformer_emotion_weights(text) if cleaned else None

    if transformer_weights is not None:
        # Adaptive blending — the transformer is good on long, varied text
        # but can be unreliable on short Russian inputs like "мне грустно".
        # When the keyword signal is strong and agrees with itself, give
        # keywords/heuristics a much larger share.
        keyword_peak = max(keyword_weights.values()) if keyword_weights else 0.0
        keyword_top = max(keyword_weights, key=keyword_weights.get) if keyword_weights else None
        transformer_top = max(transformer_weights, key=transformer_weights.get)
        word_count = len(cleaned.split())

        # Default split.
        transformer_share = 0.55
        keyword_share = 0.32
        pipeline_share = 0.13 if pipeline_weights else 0.0

        # Strong, unambiguous keyword hit ⇒ trust keyword more.
        if keyword_peak >= 0.55:
            transformer_share = 0.32
            keyword_share = 0.55
            pipeline_share = 0.13 if pipeline_weights else 0.0

        # Short text (≤ 4 words) → transformer is less reliable for Russian.
        if word_count <= 4:
            transformer_share = min(transformer_share, 0.40)
            keyword_share = max(keyword_share, 0.48)

        # Disagreement: keyword and transformer point to different emotions.
        # Reduce transformer dominance unless its confidence is very high.
        if keyword_top and keyword_top != transformer_top and keyword_peak >= 0.40:
            transformer_share = min(transformer_share, 0.45)
            keyword_share = max(keyword_share, 0.42)

        total_share = transformer_share + keyword_share + pipeline_share
        transformer_share /= total_share
        keyword_share /= total_share
        if pipeline_weights:
            pipeline_share /= total_share

        weights = {
            e: transformer_weights[e] * transformer_share
            + keyword_weights[e] * keyword_share
            for e in EMOTION_ORDER
        }
        if pipeline_weights:
            for e in EMOTION_ORDER:
                weights[e] += pipeline_weights[e] * pipeline_share

    elif pipeline_weights:
        overlap = sum(min(keyword_weights[e], pipeline_weights[e]) for e in EMOTION_ORDER)
        pipeline_share = 0.52
        if overlap < 0.34:
            pipeline_share = 0.44
        if len(cleaned.split()) <= 2:
            pipeline_share = max(pipeline_share, 0.60)

        weights = {
            e: keyword_weights[e] * (1.0 - pipeline_share) + pipeline_weights[e] * pipeline_share
            for e in EMOTION_ORDER
        }
    else:
        weights = dict(keyword_weights)

    if has_emoji:
        emoji_weights = normalize_emotion_weights(emoji_scores)
        emoji_share = min(0.32, sum(emoji_scores.values()) / (len(text) * 0.3 + 1))
        emoji_share = max(emoji_share, 0.22)
        weights = {
            e: weights[e] * (1.0 - emoji_share) + emoji_weights[e] * emoji_share
            for e in EMOTION_ORDER
        }

    peak = max(weights.values())
    if peak < 0.34:
        weights["neutral"] = round(weights.get("neutral", 0.0) + 0.10, 4)
        weights = renormalize_distribution(weights)

    return renormalize_distribution(weights)
