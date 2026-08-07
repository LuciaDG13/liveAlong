from google.cloud.firestore_v1.base_query import FieldFilter
import firebase_admin
from firebase_admin import credentials, firestore, auth
from config.config import FIREBASE_CREDENTIALS_PATH, SENDGRID_API_KEY, SENDGRID_SENDER
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)

cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)

db = firestore.client()

# Defaults only -- these are a clinical/product judgment call, not an
# engineering constant. Get them reviewed/tuned with the psychologist mentor
# before relying on them for real usage decisions.
MAX_SESSIONS_PER_DAY = 3
MAX_MINUTES_PER_DAY = 45

def get_exercise(theme, LevelAutism):
    exercises_ref = db.collection("SocialStories")

    query = (
        exercises_ref
        .where(filter=FieldFilter("theme", "==", theme))
        .where(filter=FieldFilter("levelAutism", "==", LevelAutism))
        .limit(1)
    )
    
    results = query.get()
    
    if results:
        return results[0].to_dict()["story"]
    return None

def create_user_profile(profile_data, user_id=None):
    profile_ref = db.collection("Profiles").document(user_id) if user_id else db.collection("Profiles").document()
    profile_ref.set(profile_data)
    return profile_ref.id

def _usage_flag(profile_data):
    usage = profile_data.get("usage_today") or {}
    if usage.get("date") != datetime.now().strftime("%Y-%m-%d"):
        return False
    return (
        usage.get("session_count", 0) > MAX_SESSIONS_PER_DAY
        or usage.get("minutes", 0) > MAX_MINUTES_PER_DAY
    )


def get_all_profiles():
    profiles_ref = db.collection("Profiles").where(filter=FieldFilter("role", "==", "child"))
    result = []
    for profile in profiles_ref.stream():
        data = profile.to_dict() or {}
        result.append({
            "id": profile.id,
            "name": data.get("name"),
            "usage_flag": _usage_flag(data),
            "alert_count": len(get_unacknowledged_alerts(profile.id)),
        })
    return result


def get_profile_by_id(profile_id):
    profile_ref = db.collection("Profiles").document(profile_id)
    profile_doc = profile_ref.get()
    if not profile_doc.exists:
        return None

    profile = profile_doc.to_dict() or {}
    profile["id"] = profile_id
    return profile


def get_sessions_for_user(user_id):
    sessions_ref = db.collection("Sessions").where(filter=FieldFilter("user_id", "==", user_id))
    sessions = []

    for session_doc in sessions_ref.stream():
        session_data = session_doc.to_dict() or {}
        session_data["id"] = session_doc.id

        messages = []
        for message_doc in session_doc.reference.collection("messages").stream():
            message = message_doc.to_dict() or {}
            message["id"] = message_doc.id
            messages.append(message)

        messages.sort(key=lambda message: str(message.get("timeStamp", "")))
        session_data["messages"] = messages
        sessions.append(session_data)

    sessions.sort(key=lambda session: (
        str(session.get("date", "")),
        str(session.get("end_time", ""))
    ))
    return sessions


def create_session(user_id, theme):
    now = datetime.now()
    session_ref = db.collection("Sessions").document()
    session_ref.set({
        "user_id": user_id,
        "theme": theme,
        "date": now.strftime("%Y-%m-%d"),
        "start_time": now.strftime("%H:%M:%S"),
        "status": "en cours"
    })

    _bump_usage_session_count(user_id, now)

    print(f"Session crée: {session_ref.id}")
    return session_ref.id

def save_message(session_id, role, content):
    session_ref = db.collection("Sessions").document(session_id)
    message_ref = session_ref.collection("messages")
    message_ref.add({
        "role": role,
        "content": content,
        "timeStamp": datetime.now().strftime("%H:%M:%S")
    })

def close_session(session_id, ended_by="child"):
    now = datetime.now()
    session_ref = db.collection("Sessions").document(session_id)
    session_data = session_ref.get().to_dict() or {}

    session_ref.update({
        "status": "terminee",
        "end_time": now.strftime("%H:%M:%S"),
        "ended_by": ended_by
    })

    elapsed_minutes = _elapsed_minutes(session_data.get("start_time"), now)
    if session_data.get("user_id") and elapsed_minutes is not None:
        _add_usage_minutes(session_data["user_id"], now, elapsed_minutes)


def _elapsed_minutes(start_time_str, now):
    if not start_time_str:
        return None
    try:
        start_dt = datetime.combine(now.date(), datetime.strptime(start_time_str, "%H:%M:%S").time())
    except ValueError:
        return None
    return max((now - start_dt).total_seconds() / 60, 0)


def get_usage_today(user_id, now=None):
    now = now or datetime.now()
    profile = db.collection("Profiles").document(user_id).get().to_dict() or {}
    usage = profile.get("usage_today") or {}
    today = now.strftime("%Y-%m-%d")
    if usage.get("date") != today:
        return {"date": today, "session_count": 0, "minutes": 0}
    return usage


def _bump_usage_session_count(user_id, now):
    usage = get_usage_today(user_id, now)
    usage["date"] = now.strftime("%Y-%m-%d")
    usage["session_count"] = usage.get("session_count", 0) + 1
    db.collection("Profiles").document(user_id).update({"usage_today": usage})


def _add_usage_minutes(user_id, now, minutes):
    usage = get_usage_today(user_id, now)
    usage["date"] = now.strftime("%Y-%m-%d")
    usage["minutes"] = usage.get("minutes", 0) + minutes
    db.collection("Profiles").document(user_id).update({"usage_today": usage})

def update_profile_insights(user_id, theme, insights, consolidated_profile):
    if not insights:
        return
    
    insights["date"] = datetime.now().strftime("%Y-%m-%d")
    insights["theme"] = theme
    
    profile_ref = db.collection("Profiles").document(user_id)
    profile = profile_ref.get().to_dict()
    
    existing_insights = profile.get("session_insights", [])
    existing_insights.append(insights)
    
    consolidated_profile["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    
    profile_ref.update({
        "session_insights": existing_insights,
        "consolidated_profile": consolidated_profile
    })
    print(f"Profil mis à jour avec les insights et le profil consolidé")

def send_temp_password(email, password):
    message = Mail(
        from_email=SENDGRID_SENDER,
        to_emails=email,
        subject="Your LiveAlong Account",
        html_content=f"<p>Your temporary password is: <strong>{password}</strong></p>"
    )
    try:
        sg.send(message)
        print(f"Temporary password email sent to {email}")
        return True
    except Exception as e:
        print(f"Error sending email to {email}: {e.body}")
        return None

def create_auth_account(email, password):
    try:
        user = auth.create_user(
            email=email,
            password=password
        )
        auth.set_custom_user_claims(user.uid, {'role': 'child'})
        print(f"User created with the UID: {user.uid}")
        return user.uid
    except Exception as e:
        print(f"Error during the creation of the user: {e}")
        return None

def update_avatar(user_id, avatar_svg, options):
    db.collection("Profiles").document(user_id).update({
        "avatar_svg": avatar_svg,
        "avatar_options": options,
        "avatar_customized": True
    })

def delete_child_profile(user_id):
    auth.delete_user(user_id)
    db.collection("Profiles").document(user_id).delete()

def save_emotion_entry(user_id, session_id, emotion):
    db.collection("EmotionEntries").add({
        "user_id": user_id,
        "session_id": session_id,
        "emotion": emotion,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def get_emotion_entries_for_user(user_id):
    entries_ref = db.collection("EmotionEntries").where(filter=FieldFilter("user_id", "==", user_id))
    entries = []
    for doc in entries_ref.stream():
        entry = doc.to_dict()
        entry["id"] = doc.id
        entries.append(entry)
    entries.sort(key=lambda e: str(e.get("timestamp", "")))
    return entries

def get_exercises_by_level(level_autism):
    stories_ref = db.collection("SocialStories").where(filter=FieldFilter("levelAutism", "==", level_autism))
    stories = []
    for doc in stories_ref.stream():
        story = doc.to_dict()
        story["id"] = doc.id
        stories.append(story)
    return stories

def create_safety_alert(user_id, session_id, message_excerpt, risk_level, matched_rule=None):
    alert_ref = db.collection("SafetyAlerts").document()
    alert_ref.set({
        "user_id": user_id,
        "session_id": session_id,
        "message_excerpt": message_excerpt,
        "risk_level": risk_level,
        "matched_rule": matched_rule,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "acknowledged": False,
        "acknowledged_by": None,
        "acknowledged_at": None,
    })
    return alert_ref.id

def get_unacknowledged_alerts(user_id=None):
    alerts_ref = db.collection("SafetyAlerts").where(filter=FieldFilter("acknowledged", "==", False))
    if user_id:
        alerts_ref = alerts_ref.where(filter=FieldFilter("user_id", "==", user_id))
    alerts = []
    for doc in alerts_ref.stream():
        alert = doc.to_dict() or {}
        alert["id"] = doc.id
        alerts.append(alert)
    alerts.sort(key=lambda a: str(a.get("timestamp", "")))
    return alerts

def acknowledge_alert(alert_id, acknowledged_by):
    db.collection("SafetyAlerts").document(alert_id).update({
        "acknowledged": True,
        "acknowledged_by": acknowledged_by,
        "acknowledged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })