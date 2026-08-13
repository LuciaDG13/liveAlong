import sys
import os
import json
from collections import Counter
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firebase_admin import auth
from flask import Flask, render_template, request, jsonify, make_response, send_file, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from database.firebase_client import create_session, save_message, close_session, update_profile_insights, create_user_profile, create_auth_account, send_temp_password, get_all_profiles, get_profile_by_id, get_sessions_for_user, update_avatar, delete_child_profile, save_emotion_entry, get_emotion_entries_for_user, get_exercises_by_level, get_usage_today, MAX_SESSIONS_PER_DAY, MAX_MINUTES_PER_DAY, create_safety_alert, get_unacknowledged_alerts, acknowledge_alert
from llm.safety_classifier import classify_message
from user_profiles.user_profile import get_user_profile
from llm.companion import run_session, analyze_session, consolidate_profile
from llm.lip_sync import synthesize_speech_with_lip_sync
import secrets
from web.auth import login_required, page_login_required, get_decoded_session
from datetime import timedelta, datetime
from faster_whisper import WhisperModel
from avatar_service import generate_avatar_svg
from recommendation_service import recommend_exercise, RECENT_THEME_WINDOW, NEGATIVE_EMOTIONS


SESSION_EXPIRES_IN= timedelta(days=3)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
whisper_model = WhisperModel("base.en", device="cuda", compute_type="float16")

app = Flask(__name__)


def rate_limit_key():
    decoded = get_decoded_session()
    if decoded and decoded.get("uid"):
        return decoded["uid"]
    return get_remote_address()


limiter = Limiter(key_func=rate_limit_key, app=app)

active_sessions = {}

def get_state(uid):
    return active_sessions.setdefault(uid, {
        "session_id": None,
        "user_profile": None,
        "exercise": None,
        "theme": None,
        "conversation_history": [],
        "today_emotion": None
    })

def clear_state(uid):
    active_sessions.pop(uid, None)

END_EXERCISE_TAG = "<<END_EXERCISE>>"


def finalize_session(user_id, state, ended_by="child"):
    close_session(state["session_id"], ended_by=ended_by)
    insights = analyze_session(state["user_profile"], state["conversation_history"], state["theme"])
    consolidated_profile = consolidate_profile(state["user_profile"], insights)
    update_profile_insights(user_id, state["theme"], insights, consolidated_profile)
    clear_state(user_id)

# DRAFT PLACEHOLDER -- NOT APPROVED FOR USE WITH REAL CHILDREN.
# This text must be written and approved by Dr Kanaga before this feature
# is used with any real child. It exists only so the override mechanism
# below is demonstrable/testable. See llm/safety_classifier/TAXONOMY_DRAFT.md.
CRISIS_SAFE_RESPONSE = (
    "[DRAFT PLACEHOLDER -- not an approved response. If you are seeing "
    "this in a real session, stop and replace it with mentor-approved text.]"
)


def check_message_safety(user_id, session_id, user_input):
    """Classifies user_input and logs a SafetyAlert if it's not "none".
    Returns a response text to use INSTEAD of the companion's normal reply
    when risk_level is "crisis", or None otherwise (normal reply proceeds)."""
    result = classify_message(user_input)
    risk_level = result["risk_level"]
    if risk_level == "none":
        return None

    create_safety_alert(user_id, session_id, user_input, risk_level, result.get("matched_rule"))

    if risk_level == "crisis":
        return CRISIS_SAFE_RESPONSE
    return None

@app.route("/")
def home():
    response = make_response(render_template("login.html"))
    response.set_cookie(
        "session",
        "",
        expires=0,
        httponly=True,
        samesite="Strict",
        path="/"
    )
    return response

@app.route("/child_interface")
@page_login_required
def child_interface(current_user):
    if (current_user["role"]!="child"):
        return jsonify({"error": "Unauthorized"}), 403
    return render_template("child.html")

@app.route("/therapist")
@page_login_required
def therapist(current_user):
    if (current_user["role"] != "therapist"):
        return jsonify({"error": "Unauthorized"}), 403
    return render_template("therapist.html")

@app.route("/start", methods=["POST"])
@limiter.limit("10/minute")
@login_required
def start(current_user):
    if (current_user["role"] != "child"):
        return jsonify({"error": "Unauthorized"}), 403
    user_id = current_user["uid"]
    
    today_emotion = (request.json or {}).get("emotion")

    user_profile = get_user_profile(user_id)
    all_stories = get_exercises_by_level(user_profile["levelAutism"])

    sessions = get_sessions_for_user(user_id)
    recent_themes = [s.get("theme") for s in sessions[-RECENT_THEME_WINDOW:]]
    theme_counts = Counter(s.get("theme") for s in sessions if s.get("theme"))

    emotions = get_emotion_entries_for_user(user_id)
    session_theme_by_id = {s["id"]: s.get("theme") for s in sessions}
    negative_emotion_themes = {
        session_theme_by_id.get(e.get("session_id"))
        for e in emotions
        if e.get("emotion") in NEGATIVE_EMOTIONS and session_theme_by_id.get(e.get("session_id"))
    }

    chosen_story = recommend_exercise(
        all_stories, user_profile, recent_themes, negative_emotion_themes,
        theme_counts=theme_counts, today_emotion=today_emotion
    )
    if not chosen_story:
        return jsonify({"error": "No exercise available for this level"}), 500

    theme = chosen_story["theme"]
    exercise = chosen_story["story"]
    session_id = create_session(user_id, theme)

    usage_today = get_usage_today(user_id)
    usage_nudge = (
        usage_today.get("session_count", 0) > MAX_SESSIONS_PER_DAY
        or usage_today.get("minutes", 0) > MAX_MINUTES_PER_DAY
    )

    state = get_state(user_id)
    state["session_id"] = session_id
    state["user_profile"] = user_profile
    state["exercise"] = exercise
    state["theme"] = theme
    state["conversation_history"] = []
    state["today_emotion"] = today_emotion

    first_response = run_session(user_profile, exercise, [], today_emotion)
    save_message(session_id, "assistant", first_response)
    state["conversation_history"].append({"role": "assistant", "parts": first_response})

    speech = synthesize_speech_with_lip_sync(first_response)
    return jsonify({
    "response": first_response,
    "audio": speech["audio"],
    "mouthCues": speech["mouthCues"],
    "avatar_svg": user_profile.get("avatar_svg"),
    "usage_nudge": usage_nudge
    })

@app.route("/message", methods=["POST"])
@limiter.limit("30/minute")
@login_required
def message(current_user):
    if (current_user["role"] != "child"):
        return jsonify({"error": "Unauthorized"}), 403

    state = get_state(current_user["uid"])
    user_input = request.json.get("message")

    save_message(state["session_id"], "assistant", user_input)
    state["conversation_history"].append({"role": "assistant", "parts": user_input})

    safety_override = check_message_safety(current_user["uid"], state["session_id"], user_input)
    if safety_override:
        response_text = safety_override
    else:
        response_text = run_session(
            state["user_profile"],
            state["exercise"],
            state["conversation_history"],
            state["today_emotion"]
        )

    session_ended = END_EXERCISE_TAG in response_text
    if session_ended:
        response_text = response_text.replace(END_EXERCISE_TAG, "").strip()

    save_message(state["session_id"], "assistant", response_text)
    state["conversation_history"].append({"role": "assistant", "parts": response_text})

    speech = synthesize_speech_with_lip_sync(response_text)

    if session_ended:
        finalize_session(current_user["uid"], state, ended_by="companion")

    return jsonify({
        "user_input": user_input,
        "response": response_text,
        "audio": speech["audio"],
        "mouthCues": speech["mouthCues"],
        "session_ended": session_ended
    })

@app.route("/message_voice", methods=["POST"])
@limiter.limit("30/minute")
@login_required
def message_voice(current_user):
    if current_user["role"] != "child":
        return jsonify({"error": "Unauthorized"}), 403

    if 'audio' not in request.files:
        return jsonify({"error": "No audio file received"}), 400

    state = get_state(current_user["uid"])

    # 1. Récupération et sauvegarde de l'audio du téléphone
    audio_file = request.files['audio']
    input_path = "input.wav"
    audio_file.save(input_path)

    # 2. Transcription Whisper (Audio -> Texte anglais)
    segments, _ = whisper_model.transcribe(input_path, language="en")
    user_input = "".join([segment.text for segment in segments])

    # 3. Ton système de session et d'historique natif
    save_message(state["session_id"], "user", user_input)
    state["conversation_history"].append({"role": "user", "parts": user_input})

    # 4. TON LLM ADAPTÉ (Inchangé)
    safety_override = check_message_safety(current_user["uid"], state["session_id"], user_input)
    if safety_override:
        response_text = safety_override
    else:
        response_text = run_session(
            state["user_profile"],
            state["exercise"],
            state["conversation_history"],
            state["today_emotion"]
        )

    session_ended = END_EXERCISE_TAG in response_text
    if session_ended:
        response_text = response_text.replace(END_EXERCISE_TAG, "").strip()

    save_message(state["session_id"], "assistant", response_text)
    state["conversation_history"].append({"role": "assistant", "parts": response_text})

    speech = synthesize_speech_with_lip_sync(response_text)

    if session_ended:
        finalize_session(current_user["uid"], state, ended_by="companion")

    return jsonify({
        "user_input": user_input,
        "response": response_text,
        "audio": speech["audio"],
        "mouthCues": speech["mouthCues"],
        "session_ended": session_ended
    })

@app.route("/end", methods=["POST"])
@limiter.limit("10/minute")
@login_required
def end(current_user):
    if (current_user["role"] != "child"):
        return jsonify({"error": "Unauthorized"}), 403

    user_id = current_user["uid"]
    state = get_state(user_id)

    finalize_session(user_id, state, ended_by="child")

    farewell_text = "See you later!"
    speech = synthesize_speech_with_lip_sync(farewell_text)

    return jsonify({
    "status": "session terminée",
    "response": farewell_text,
    "audio": speech["audio"],
    "mouthCues": speech["mouthCues"]
})

@app.route("/therapist/create_profile", methods=["GET", "POST"])
@limiter.limit("5/minute")
@login_required
def create_profile(current_user):
    if current_user["role"] != "therapist":
        return jsonify({"error": "Unauthorized"}), 403
    if request.method == "GET":
        return render_template("creation-profile.html")
    
    profile_data = request.json
    if profile_data.get("parental-consent") != "true":
        return jsonify({"error": "Parental/guardian consent is required"}), 400

    mapped_data = {
        "role": "child",
        "consent_given": True,
        "consent_timestamp": datetime.now().isoformat(),
        "name": profile_data.get("name"),
        "date_of_birth": profile_data.get("date_of_birth"),
        "gender": profile_data.get("gender"),
        "pronoun": profile_data.get("pronoun"),
        "communication-type": profile_data.get("communication-type"),
        "language-level": profile_data.get("language-level"),
        "levelAutism": int(profile_data.get("levelAutism")) if profile_data.get("levelAutism") else None,
        "interests": profile_data.get("interests"),
        "sensory-auditory": profile_data.get("sensory-auditory"),
        "sensory-visual": profile_data.get("sensory-visual"),
        "sensory-tactile": profile_data.get("sensory-tactile"),
        "sensory-olfactory": profile_data.get("sensory-olfactory"),
        "sensory-gustatory": profile_data.get("sensory-gustatory"),
        "soothing": profile_data.get("soothing"),
        "physical-contact": profile_data.get("physical-contact"),
        "clinical-context": profile_data.get("clinical-context"),
        "triggers": profile_data.get("triggers"),
        "email": profile_data.get("email")
    }

    avatar_options_raw = profile_data.get("avatar-options")
    avatar_options = json.loads(avatar_options_raw) if avatar_options_raw else {}
    avatar_seed = profile_data.get("avatar-seed") or profile_data.get("name", "default")
    mapped_data["avatar_svg"] = None
    mapped_data["avatar_customized"] = False

    password = secrets.token_urlsafe(12)
    email= profile_data.get("email")

    new_id = create_auth_account(email, password)
    if new_id is None:
        return jsonify({"error": "Failed to create user account"}), 500
    email_sent = send_temp_password(email, password)
    if email_sent is None:      
        auth.delete_user(new_id)
        print(f"User {new_id} deleted due to email failure")
        return jsonify({"error": "Failed to send temporary password email"}), 500
    mapped_data["user_id"] = new_id
    try:   
        create_user_profile(mapped_data, user_id=new_id)
    except Exception as e:
        auth.delete_user(new_id)
        print(f"User {new_id} deleted due to an error: {e}")
        return jsonify({"error": "Failed to create user profile"}), 500
    return jsonify({"user_id": new_id})

@app.route("/auth/verify", methods=["POST"])
@limiter.limit("5/minute")
def verify_token():
    id_token = (request.json or {}).get("idToken")
    if not id_token:
        return jsonify({"error": "Missing token"}), 400
    try:
        decoded_token = auth.verify_id_token(id_token, clock_skew_seconds=60)
        uid = decoded_token.get("uid")
        user_profile = get_user_profile(uid)
        name = user_profile.get("name") if user_profile else None
        avatar_customized = user_profile.get("avatar_customized", False) if user_profile else False
    except Exception:
        return jsonify({"error": "Invalid token"}), 401
    if decoded_token.get("role") == "therapist":
        redirect_url= "/therapist"
    elif decoded_token.get("role") == "child":
        redirect_url = "/child_interface" if avatar_customized else "/child_interface/avatar-setup"
    else:
        return jsonify({"error": "Invalid role"}), 403
    
    try: 
        session_cookie = auth.create_session_cookie(id_token, expires_in=SESSION_EXPIRES_IN)
    except Exception:
        return jsonify({"error": "Failed to create session"}), 401
    
    response = make_response(jsonify({"redirect_url": redirect_url, "name": name}))
    response.set_cookie(
        "session",
        session_cookie,
        max_age=int(SESSION_EXPIRES_IN.total_seconds()),
        httponly=True,
        samesite="Strict",
        path="/"
    )
    return response

@app.route("/api/profiles", methods=["GET"])
@login_required
def get_profiles(current_user):
    if current_user["role"] != "therapist":
        return jsonify({"error": "Unauthorized"}), 403
    profiles = get_all_profiles()
    return jsonify({"profiles": profiles})


@app.route("/api/profiles/<profile_id>/details", methods=["GET"])
@login_required
def get_profile_details(current_user, profile_id):
    if current_user["role"] != "therapist":
        return jsonify({"error": "Unauthorized"}), 403

    profile = get_profile_by_id(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    sessions = get_sessions_for_user(profile_id)
    emotions = get_emotion_entries_for_user(profile_id)
    alerts = get_unacknowledged_alerts(profile_id)
    return jsonify({"profile": profile, "sessions": sessions, "emotions": emotions, "alerts": alerts})

@app.route("/api/profiles/<profile_id>/alerts/<alert_id>/acknowledge", methods=["POST"])
@login_required
def acknowledge_profile_alert(current_user, profile_id, alert_id):
    if current_user["role"] != "therapist":
        return jsonify({"error": "Unauthorized"}), 403
    acknowledge_alert(alert_id, current_user["uid"])
    return jsonify({"status": "acknowledged"})

@app.route("/therapist/delete_profile/<profile_id>", methods=["POST"])
@login_required
def delete_profile(current_user, profile_id):
    if current_user["role"] != "therapist":
        return jsonify({"error": "Unauthorized"}), 403
    try:
        delete_child_profile(profile_id)
    except Exception as e:
        print(f"Error deleting profile {profile_id}: {e}")
        return jsonify({"error": "Failed to delete profile"}), 500
    return jsonify({"status": "deleted"})

@app.route("/therapist/profiles")
def select_profile():
    return render_template("select-profile.html")

@app.route("/child_interface/avatar-setup")
@page_login_required
def avatar_setup(current_user):
    if current_user["role"] != "child":
        return jsonify({"error": "Unauthorized"}), 403
    return render_template("avatar-setup.html")

@app.route("/api/avatar/save", methods=["POST"])
@login_required
def save_avatar(current_user):
    if current_user["role"] != "child":
        return jsonify({"error": "Unauthorized"}), 403
    options = request.json.get("options", {})
    avatar_svg = generate_avatar_svg(options.get("seed", current_user["uid"]), options)
    update_avatar(current_user["uid"], avatar_svg, options)
    return jsonify({"status": "ok"})

@app.route("/api/emotion/checkin", methods=["POST"])
@login_required
def emotion_checkin(current_user):
    if current_user["role"] != "child":
        return jsonify({"error": "Unauthorized"}), 403
    emotion = request.json.get("emotion")
    if not emotion:
        return jsonify({"error": "Missing emotion"}), 400
    state = get_state(current_user["uid"])
    save_emotion_entry(current_user["uid"], state.get("session_id"), emotion)
    return jsonify({"status": "ok"})

# Thresholds/fallback for the child-facing "Activities I've practiced"
# grouping in /api/progress -- a display/gamification choice, not a
# clinical one. Used only when no LLM-derived "understanding" exists yet
# for a theme (e.g. sessions predating that field).
CONFIDENT_SESSION_COUNT = 4
PRACTICING_SESSION_COUNT = 2


def _status_for_count(count):
    if count >= CONFIDENT_SESSION_COUNT:
        return "confident"
    if count >= PRACTICING_SESSION_COUNT:
        return "practicing"
    return "started"


def _latest_understanding_for_theme(session_insights, theme):
    for insight in reversed(session_insights):
        if insight.get("theme") == theme and insight.get("understanding"):
            return insight["understanding"]
    return None


def _status_for_theme(count, understanding):
    if understanding == "confident":
        return "confident"
    if understanding in ("developing", "struggling"):
        return "started" if count <= 1 else "practicing"
    # No understanding data yet for this theme -- fall back to frequency only.
    return _status_for_count(count)


@app.route("/api/progress", methods=["GET"])
@limiter.limit("30/minute")
@login_required
def get_progress(current_user):
    if current_user["role"] != "child":
        return jsonify({"error": "Unauthorized"}), 403

    user_id = current_user["uid"]
    profile = get_user_profile(user_id) or {}
    sessions = get_sessions_for_user(user_id)
    session_insights = profile.get("session_insights") or []

    theme_counts = Counter(s.get("theme") for s in sessions if s.get("theme"))
    themes_by_status = {"confident": [], "practicing": [], "started": []}
    for theme in sorted(theme_counts):
        understanding = _latest_understanding_for_theme(session_insights, theme)
        status = _status_for_theme(theme_counts[theme], understanding)
        themes_by_status[status].append(theme)

    consolidated = profile.get("consolidated_profile") or {}
    skills_growing = consolidated.get("resolved_difficulties") or []

    return jsonify({"themes_by_status": themes_by_status, "skills_growing": skills_growing})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)