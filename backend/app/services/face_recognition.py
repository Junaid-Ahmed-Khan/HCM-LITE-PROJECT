
import base64
import binascii
from functools import lru_cache

import cv2
import numpy as np
from deepface import DeepFace


MODEL_NAME = "Facenet512"
DETECTOR_BACKEND = "opencv"

# Initial prototype threshold only. Calibrate with real enrollment and
# verification samples before using this for consequential decisions.
MAX_COSINE_DISTANCE = 0.30

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def decode_image(image_base64: str) -> np.ndarray:
    """Decode a base64 image into an OpenCV BGR image."""
    if not image_base64 or not isinstance(image_base64, str):
        raise ValueError("A face image is required.")

    # Support data URLs such as data:image/jpeg;base64,...
    if image_base64.startswith("data:"):
        parts = image_base64.split(",", 1)
        if len(parts) != 2:
            raise ValueError("Invalid image data URL.")
        image_base64 = parts[1]

    try:
        raw = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The image must be valid base64.") from exc

    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be smaller than 5 MB.")

    image_array = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("The uploaded file is not a supported image.")

    height, width = image.shape[:2]
    if width < 100 or height < 100:
        raise ValueError("Image resolution is too small.")

    return image


def _represent(image: np.ndarray) -> list[float]:
    """Generate one embedding, requiring exactly one detectable face."""
    results = DeepFace.represent(
        img_path=image,
        model_name=MODEL_NAME,
        detector_backend=DETECTOR_BACKEND,
        enforce_detection=True,
        align=True,
        normalization="Facenet2018",
    )

    if len(results) != 1:
        raise ValueError("The image must contain exactly one face.")

    embedding = results[0].get("embedding")
    if not embedding:
        raise ValueError("Could not generate a face template.")

    vector = np.asarray(embedding, dtype=np.float32)

    if vector.ndim != 1 or not np.isfinite(vector).all():
        raise ValueError("Invalid face representation.")

    return vector.tolist()


def create_face_embedding(image_base64: str) -> list[float]:
    image = decode_image(image_base64)
    return _represent(image)


def cosine_distance(
    first: list[float],
    second: list[float],
) -> float:
    a = np.asarray(first, dtype=np.float32)
    b = np.asarray(second, dtype=np.float32)

    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("Stored face template is incompatible.")

    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0:
        raise ValueError("Invalid face template.")

    similarity = float(np.dot(a, b) / denominator)
    return 1.0 - similarity


def verify_face(
    submitted_image_base64: str,
    stored_embedding: list[float],
) -> tuple[bool, float]:
    submitted_embedding = create_face_embedding(submitted_image_base64)
    distance = cosine_distance(submitted_embedding, stored_embedding)

    return distance <= MAX_COSINE_DISTANCE, distance
