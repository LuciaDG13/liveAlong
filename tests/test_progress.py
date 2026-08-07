FAKE_USERS = {
    "cookie-a": {"uid": "child-a", "role": "child"},
}


def fake_get_decoded_session():
    from flask import request
    return FAKE_USERS.get(request.cookies.get("session"))


def test_progress_groups_themes_by_practice_count(mocked_app_module, monkeypatch):
    app_module = mocked_app_module

    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)

    monkeypatch.setattr(
        app_module, "get_user_profile",
        lambda uid: {"consolidated_profile": {"resolved_difficulties": ["waiting turns", "asking for help"]}},
    )
    monkeypatch.setattr(
        app_module, "get_sessions_for_user",
        lambda uid: (
            [{"theme": "Waiting in line"}] * 4  # >= CONFIDENT_SESSION_COUNT
            + [{"theme": "Sharing toys"}] * 2    # >= PRACTICING_SESSION_COUNT
            + [{"theme": "Change of plans"}]     # just started
            + [{"theme": None}]                  # missing theme, dropped
        ),
    )

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")

    resp = client.get("/api/progress")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["themes_by_status"] == {
        "confident": ["Waiting in line"],
        "practicing": ["Sharing toys"],
        "started": ["Change of plans"],
    }
    assert data["skills_growing"] == ["waiting turns", "asking for help"]


def test_progress_confident_understanding_overrides_low_count(mocked_app_module, monkeypatch):
    """Her example: a theme the child was immediately comfortable with should
    show as confident even after a single session."""
    app_module = mocked_app_module

    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(
        app_module, "get_user_profile",
        lambda uid: {
            "consolidated_profile": {},
            "session_insights": [
                {"theme": "Personal space", "understanding": "confident"},
            ],
        },
    )
    monkeypatch.setattr(app_module, "get_sessions_for_user", lambda uid: [{"theme": "Personal space"}])

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")

    data = client.get("/api/progress").get_json()
    assert data["themes_by_status"]["confident"] == ["Personal space"]


def test_progress_struggling_understanding_caps_status_despite_high_count(mocked_app_module, monkeypatch):
    """Her other example: a theme practiced a lot but still poorly grasped
    should not be shown as confident just because of repetition."""
    app_module = mocked_app_module

    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(
        app_module, "get_user_profile",
        lambda uid: {
            "consolidated_profile": {},
            "session_insights": [
                {"theme": "Change of plans", "understanding": "struggling"},
                {"theme": "Change of plans", "understanding": "struggling"},
            ],
        },
    )
    monkeypatch.setattr(
        app_module, "get_sessions_for_user",
        lambda uid: [{"theme": "Change of plans"}] * 6,  # well above CONFIDENT_SESSION_COUNT
    )

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")

    data = client.get("/api/progress").get_json()
    assert data["themes_by_status"] == {"confident": [], "practicing": ["Change of plans"], "started": []}


def test_progress_single_session_non_confident_understanding_stays_started(mocked_app_module, monkeypatch):
    app_module = mocked_app_module

    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(
        app_module, "get_user_profile",
        lambda uid: {
            "consolidated_profile": {},
            "session_insights": [{"theme": "Sharing toys", "understanding": "developing"}],
        },
    )
    monkeypatch.setattr(app_module, "get_sessions_for_user", lambda uid: [{"theme": "Sharing toys"}])

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")

    data = client.get("/api/progress").get_json()
    assert data["themes_by_status"]["started"] == ["Sharing toys"]


def test_progress_uses_latest_understanding_not_earliest(mocked_app_module, monkeypatch):
    app_module = mocked_app_module

    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(
        app_module, "get_user_profile",
        lambda uid: {
            "consolidated_profile": {},
            "session_insights": [
                {"theme": "Waiting in line", "understanding": "struggling"},
                {"theme": "Waiting in line", "understanding": "confident"},
            ],
        },
    )
    monkeypatch.setattr(app_module, "get_sessions_for_user", lambda uid: [{"theme": "Waiting in line"}] * 2)

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")

    data = client.get("/api/progress").get_json()
    assert data["themes_by_status"]["confident"] == ["Waiting in line"]


def test_progress_handles_missing_profile_gracefully(mocked_app_module, monkeypatch):
    app_module = mocked_app_module

    monkeypatch.setattr("web.auth.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr("web.app.get_decoded_session", fake_get_decoded_session)
    monkeypatch.setattr(app_module, "get_user_profile", lambda uid: None)
    monkeypatch.setattr(app_module, "get_sessions_for_user", lambda uid: [])

    client = app_module.app.test_client()
    client.set_cookie("session", "cookie-a")

    resp = client.get("/api/progress")

    assert resp.status_code == 200
    assert resp.get_json() == {
        "themes_by_status": {"confident": [], "practicing": [], "started": []},
        "skills_growing": [],
    }
