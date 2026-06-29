from database.firebase_client import db

def get_user_profile(user_id):
    doc = db.collection("Profiles").document(user_id).get()
    
    if doc.exists:
        return doc.to_dict()
    else:
        print(f"Profil introuvable pour l'ID : {user_id}")
        return None