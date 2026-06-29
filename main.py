from database.firebase_client import get_exercise, create_session, save_message, create_session, close_session, update_profile_insights
from user_profiles.user_profile import get_user_profile
from llm.companion import run_session, analyze_session, consolidate_profile

def main():
    user_id = "ncIl1AyFDPYCRHgcalax" # Id en fonction du profil choisi (Firebase) 
    theme = "Change of plans"

    # Attention: si on ne met rien on a une erreur
    user_profile = get_user_profile(user_id)
    if not user_profile:
        return

    exercise = get_exercise(theme, user_profile["levelAutism"])

    session_id = create_session(user_id, theme)

    conversation_history = []

    print("Début de la session.\n Lorsque vous souhaitez arrêter la session, écrivez 'fin'")

    # Premier message du LLM
    first_response = run_session(user_profile, exercise, conversation_history)
    print(f"\n LiveAlong : {first_response}\n")

    save_message(session_id, "model", first_response)
    conversation_history.append({"role": "model", "parts": first_response})

    while True:
        user_input = input("Toi : ")

        if user_input.lower() == "fin":
            close_session(session_id)
            
            # Analyse de la conversation par le LLM
            print("\n Analyse de la session en cours...")
            insights = analyze_session(user_profile, conversation_history, theme)

            consolidated_profile = consolidate_profile(user_profile, insights)
            
            # Mise à jour du profil dans Firebase
            update_profile_insights(user_id, theme, insights, consolidated_profile)
            
            print("\n Session terminée et profil mis à jour.")
            break
        save_message(session_id, "user", user_input)
        conversation_history.append({"role": "user", "parts": user_input})

        response = run_session(user_profile, exercise, conversation_history)
        print(f"\n LiveAlong : {response}\n")

        save_message(session_id, "model", response)
        conversation_history.append({"role": "model", "parts": response})

if __name__ == "__main__":
    main()