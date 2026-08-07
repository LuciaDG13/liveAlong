FAKE_USERS = {
    "cookie-a": {"uid": "child-a", "role": "child"},
}


def fake_get_decoded_session():
    from flask import request
    return FAKE_USERS.get(request.cookies.get("session"))


def _prep(app_module, monkeypatch):
    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(app_module, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(
        app_module, "synthesize_speech_with_lip_sync", lambda text: {"audio": None, "mouthCues": []}
    )
    monkeypatch.setattr(app_module, "classify_message", lambda text: {"risk_level": "none", "matched_rule": None})

    state = app_module.get_state("child-a")
    state["session_id"] = "session-a"
    state["user_profile"] = {"name": "Alice"}
    state["exercise"] = "exercise-a"
    state["theme"] = "Waiting in line"
    state["conversation_history"] = []

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")
    return client


def test_companion_end_tag_ends_session_and_strips_tag(mocked_app_module, monkeypatch):
    app_module = mocked_app_module
    client = _prep(app_module, monkeypatch)

    monkeypatch.setattr(
        app_module, "run_session",
        lambda *a, **k: "That's okay, we can continue another time. See you soon!\n<<END_EXERCISE>>",
    )

    finalize_calls = []
    monkeypatch.setattr(
        app_module, "finalize_session",
        lambda user_id, state, ended_by="child": finalize_calls.append((user_id, ended_by)),
    )

    resp = client.post("/message", json={"message": "I don't want to continue"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["session_ended"] is True
    assert "<<END_EXERCISE>>" not in data["response"]
    assert data["response"] == "That's okay, we can continue another time. See you soon!"
    assert finalize_calls == [("child-a", "companion")]


def test_normal_reply_does_not_end_session(mocked_app_module, monkeypatch):
    app_module = mocked_app_module
    client = _prep(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "run_session", lambda *a, **k: "Let's keep going, you're doing great!")

    finalize_calls = []
    monkeypatch.setattr(
        app_module, "finalize_session",
        lambda user_id, state, ended_by="child": finalize_calls.append((user_id, ended_by)),
    )

    resp = client.post("/message", json={"message": "okay let's continue"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["session_ended"] is False
    assert data["response"] == "Let's keep going, you're doing great!"
    assert finalize_calls == []
    assert "child-a" in app_module.active_sessions


def test_close_session_records_ended_by(mocked_firebase_client):
    fc = mocked_firebase_client
    fc.db.collection("Sessions").document("s1").set({"user_id": "child-a", "start_time": "10:00:00"})

    fc.close_session("s1", ended_by="companion")

    stored = fc.db.collection("Sessions").document("s1").get().to_dict()
    assert stored["ended_by"] == "companion"
    assert stored["status"] == "terminee"
