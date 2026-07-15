from database.firebase_client import db

def get_user_profile(user_id):
    doc = db.collection("Profiles").document(user_id).get()

    if not doc.exists:
        print(f"Profil introuvable pour l'ID : {user_id}")
        return None

    profile = doc.to_dict()

    sensory_fields = [
        profile.get("sensory-auditory"),
        profile.get("sensory-visual"),
        profile.get("sensory-tactile"),
        profile.get("sensory-olfactory"),
        profile.get("sensory-gustatory"),
    ]
    profile["sensory"] = list(filter(None, sensory_fields))

    profile["interest"] = profile.get("interests")
    profile["language"] = profile.get("language-level")

    return profile