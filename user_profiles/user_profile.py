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

    sensory_categories = []
    if profile.get("sensory-auditory"):
        sensory_categories.append("auditory")
    if profile.get("sensory-visual"):
        sensory_categories.append("visual")
    if profile.get("sensory-tactile"):
        sensory_categories.append("tactile")
    if profile.get("sensory-olfactory"):
        sensory_categories.append("olfactory")
    if profile.get("sensory-gustatory"):
        sensory_categories.append("gustatory")
    profile["sensory_categories"] = sensory_categories

    return profile