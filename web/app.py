import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firebase_admin import auth
from flask import Flask, render_template, request, jsonify, make_response
from database.firebase_client import get_exercise, create_session, save_message, close_session, update_profile_insights, create_user_profile, create_auth_account, send_temp_password, get_all_profiles
from user_profiles.user_profile import get_user_profile
from llm.companion import run_session, analyze_session, consolidate_profile
import secrets
from web.auth import login_required, page_login_required
from datetime import timedelta

SESSION_EXPIRES_IN= timedelta(days=3)

app = Flask(__name__)

# Variables globales simples pour garder l'état de la session en cours
# (suffisant pour une démo avec un seul enfant à la fois)
session_state = {
    "session_id": None,
    "user_profile": None,
    "exercise": None,
    "theme": None,
    "conversation_history": []
}

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/child_interface")
@page_login_required
def child_interface(current_user):
    if (current_user["role"]!="child"):
        return jsonify({"error": "Unauthorized"}), 403
    return render_template("child.html")

@app.route("/therapist")
@page_login_required
def therapist(current_user):
    print(f"The user is {current_user.get('role')} whose name is {current_user.get('name')}")
    if (current_user["role"] != "therapist"):
        return jsonify({"error": "Unauthorized"}), 403
    return render_template("therapist.html")

@app.route("/start", methods=["POST"])
@login_required
def start(current_user):
    if (current_user["role"] != "child"):
        return jsonify({"error": "Unauthorized"}), 403
    user_id = request.json.get("user_id")
    theme = "Change of plans"
    user_profile = get_user_profile(user_id)
    exercise = get_exercise(theme, user_profile["levelAutism"])
    session_id = create_session(user_id, theme)

    session_state["session_id"] = session_id
    session_state["user_profile"] = user_profile
    session_state["exercise"] = exercise
    session_state["theme"] = theme
    session_state["conversation_history"] = []

    first_response = run_session(user_profile, exercise, [])
    save_message(session_id, "assistant", first_response)
    session_state["conversation_history"].append({"role": "assistant", "parts": first_response})

    return jsonify({"response": first_response})

@app.route("/message", methods=["POST"])
@login_required
def message(current_user):
    if (current_user["role"] != "child"):
        return jsonify({"error": "Unauthorized"}), 403

    user_input = request.json.get("message")

    save_message(session_state["session_id"], "user", user_input)
    session_state["conversation_history"].append({"role": "user", "parts": user_input})

    response = run_session(
        session_state["user_profile"],
        session_state["exercise"],
        session_state["conversation_history"]
    )

    save_message(session_state["session_id"], "assistant", response)
    session_state["conversation_history"].append({"role": "assistant", "parts": response})

    return jsonify({"response": response})

@app.route("/end", methods=["POST"])
@login_required
def end(current_user):
    if (current_user["role"] != "child"):
        return jsonify({"error": "Unauthorized"}), 403

    close_session(session_state["session_id"])

    insights = analyze_session(
        session_state["user_profile"],
        session_state["conversation_history"],
        session_state["theme"]
    )
    consolidated_profile = consolidate_profile(session_state["user_profile"], insights)
    update_profile_insights(
    current_user["user_id"],
    session_state["theme"],
    insights,
    consolidated_profile
)

    return jsonify({"status": "session terminée"})

@app.route("/therapist/create_profile", methods=["GET", "POST"])
def create_profile():
    if request.method == "GET":
        return render_template("creation-profile.html")
    
    profile_data = request.json  # Récupère le dictionnaire envoyé depuis le formulaire
    mapped_data = {
        "name": profile_data.get("name"),
        "date_of_birth": profile_data.get("date_of_birth"),
        "gender": profile_data.get("gender"),
        "pronoun": profile_data.get("pronoun"),
        "communication-type": profile_data.get("communication-type"),
        "language-level": profile_data.get("language-level"),
        "autism-level": profile_data.get("autism-level"),
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
    password = secrets.token_urlsafe(12)
    email= profile_data.get("email")

    new_id = create_auth_account(email, password)
    if new_id is None:
        return jsonify({"error": "Failed to create user account"}), 500
    email_sent = send_temp_password(email, password)
    if email_sent is None:      
        auth.delete_user(new_id)
        print("User {new_id} deleted due to email failure")  
        return jsonify({"error": "Failed to send temporary password email"}), 500
    mapped_data["user_id"] = new_id
    try:   
        create_user_profile(mapped_data)
    except Exception as e:
        auth.delete_user(new_id)
        print("User {new_id} deleted due to an error: {e}") 
        return jsonify({"error": "Failed to create user profile"}), 500
    return jsonify({"user_id": new_id})

@app.route("/auth/verify", methods=["POST"])
def verify_token():    
    id_token = (request.json or {}).get("idToken")
    if not id_token:
        return jsonify({"error": "Missing token"}), 400
    try:
        decoded_token = auth.verify_id_token(id_token, clock_skew_seconds=60)
    except Exception:
        return jsonify({"error": "Invalid token"}), 401
    if decoded_token.get("role") == "therapist":
        redirect_url= "/therapist"
    elif decoded_token.get("role") == "child":
        redirect_url= "/child_interface"
    else:
        return jsonify({"error": "Invalid role"}), 403
    
    try: 
        session_cookie = auth.create_session_cookie(id_token, expires_in=SESSION_EXPIRES_IN)
    except Exception:
        return jsonify({"error": "Failed to create session"}), 401
    
    response = make_response(jsonify({"redirect_url": redirect_url}))
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

@app.route("/therapist/profiles")
def select_profile():
    return render_template("select-profile.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)