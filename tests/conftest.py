import importlib
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
for _path in (PROJECT_ROOT, WEB_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

REQUIRED_ENV_VARS = {
    "GOOGLE_API_KEY": "test-key",
    "SENDGRID_API_KEY": "test-key",
    "SENDGRID_SENDER": "test@example.com",
    "FIREBASE_CREDENTIALS_PATH": "test-credentials.json",
}


class FakeDoc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class FakeDocRef:
    def __init__(self, store, key):
        self._store = store
        self._key = key

    def get(self):
        return FakeDoc(self._store.get(self._key))

    def set(self, data):
        self._store[self._key] = dict(data)

    def update(self, data):
        self._store.setdefault(self._key, {}).update(data)


class FakeCollection:
    def __init__(self, store):
        self._store = store

    def document(self, key):
        return FakeDocRef(self._store, key)


class FakeDB:
    """Minimal in-memory stand-in for a Firestore client -- just enough
    (collection/document/get/set/update) to unit-test logic in
    database/firebase_client.py without touching real Firestore."""

    def __init__(self):
        self._collections = {}

    def collection(self, name):
        return FakeCollection(self._collections.setdefault(name, {}))


@pytest.fixture
def mocked_firebase_client(monkeypatch):
    """Imports database.firebase_client with Firebase Admin mocked out, and
    swaps its `db` for a FakeDB so usage-counter logic can be tested without
    real Firestore access."""
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)

    for module_name in list(sys.modules):
        if module_name.startswith("database.") or module_name == "config.config":
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    with patch("firebase_admin.credentials.Certificate", return_value=MagicMock()), \
         patch("firebase_admin.initialize_app", return_value=MagicMock()), \
         patch("firebase_admin.firestore.client", return_value=MagicMock()):
        module = importlib.import_module("database.firebase_client")

    module.db = FakeDB()
    yield module

    monkeypatch.delitem(sys.modules, "database.firebase_client", raising=False)


@pytest.fixture
def mocked_app_module(monkeypatch):
    """Imports web.app with every heavy/networked dependency mocked out:
    Firebase Admin (no real credentials/network), the Whisper STT model
    (no CUDA/download), and the Qwen+LoRA companion model (reuses the same
    from_pretrained-mocking pattern as tests/test_companion.py, so it
    degrades to MODEL_AVAILABLE = False instead of trying to load on GPU).
    Safe to import in any environment, including CI with no GPU/secrets.
    """
    import transformers

    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)

    for module_name in list(sys.modules):
        if module_name == "web.app" or module_name.startswith("database.") or module_name in (
            "config.config",
            "llm.companion",
            "web.auth",
        ):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    def broken_from_pretrained(*args, **kwargs):
        raise OSError("model loading disabled in tests")

    try:
        import kokoro  # noqa: F401
    except ImportError:
        fake_kokoro = types.ModuleType("kokoro")
        fake_kokoro.KPipeline = MagicMock(side_effect=RuntimeError("kokoro disabled in tests"))
        monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)

    with patch("firebase_admin.credentials.Certificate", return_value=MagicMock()), \
         patch("firebase_admin.initialize_app", return_value=MagicMock()), \
         patch("firebase_admin.firestore.client", return_value=MagicMock()), \
         patch("faster_whisper.WhisperModel", return_value=MagicMock()), \
         patch.object(transformers.AutoTokenizer, "from_pretrained", side_effect=broken_from_pretrained), \
         patch.object(transformers.AutoModelForCausalLM, "from_pretrained", side_effect=broken_from_pretrained), \
         patch("peft.PeftModel.from_pretrained", side_effect=broken_from_pretrained):
        app_module = importlib.import_module("web.app")

    yield app_module

    monkeypatch.delitem(sys.modules, "web.app", raising=False)
