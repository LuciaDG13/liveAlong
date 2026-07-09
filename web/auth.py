from firebase_admin import auth
from flask import request, jsonify, redirect
from functools import wraps

def get_decoded_session():
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        print("Les cookies ne sont pas chargés")
        """Debugging line"""
        return None
    try:
        return auth.verify_session_cookie(session_cookie, check_revoked= True, clock_skew_seconds=60)
    except Exception as e:
        print(f"Error verify_session_cookie: {e}")
        return None
    

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        decoded = get_decoded_session()
        if decoded is None:
            return jsonify({"error": "Missing or invalid session"}), 401
        kwargs["current_user"] = decoded
        return f(*args, **kwargs)
    return decorated

def page_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        decoded = get_decoded_session()
        if decoded is None:
            return redirect("/")
        kwargs["current_user"] = decoded
        return f(*args, **kwargs)
    return decorated