from firebase_admin import auth
from flask import request, jsonify
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing token"}), 401
        token = token.split("Bearer ")[-1]
        try:
            decoded = auth.verify_id_token(token)
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        kwargs["current_user"] = decoded
        return f(*args, **kwargs)
    return decorated