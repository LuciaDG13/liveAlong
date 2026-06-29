from google.cloud.firestore_v1.base_query import FieldFilter
import firebase_admin
from firebase_admin import credentials, firestore
from config import FIREBASE_CREDENTIALS_PATH
from datetime import datetime

cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

def get_exercise(theme, levelAutism):
    exercises_ref = db.collection("SocialStories")

    query = (
        exercises_ref
        .where(filter=FieldFilter("Theme", "==", theme))
        .where(filter=FieldFilter("LevelAutism", "==", int(levelAutism)))
        .limit(1)
    )
    
    results = query.get()
    
    if results:
        return results[0].to_dict()["Story"]
    return None

def create_session(user_id, theme):
    session_ref = db.collection("Sessions").document()
    session_ref.set({
        "user_id": user_id,
        "theme": theme,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "en cours"
    })

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

def close_session(session_id):
    db.collection("Sessions").document(session_id).update({
        "status": "terminee",
        "end_time": datetime.now().strftime("%H:%M:%S")
    })

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