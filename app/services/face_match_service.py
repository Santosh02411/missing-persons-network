"""Face-similarity scoring between a case's photo and a sighting's photo.

Deliberately built on classical computer vision (Haar cascade face
detection + per-cell Local Binary Pattern histograms, the same texture
descriptor behind OpenCV's own LBPHFaceRecognizer, just applied pairwise
instead of via a trained classifier) rather than a deep embedding model
(FaceNet/ArcFace/SFace). That's a real accuracy tradeoff, not a design
preference -- this app's deployment environment has no path to fetch
pretrained deep-learning weights at build time (the common ones are
distributed via Git LFS or third-party model hubs), while OpenCV's Haar
cascades and scikit-image's LBP implementation ship as ordinary pip
package data with no extra download step, so they're what's actually
reliable to run.

Everything below is intentionally isolated behind extract_descriptor() and
compare_descriptors() so a deep embedding model can be dropped in later
without touching sighting_service.py or the API route -- see the note on
extract_descriptor() for exactly what to change.
"""
import logging

import cv2
import numpy as np
from skimage.feature import local_binary_pattern

logger = logging.getLogger("app.face_match")

_FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

_FACE_SIZE = 128  # face crop is resized to this square before descriptor extraction
_GRID = 8  # face is divided into GRID x GRID cells for the per-cell LBP histogram
_LBP_POINTS = 8
_LBP_RADIUS = 1


def _decode_image(image_bytes: bytes) -> np.ndarray | None:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return image  # None if the bytes aren't a decodable image


def _largest_face(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Returns (x, y, w, h) of the largest detected face, or None. Case and
    sighting photos are typically a single clear portrait, so "largest
    detected face" is a reasonable stand-in for "the subject" without needing
    the caller to crop the photo themselves."""
    faces = _FACE_CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
    )
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: f[2] * f[3])


def extract_descriptor(image_bytes: bytes) -> np.ndarray | None:
    """Detects the largest face in the image and returns its texture
    descriptor (a normalized vector), or None if no face could be detected
    or the image couldn't be decoded.

    To upgrade this to a deep embedding model later (recommended if
    accuracy matters more than zero-setup deployment): replace this
    function's body with face detection + embedding via that model, keep
    the same (bytes) -> np.ndarray | None signature, and leave
    compare_descriptors() using cosine similarity -- deep embeddings compare
    the same way.
    """
    image = _decode_image(image_bytes)
    if image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    box = _largest_face(gray)
    if box is None:
        return None
    x, y, w, h = box
    face = gray[y : y + h, x : x + w]
    face = cv2.resize(face, (_FACE_SIZE, _FACE_SIZE))
    face = cv2.equalizeHist(face)  # normalizes lighting differences between photos

    cell = _FACE_SIZE // _GRID
    histograms = []
    for row in range(_GRID):
        for col in range(_GRID):
            patch = face[row * cell : (row + 1) * cell, col * cell : (col + 1) * cell]
            lbp = local_binary_pattern(patch, _LBP_POINTS, _LBP_RADIUS, method="uniform")
            n_bins = _LBP_POINTS + 2
            hist, _ = np.histogram(lbp, bins=n_bins, range=(0, n_bins), density=True)
            histograms.append(hist)

    descriptor = np.concatenate(histograms).astype(np.float32)
    norm = np.linalg.norm(descriptor)
    if norm > 0:
        descriptor = descriptor / norm
    return descriptor


def compare_descriptors(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two descriptors, clamped to [0, 1] -- both
    inputs are already L2-normalized by extract_descriptor(), so this is
    just their dot product."""
    score = float(np.dot(a, b))
    return max(0.0, min(1.0, score))


def match_faces(case_photo_bytes: bytes, sighting_photo_bytes: bytes) -> dict:
    """Top-level entry point used by sighting_service.create_sighting().
    Returns a dict rather than raising, since "couldn't detect a face" is
    an expected, non-error outcome (bad photo angle, group photo, etc.) that
    the caller should record as "no score available", not fail on.

    {"score": float 0..1 | None, "case_face_detected": bool, "sighting_face_detected": bool}
    """
    case_descriptor = extract_descriptor(case_photo_bytes)
    sighting_descriptor = extract_descriptor(sighting_photo_bytes)
    result = {
        "score": None,
        "case_face_detected": case_descriptor is not None,
        "sighting_face_detected": sighting_descriptor is not None,
    }
    if case_descriptor is not None and sighting_descriptor is not None:
        result["score"] = compare_descriptors(case_descriptor, sighting_descriptor)
    return result
