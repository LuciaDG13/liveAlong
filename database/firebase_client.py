from google.cloud.firestore_v1.base_query import FieldFilter
import firebase_admin
from firebase_admin import credentials, firestore, auth
from config.config import FIREBASE_CREDENTIALS_PATH, SENDGRID_API_KEY, SENDGRID_SENDER
from datetime import datetime
from sendgrid import SendGridAPIClient 
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

load_dotenv()
sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)

cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)

db = firestore.client()

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

def get_all_profiles():
    profiles_ref = db.collection("Profiles").where(filter=FieldFilter("role", "==", "child"))
    profiles = profiles_ref.stream()
    return [{"id": profile.id, "name": profile.to_dict().get("name")} for profile in profiles]


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