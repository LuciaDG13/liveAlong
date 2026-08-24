"""
poster_lora_comparison.py

Outil ponctuel pour generer un exemple avant/apres LoRA, a coller sur le
poster. Ne fait pas partie de l'app -- a lancer une fois a la main :

    (env conda LiveAlong) python poster_lora_comparison.py

Assure-toi qu'app.py n'est PAS lance en meme temps (le modele ne tiendrait
pas deux fois en VRAM).

Principe : llm.companion charge le modele de base (Qwen2.5-7B-Instruct) puis
lui applique l'adaptateur LoRA (PeftModel). Le meme objet model est reutilise
pour les deux generations -- le context manager model.disable_adapter() de
peft desactive temporairement le LoRA sans rien recharger, donc on obtient
un vrai "avant" (modele brut) et "apres" (LoRA actif) sur exactement le
meme code de production (run_session), juste avec l'adaptateur coupe ou non.
"""
import sys

from llm.companion import model, tokenizer, MODEL_AVAILABLE, run_session

if not MODEL_AVAILABLE:
    print("Le modele n'a pas pu etre charge -- impossible de generer la comparaison.")
    sys.exit(1)

# Le tout premier message ("phrase d'ouverture") est volontairement bref et
# generique quel que soit le profil (cf. system prompt : "Be brief... If
# this is the first message, introduce the exercise"), donc il ne montre pas
# grand-chose. On simule plutot un deuxieme tour -- meme ouverture, meme
# reponse de l'enfant pour les deux profils -- afin d'isoler le profil comme
# seule variable qui peut faire differer la reponse du modele.
OPENING = "Great! Today we're going to talk about waiting in line at the bakery. Have you ever been to a bakery before?"
CHILD_REPLY = "I don't like waiting, it's boring."
CONVERSATION_HISTORY = [
    {"role": "assistant", "parts": OPENING},
    {"role": "user", "parts": CHILD_REPLY},
]

PROFILES = [
    {
        "label": "Profil A -- niveau 3, vocabulaire simple, sensible au bruit",
        "profile": {
            "name": "Sam",
            "levelAutism": 3,
            "sensory": ["loud noises", "bright lights"],
            "interest": "trains",
            "language": "simple, short sentences",
        },
        "exercise": "A story about waiting in line at the bakery.",
    },
    {
        "label": "Profil B -- niveau 1, vocabulaire riche, aucune sensibilite declaree",
        "profile": {
            "name": "Alex",
            "levelAutism": 1,
            "sensory": [],
            "interest": "dinosaurs and space",
            "language": "rich vocabulary, longer sentences",
        },
        "exercise": "A story about waiting in line at the bakery.",
    },
]

print(f'Message de l\'enfant simule (identique pour les deux profils) : "{CHILD_REPLY}"\n')

for entry in PROFILES:
    print("=" * 70)
    print(entry["label"])
    print("=" * 70)

    print("\n--- AVANT (modele de base, LoRA desactive) ---\n")
    with model.disable_adapter():
        base_reply = run_session(entry["profile"], entry["exercise"], CONVERSATION_HISTORY)
    print(base_reply)

    print("\n--- APRES (avec l'adaptateur LoRA) ---\n")
    lora_reply = run_session(entry["profile"], entry["exercise"], CONVERSATION_HISTORY)
    print(lora_reply)
    print()
