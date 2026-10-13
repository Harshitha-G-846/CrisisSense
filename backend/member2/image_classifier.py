"""
image_classifier.py — Member 2
Visual disaster classification using EfficientNet-B0.

Trained on sarthaktandulje/disaster-damage-5class (Kaggle).
Classes: ['earthquake', 'fire', 'flood', 'landslide', 'normal', 'smoke']
Input: 224x224 RGB

Produces EvidenceItem objects for fusion.

IMPORTANT: This model is for research and prototyping only.
It must NOT be used as the sole decision-maker in emergency response.
Human verification is required.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import List, Optional, Union

import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "models", "disaster_model_6class.pth")
)

# Confidence threshold below which we do NOT emit a class claim.
CONFIDENCE_THRESHOLD = 0.60

# The class we treat as "no disaster detected."
NORMAL_CLASS = "normal"

# Cache
_cached_model = None
_cached_classes: Optional[List[str]] = None
_cached_device: Optional[torch.device] = None


# ---------------------------------------------------------------------------
# Model Loading (lazy)
# ---------------------------------------------------------------------------

def _load_model():
    """Load the EfficientNet-B0 6-class disaster classifier (lazy, cached)."""
    global _cached_model, _cached_classes, _cached_device

    if _cached_model is not None:
        return _cached_model, _cached_classes, _cached_device

    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(
            f"Disaster classifier weights not found at: {MODEL_PATH}"
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(MODEL_PATH, map_location=device, weights_only=False)

    state_dict = checkpoint.get("model_state_dict", checkpoint)
    class_names = list(checkpoint.get("class_names", []))

    if not class_names:
        raise ValueError("Checkpoint has no 'class_names'. Cannot determine class order.")

    model = models.efficientnet_b0(weights=None)
    model.classifier[1] = nn.Linear(
        model.classifier[1].in_features, len(class_names)
    )
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    _cached_model = model
    _cached_classes = class_names
    _cached_device = device
    return _cached_model, _cached_classes, _cached_device


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

_preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_model_available() -> bool:
    """Return True if the .pth file exists."""
    return os.path.isfile(MODEL_PATH)


def classify_image(
    image_input: Union[str, os.PathLike, Image.Image],
    reference_date: Optional[date] = None,
) -> List[EvidenceItem]:
    """
    Classify an image for disaster type.

    Emits EvidenceItem objects for:
      - A high-confidence non-normal disaster (fire/flood/earthquake/landslide/smoke)
      - A high-confidence "normal" (non-crisis) scene
      - Low confidence (NEUTRAL)
      - Errors (NEUTRAL)
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    # ---- Load image ----
    try:
        if isinstance(image_input, Image.Image):
            img = image_input.convert("RGB")
        elif isinstance(image_input, (str, os.PathLike)):
            img = Image.open(image_input).convert("RGB")
        else:
            return [_neutral("Invalid image input type")]
    except Exception as exc:
        return [_neutral(f"Could not load image: {exc}")]

    # ---- Load model ----
    try:
        model, class_names, device = _load_model()
    except FileNotFoundError as exc:
        return [_neutral(str(exc))]
    except Exception as exc:
        return [_neutral(f"Model loading failed: {exc}")]

    # ---- Inference ----
    try:
        tensor = _preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1)[0]

        top_idx = int(torch.argmax(probs).item())
        top_class = class_names[top_idx]
        top_prob = float(probs[top_idx].item())

        probabilities = {
            class_names[i]: round(float(probs[i].item()), 4)
            for i in range(len(class_names))
        }
    except Exception as exc:
        return [_neutral(f"Inference failed: {exc}")]

    # ---- Decide what to emit ----

    # Case 1: High-confidence NORMAL scene — explicit non-crisis evidence
    if top_class == NORMAL_CLASS and top_prob >= CONFIDENCE_THRESHOLD:
        return [
            EvidenceItem(
                source=EvidenceSource.IMAGE_NORMAL_CLASSIFICATION,
                finding=(
                    f"Image classified as a normal (non-disaster) scene "
                    f"(confidence {top_prob:.2f})."
                ),
                polarity=EvidencePolarity.NEUTRAL,
                weight=round(min(top_prob, 0.85), 4),
                details={
                    "predicted_class": top_class,
                    "confidence": round(top_prob, 4),
                    "all_probabilities": probabilities,
                    "note": "Normal scene is not evidence of a crisis.",
                },
            )
        ]

    # Case 2: Low confidence overall — NEUTRAL
    if top_prob < CONFIDENCE_THRESHOLD:
        return [
            EvidenceItem(
                source=EvidenceSource.IMAGE_CLASSIFICATION,
                finding=(
                    f"Image classification low confidence "
                    f"('{top_class}' at {top_prob:.2f} < {CONFIDENCE_THRESHOLD}). "
                    f"No strong visual disaster signal."
                ),
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.20,
                details={
                    "predicted_class": top_class,
                    "confidence": round(top_prob, 4),
                    "all_probabilities": probabilities,
                },
            )
        ]

    # Case 3: High-confidence non-normal disaster class
    return [
        EvidenceItem(
            source=EvidenceSource.IMAGE_CLASSIFICATION,
            finding=(
                f"Visual analysis suggests {top_class.title()} "
                f"(confidence {top_prob:.2f})."
            ),
            polarity=EvidencePolarity.NEUTRAL,
            weight=round(min(top_prob, 0.85), 4),
            details={
                "predicted_class": top_class,
                "confidence": round(top_prob, 4),
                "all_probabilities": probabilities,
                "note": (
                    "Visual class is informational. Currentness requires "
                    "separate temporal evidence."
                ),
            },
        )
    ]


def _neutral(finding: str) -> EvidenceItem:
    return EvidenceItem(
        source=EvidenceSource.IMAGE_CLASSIFICATION,
        finding=finding,
        polarity=EvidencePolarity.NEUTRAL,
        weight=0.10,
        details={"error": True},
    )