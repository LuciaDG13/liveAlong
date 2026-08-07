from datetime import datetime


def test_usage_flag_pure_logic(mocked_firebase_client):
    fc = mocked_firebase_client
    today = datetime.now().strftime("%Y-%m-%d")

    assert fc._usage_flag({}) is False
    assert fc._usage_flag({"usage_today": {"date": today, "session_count": 1, "minutes": 5}}) is False
    assert fc._usage_flag({"usage_today": {"date": today, "session_count": 4, "minutes": 5}}) is True
    assert fc._usage_flag({"usage_today": {"date": today, "session_count": 1, "minutes": 46}}) is True
    # stale (yesterday's) counters must not trigger the flag
    assert fc._usage_flag({"usage_today": {"date": "2000-01-01", "session_count": 99, "minutes": 999}}) is False


def test_elapsed_minutes():
    from database.firebase_client import _elapsed_minutes

    now = datetime(2026, 1, 1, 10, 15, 30)
    assert _elapsed_minutes(None, now) is None
    assert _elapsed_minutes("not-a-time", now) is None
    assert _elapsed_minutes("10:00:30", now) == 15.0
    # clock skew / bad data should never produce a negative duration
    assert _elapsed_minutes("10:30:30", now) == 0


def test_usage_counters_bump_and_rollover(mocked_firebase_client):
    fc = mocked_firebase_client
    fc.db.collection("Profiles").document("child-a").set({"name": "Alice"})

    day1 = datetime(2026, 1, 1, 9, 0, 0)
    fc._bump_usage_session_count("child-a", day1)
    fc._bump_usage_session_count("child-a", datetime(2026, 1, 1, 9, 30, 0))
    stored = fc.db.collection("Profiles").document("child-a").get().to_dict()["usage_today"]
    assert stored["session_count"] == 2
    assert stored["date"] == "2026-01-01"

    fc._add_usage_minutes("child-a", datetime(2026, 1, 1, 9, 45, 0), 12.5)
    stored = fc.db.collection("Profiles").document("child-a").get().to_dict()["usage_today"]
    assert stored["minutes"] == 12.5

    # a new day resets the counters instead of accumulating further
    fc._bump_usage_session_count("child-a", datetime(2026, 1, 2, 8, 0, 0))
    stored = fc.db.collection("Profiles").document("child-a").get().to_dict()["usage_today"]
    assert stored["session_count"] == 1
    assert stored["date"] == "2026-01-02"
