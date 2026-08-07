import importlib
import sys
from unittest.mock import patch

import pytest


def test_classifier_loads_and_predicts_known_classes():
    import llm.safety_classifier as sc
    assert sc.MODEL_AVAILABLE is True

    none_result = sc.classify_message("I played with my trains today")
    assert none_result["risk_level"] in ("none", "mild_distress")  # tiny model, not asserting exact label

    empty_result = sc.classify_message("")
    assert empty_result == {"risk_level": "none", "matched_rule": None}


def test_classifier_falls_back_when_model_missing(monkeypatch):
    monkeypatch.delitem(sys.modules, "llm.safety_classifier", raising=False)

    with patch("joblib.load", side_effect=OSError("model file missing")):
        module = importlib.import_module("llm.safety_classifier")

    assert module.MODEL_AVAILABLE is False
    assert module.classify_message("anything at all") == {"risk_level": "none", "matched_rule": None}

    monkeypatch.delitem(sys.modules, "llm.safety_classifier", raising=False)


def test_keyword_prefilter_overrides_ml_classification(monkeypatch):
    import llm.safety_classifier as sc

    monkeypatch.setattr(sc, "matches_crisis_keyword", lambda text: "test-phrase")
    result = sc.classify_message("this text is irrelevant, the keyword mock always matches")

    assert result == {"risk_level": "crisis", "matched_rule": "test-phrase"}


def test_crisis_keywords_list_is_currently_empty():
    """Documents the current (intentional) state: no mentor-reviewed crisis
    keywords exist yet. If this test starts failing because someone added
    keywords, make sure that was done WITH Dr Kanaga, not around her."""
    from llm.safety_classifier.keywords import CRISIS_KEYWORDS
    assert CRISIS_KEYWORDS == []
