from app.ml.image_model import detect_image_emotion
from app.ml.text_model import detect_text_emotion
from app.schemas import Emotion, MoodRequest


def detect_emotion(request: MoodRequest) -> Emotion:
    text_emotion = detect_text_emotion(request.text)
    image_emotion = detect_image_emotion(request.image)

    if text_emotion:
        return text_emotion

    if image_emotion:
        return image_emotion

    if request.hasCameraCapture:
        return "neutral"

    return "neutral"
