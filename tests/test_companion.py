import importlib
import sys
from unittest.mock import patch

import transformers


def test_companion_falls_back_when_model_loading_fails(monkeypatch):
    def broken_from_pretrained(*args, **kwargs):
        raise OSError("The paging file is too small for this operation to complete")

    monkeypatch.delitem(sys.modules, "llm.companion", raising=False)

    with patch.object(transformers.AutoTokenizer, "from_pretrained", side_effect=broken_from_pretrained), \
         patch.object(transformers.AutoModelForCausalLM, "from_pretrained", side_effect=broken_from_pretrained), \
         patch("peft.PeftModel.from_pretrained", side_effect=broken_from_pretrained):
        module = importlib.import_module("llm.companion")

    assert module.MODEL_AVAILABLE is False
    assert module.run_session({"name": "Ari", "levelAutism": 2, "sensory": ["noise"], "interest": ["cars"], "language": "simple"}, "Play together", []) == "Sorry, I could not load the companion model right now. Please try again later."
