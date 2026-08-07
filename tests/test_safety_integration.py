FAKE_USERS = {
    "cookie-a": {"uid": "child-a", "role": "child"},
}


def fake_get_decoded_session():
    from flask import request
    return FAKE_USERS.get(request.cookies.get("session"))


def _prep_common_mocks(app_module, monkeypatch):
    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(app_module, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(
        app_module, "synthesize_speech_with_lip_sync", lambda text: {"audio": None, "mouthCues": []}
    )

    state = app_module.get_state("child-a")
    state["session_id"] = "session-a"
    state["user_profile"] = {"name": "Alice"}
    state["exercise"] = "exercise-a"
    state["conversation_history"] = []

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")
    return client


def test_crisis_message_overrides_reply_and_creates_alert(mocked_app_module, monkeypatch):
    app_module = mocked_app_module
    client = _prep_common_mocks(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "run_session", lambda *a, **k: "SHOULD NOT BE USED")
    monkeypatch.setattr(
        app_module, "classify_message",
        lambda text: {"risk_level": "crisis", "matched_rule": "test-phrase"},
    )

    created_alerts = []
    monkeypatch.setattr(
        app_module, "create_safety_alert",
        lambda user_id, session_id, excerpt, risk_level, matched_rule=None:
            created_alerts.append((user_id, session_id, excerpt, risk_level, matched_rule)),
    )

    resp = client.post("/message", json={"message": "concerning text"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["response"] == app_module.CRISIS_SAFE_RESPONSE
    assert data["response"] != "SHOULD NOT BE USED"
    assert len(created_alerts) == 1
    assert created_alerts[0][0] == "child-a"
    assert created_alerts[0][3] == "crisis"


def test_mild_distress_message_still_replies_normally_but_logs_alert(mocked_app_module, monkeypatch):
    app_module = mocked_app_module
    client = _prep_common_mocks(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "run_session", lambda *a, **k: "a normal companion reply")
    monkeypatch.setattr(
        app_module, "classify_message",
        lambda text: {"risk_level": "mild_distress", "matched_rule": None},
    )

    created_alerts = []
    monkeypatch.setattr(
        app_module, "create_safety_alert",
        lambda user_id, session_id, excerpt, risk_level, matched_rule=None:
            created_alerts.append(risk_level),
    )

    resp = client.post("/message", json={"message": "I feel sad"})

    assert resp.status_code == 200
    assert resp.get_json()["response"] == "a normal companion reply"
    assert created_alerts == ["mild_distress"]


def test_none_risk_message_does_not_create_alert(mocked_app_module, monkeypatch):
    app_module = mocked_app_module
    client = _prep_common_mocks(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "run_session", lambda *a, **k: "a normal companion reply")
    monkeypatch.setattr(
        app_module, "classify_message",
        lambda text: {"risk_level": "none", "matched_rule": None},
    )

    created_alerts = []
    monkeypatch.setattr(app_module, "create_safety_alert", lambda *a, **k: created_alerts.append(a))

    resp = client.post("/message", json={"message": "hello"})

    assert resp.status_code == 200
    assert resp.get_json()["response"] == "a normal companion reply"
    assert created_alerts == []
