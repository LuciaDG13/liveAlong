import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, render_template, request, jsonify
from database.firebase_client import get_exercise, create_session, save_message, close_session, update_profile_insights
from user_profiles.user_profile import get_user_profile
from llm.companion import run_session, analyze_session, consolidate_profile



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
    return render_template("index.html")

@app.route("/child_interface")
def child_interface():
    return render_template("child.html")

@app.route("/start", methods=["POST"])
def start():
    user_id = "ncIl1AyFDPYCRHgcalax"
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
    save_message(session_id, "model", first_response)
    session_state["conversation_history"].append({"role": "model", "parts": first_response})

    return jsonify({"response": first_response})

@app.route("/message", methods=["POST"])
def message():
    user_input = request.json.get("message")

    save_message(session_state["session_id"], "user", user_input)
    session_state["conversation_history"].append({"role": "user", "parts": user_input})

    response = run_session(
        session_state["user_profile"],
        session_state["exercise"],
        session_state["conversation_history"]
    )

    save_message(session_state["session_id"], "model", response)
    session_state["conversation_history"].append({"role": "model", "parts": response})

    return jsonify({"response": response})

@app.route("/end", methods=["POST"])
def end():
    close_session(session_state["session_id"])

    insights = analyze_session(
        session_state["user_profile"],
        session_state["conversation_history"],
        session_state["theme"]
    )
    consolidated_profile = consolidate_profile(session_state["user_profile"], insights)
    update_profile_insights(
        session_state["user_profile"]["name"],  # ⚠️ à vérifier : remplace par le vrai user_id
        session_state["theme"],
        insights,
        consolidated_profile
    )

    return jsonify({"status": "session terminée"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)