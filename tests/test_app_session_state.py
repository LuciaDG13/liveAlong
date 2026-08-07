FAKE_USERS = {
    "cookie-a": {"uid": "child-a", "role": "child"},
    "cookie-b": {"uid": "child-b", "role": "child"},
}


def fake_get_decoded_session():
    from flask import request
    return FAKE_USERS.get(request.cookies.get("session"))


def test_get_state_is_isolated_per_user(mocked_app_module):
    app_module = mocked_app_module

    state_a = app_module.get_state("child-a")
    state_a["theme"] = "Waiting in line"
    state_b = app_module.get_state("child-b")

    assert state_b["theme"] is None
    assert app_module.get_state("child-a")["theme"] == "Waiting in line"

    app_module.clear_state("child-a")
    assert "child-a" not in app_module.active_sessions
    assert "child-b" in app_module.active_sessions


def test_message_route_does_not_leak_state_between_users(mocked_app_module, monkeypatch):
    app_module = mocked_app_module

    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(app_module, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(
        app_module, "synthesize_speech_with_lip_sync", lambda text: {"audio": None, "mouthCues": []}
    )
    monkeypatch.setattr(
        app_module, "run_session",
        lambda user_profile, exercise, history, today_emotion=None: f"reply-for-{user_profile['name']}",
    )

    state_a = app_module.get_state("child-a")
    state_a["session_id"] = "session-a"
    state_a["user_profile"] = {"name": "Alice"}
    state_a["exercise"] = "exercise-a"
    state_a["conversation_history"] = []

    state_b = app_module.get_state("child-b")
    state_b["session_id"] = "session-b"
    state_b["user_profile"] = {"name": "Bob"}
    state_b["exercise"] = "exercise-b"
    state_b["conversation_history"] = []

    client_a = app_module.app.test_client()
    client_a.set_cookie("session", "cookie-a")
    client_b = app_module.app.test_client()
    client_b.set_cookie("session", "cookie-b")

    resp_a = client_a.post("/message", json={"message": "hi"})
    resp_b = client_b.post("/message", json={"message": "hello"})

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.get_json()["response"] == "reply-for-Alice"
    assert resp_b.get_json()["response"] == "reply-for-Bob"

    # each user's history only ever saw their own messages
    assert all(msg["parts"] != "hello" for msg in state_a["conversation_history"])
    assert all(msg["parts"] != "hi" for msg in state_b["conversation_history"])
