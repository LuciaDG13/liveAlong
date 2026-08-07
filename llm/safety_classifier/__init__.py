"""Distress/crisis text classifier -- see TAXONOMY_DRAFT.md before touching
this module's behavior.

Public API:
    classify_message(text) -> {"risk_level": "none" | "mild_distress" | "crisis",
                                "matched_rule": str | None}

Two layers, checked in order:
1. Deterministic keyword pre-filter (keywords.py) -- currently empty/inert,
   pending mentor-reviewed phrases.
2. ML classifier (TF-IDF + logistic regression, trained by train.py) --
   currently trained only on "none"/"mild_distress" (see data/README.md),
   so it cannot currently predict "crisis" either.

Neither layer can currently detect a real crisis. This module implements
the mechanism end-to-end (and is safe to integrate/test); real detection
capability requires mentor-reviewed keywords and training data.

Fails open: if the model can't be loaded, classify_message() returns
"none" rather than blocking the app. That's a deliberate simplification
given there is no real crisis-detection capability yet either way -- once
real detection exists, whether a load failure should fail open or closed
is worth a separate discussion.
"""

import os

import joblib

from .keywords import matches_crisis_keyword

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.joblib")

MODEL_AVAILABLE = False
_pipeline = None

try:
    _pipeline = joblib.load(MODEL_PATH)
    MODEL_AVAILABLE = True
except Exception as exc:
    print(f"Unable to load safety classifier model: {exc}")
    MODEL_AVAILABLE = False


def classify_message(text):
    if not text or not text.strip():
        return {"risk_level": "none", "matched_rule": None}

    matched_rule = matches_crisis_keyword(text)
    if matched_rule:
        return {"risk_level": "crisis", "matched_rule": matched_rule}

    if not MODEL_AVAILABLE:
        return {"risk_level": "none", "matched_rule": None}

    try:
        predicted = str(_pipeline.predict([text])[0])
    except Exception as exc:
        print(f"Error while classifying message: {exc}")
        return {"risk_level": "none", "matched_rule": None}

    return {"risk_level": predicted, "matched_rule": None}
