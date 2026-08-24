# Rapport technique — LiveAlong

Compagnon conversationnel IA pour enfants avec troubles du spectre autistique (TSA)

## Sommaire

1. Vue d'ensemble et architecture générale
2. Modèle de données (Firestore)
3. Authentification et rôles
4. Parcours thérapeute
5. Parcours enfant
6. **Cœur du système : le modèle de langage et le fine-tuning LoRA**
7. **Entraînement d'un adaptateur LoRA personnalisé (5 personas) — travail réalisé pendant le stage**
8. Les autres briques IA/ML du pipeline
9. Sécurité, confidentialité et limites d'usage
10. Tests automatisés
11. Historique technique et difficultés rencontrées
12. Limites connues et pistes futures
13. Conclusion

---

## 1. Vue d'ensemble et architecture générale

LiveAlong est une application web destinée à deux profils d'utilisateurs :

- **l'enfant** (avec TSA), qui dialogue avec un compagnon animé pour pratiquer des "histoires sociales" (social stories) autour de thèmes du quotidien (attendre son tour, changement de plan, etc.) ;
- **le·la thérapeute**, qui crée les profils, supervise les séances a posteriori et reçoit des alertes en cas de message inquiétant.

### Stack technique

| Couche | Technologies |
|---|---|
| Backend web | Flask, Flask-Limiter (rate limiting) |
| Authentification | Firebase Authentication (comptes + claims de rôle + cookies de session) |
| Base de données | Firebase Firestore (NoSQL, orienté documents) |
| Emails transactionnels | SendGrid (mot de passe temporaire à la création d'un profil) |
| LLM conversationnel | Qwen2.5-7B-Instruct + adaptateur **LoRA** ASD-iLLM (`transformers`, `peft`, `bitsandbytes`) |
| Reconnaissance vocale | `faster-whisper` (modèle Whisper `base.en`) |
| Synthèse vocale | Kokoro TTS |
| Lip-sync | Rhubarb Lip Sync (exécutable externe) |
| Classification de sécurité | scikit-learn (TF-IDF + régression logistique) |
| Avatar | Dicebear (génération SVG procédurale) + animation JS custom |
| Frontend | HTML/CSS/JS "vanilla" (pas de framework), Firebase JS SDK |

### Flux d'un tour de dialogue

```
Enfant (voix, texte ou pictogrammes)
   │
   ▼
[Whisper]  parole -> texte                         (web/app.py, si entrée vocale)
   │
   ▼
[Classifieur de sécurité]  texte -> none / mild_distress / crisis
   │  (si "crisis" -> réponse de repli + alerte thérapeute, sinon on continue)
   ▼
[Qwen2.5-7B-Instruct + LoRA ASD-iLLM]  texte -> réponse   (llm/companion.py)
   │  (prompt système personnalisé par profil + historique)
   ▼
[Kokoro TTS]  texte -> audio
   │
   ▼
[Rhubarb]  audio -> visèmes (mouthCues)
   │
   ▼
Avatar animé côté navigateur (audio + lip-sync image par image)
```

Chaque échange est journalisé dans Firestore (`Sessions/{id}/messages`). En fin de séance, le modèle est réinvoqué deux fois de plus pour **analyser** la conversation et **mettre à jour un profil clinique consolidé**, exploité par le thérapeute et par les séances suivantes.

---

## 2. Modèle de données (Firestore)

L'application utilise cinq collections principales, déduites de `database/firebase_client.py` :

| Collection | Contenu | Écrit par |
|---|---|---|
| `Profiles` | Un document par enfant : identité, niveau TSA, sensibilités sensorielles, centres d'intérêt, `avatar_svg`/`avatar_options`, `consolidated_profile`, `session_insights[]`, `usage_today` | création de profil, fin de séance, sauvegarde avatar |
| `Sessions` | Une séance (thème, date, heures, statut, `ended_by`) + sous-collection `messages` (rôle, contenu, horodatage) | `create_session`, `save_message`, `close_session` |
| `SocialStories` | Banque d'exercices (histoire sociale) indexée par `theme` + `levelAutism` | remplie côté thérapeute (`pdf_to_firestore.py`) |
| `EmotionEntries` | Check-ins émotionnels de l'enfant (`user_id`, `session_id`, `emotion`, `timestamp`) | check-in avant séance |
| `SafetyAlerts` | Messages signalés par le classifieur de sécurité, avec statut d'acquittement thérapeute | `create_safety_alert` / `acknowledge_alert` |

```python
# database/firebase_client.py
def create_session(user_id, theme):
    now = datetime.now()
    session_ref = db.collection("Sessions").document()
    session_ref.set({
        "user_id": user_id,
        "theme": theme,
        "date": now.strftime("%Y-%m-%d"),
        "start_time": now.strftime("%H:%M:%S"),
        "status": "en cours"
    })
    _bump_usage_session_count(user_id, now)
    return session_ref.id
```

Le profil "consolidé" (`consolidated_profile`) est la mémoire long-terme de l'enfant : traits stables, difficultés émergentes, difficultés résolues. Il est réécrit à chaque fin de séance par le LLM (voir §6.9) et réinjecté dans le prompt système de la séance suivante — c'est le mécanisme qui permet au compagnon de ne pas répéter les mêmes exercices et de suivre les progrès dans le temps.

---

## 3. Authentification et rôles

L'authentification repose sur **Firebase Auth**, avec deux rôles distincts (`child` / `therapist`) encodés comme *custom claims* sur le compte Firebase, positionnés côté serveur à la création du compte :

```python
# database/firebase_client.py
def create_auth_account(email, password):
    user = auth.create_user(email=email, password=password)
    auth.set_custom_user_claims(user.uid, {'role': 'child'})
    return user.uid
```

Côté navigateur (`web/static/js/auth.js`), la connexion se fait via le SDK Firebase (`signInWithEmailAndPassword`), puis le jeton d'identité (ID token) est envoyé au backend pour vérification et échange contre un **cookie de session httponly** :

```python
# web/app.py — /auth/verify
decoded_token = auth.verify_id_token(id_token, clock_skew_seconds=60)
...
session_cookie = auth.create_session_cookie(id_token, expires_in=SESSION_EXPIRES_IN)
response.set_cookie("session", session_cookie, httponly=True, samesite="Strict", path="/")
```

Toutes les routes sensibles sont protégées par les décorateurs `login_required` (API, renvoie 401) ou `page_login_required` (pages, redirige vers `/`), définis dans `web/auth.py`, et chaque route vérifie en plus explicitement le rôle attendu (`if current_user["role"] != "child": return 403`). Aucun mot de passe n'est géré directement par LiveAlong : le mot de passe temporaire d'un nouveau profil enfant est généré côté serveur (`secrets.token_urlsafe(12)`) et envoyé par email via SendGrid, jamais affiché dans l'interface thérapeute.

---

## 4. Parcours thérapeute

### 4.1 Création d'un profil enfant

`web/templates/creation-profile.html` + route `POST /therapist/create_profile` (`web/app.py:303`). Le consentement parental est une condition bloquante côté serveur :

```python
if profile_data.get("parental-consent") != "true":
    return jsonify({"error": "Parental/guardian consent is required"}), 400
```

Le formulaire capture : identité, date de naissance, niveau TSA, type de communication, niveau de langage, centres d'intérêt, sensibilités sensorielles (auditive/visuelle/tactile/olfactive/gustative), apaisement, contact physique, contexte clinique, déclencheurs (`triggers`), et un avatar de départ. À la validation : compte Firebase Auth créé, mot de passe temporaire envoyé par email, document `Profiles` créé — avec **rollback** (suppression du compte Auth) si l'email ou la création du profil échoue, pour éviter un compte orphelin sans accès.

### 4.2 Tableau de bord thérapeute

`web/static/js/select-profile.js` (374 lignes) affiche la liste des profils enfants avec deux badges d'alerte visuelle :

```javascript
// web/static/js/select-profile.js
${profile.alert_count > 0 ? `<span class="profile-card-badge alert" ...>●</span>` : ""}
${profile.usage_flag ? `<span class="profile-card-badge usage" ...>●</span>` : ""}
```

La fiche détail d'un profil agrège plusieurs vues construites côté client à partir d'un seul appel API (`GET /api/profiles/<id>/details`) :

- **Récapitulatif** du profil + profil consolidé (traits stables / difficultés émergentes / résolues) ;
- **Alertes de sécurité** non acquittées, avec bouton "Acknowledge" (`POST /api/profiles/<id>/alerts/<alert_id>/acknowledge`) ;
- **Heatmap émotionnelle** sur 12 semaines glissantes, une cellule par jour, construite en JS pur à partir des `EmotionEntries` (un seul point par jour si plusieurs check-ins) ;
- **Historique des conversations**, séance par séance, sous forme de bulles de chat.

La suppression d'un profil (`POST /therapist/delete_profile/<id>`) est irréversible et supprime à la fois le document Firestore et le compte Firebase Auth associé ; une confirmation JS (`window.confirm`) est requise côté client.

---

## 5. Parcours enfant

### 5.1 Sélection de l'exercice du jour

Au clic sur "commencer", la route `POST /start` choisit le thème de la séance via un **système de score explicite** (pas un modèle appris), défini dans `web/recommendation_service.py` :

```python
# web/recommendation_service.py
def score_story(story, user_profile, recent_themes, negative_emotion_themes, theme_counts=None, today_emotion=None):
    score = 0
    if story.get("theme") in recent_themes:
        score -= 10                          # éviter la répétition récente
    if story.get("theme") in emerging_difficulties:
        score += 5                           # prioriser les difficultés émergentes
    score -= conflict_count * 4              # éviter les conflits sensoriels
    if any(tag in interests_text for tag in interest_tags):
        score += 3                           # bonus si lié à un centre d'intérêt
    if today_emotion in NEGATIVE_EMOTIONS:
        # jour difficile -> pencher vers un thème déjà familier plutôt qu'un thème inédit
        ...
    return score
```

Le thème avec le meilleur score est retenu. Ce module est entièrement déterministe et testé unitairement (`tests/test_recommendation_service.py`).

### 5.2 Check-in émotionnel

Avant que la conversation ne démarre, l'enfant indique son humeur du moment via une grille de pictogrammes d'émotions (`renderEmotionCheckin`, `web/static/js/pictograms.js`). Cette information sert deux fois : elle influence le choix du thème (§5.1) et elle est injectée dans le prompt système du LLM (`today_emotion`, voir §6.7) pour adapter le ton dès le premier message.

### 5.3 Trois canaux d'entrée pour l'enfant

L'interface enfant (`child.html` / `child.js`) propose trois façons équivalentes de répondre, pensées pour des profils de communication différents :

**Texte** — saisie classique, envoyé à `POST /message`.

**Voix** — bouton micro (`web/static/js/speech.js`). L'enregistrement démarre au clic et s'arrête **automatiquement après un silence prolongé**, via une détection de niveau sonore calibrée sur le bruit ambiant :

```javascript
// web/static/js/speech.js
const SILENCE_LIMIT = 4000;      // ms de silence avant arrêt auto
const CALIBRATION_DURATION = 400; // ms pour mesurer le bruit de fond
const NOISE_MARGIN = 8;

function monitorSilence(){
    const level = getVolumeLevel();
    const treshold = ambientNoiseLevel + NOISE_MARGIN;
    if (level > treshold) { lastSoundTime = Date.now(); hasDetectedSound = true; }
    if (Date.now() - lastSoundTime >= SILENCE_LIMIT) stopRecording();
}
```

L'audio est envoyé à `POST /message_voice`, transcrit par Whisper côté serveur (§8.2), puis traité exactement comme un message texte.

**Pictogrammes** — grille de communication alternative et améliorée (CAA), `pictograms.js`. Les pictogrammes sont organisés en 4 catégories (*Needs*, *Actions*, *People*, *Emotions*) accessibles par onglets, plus une **barre "Oui/Non" fixe**, toujours visible quel que soit l'onglet ouvert, en application du principe de "vocabulaire core" en CAA (les mots les plus utilisés doivent être accessibles en un seul geste) :

```javascript
// web/static/js/pictograms.js
// Réponses oui/non : vocabulaire le plus utilisé de tous, donc affiché à
// part dans une barre fixe (#pictogram-core-bar), toujours visible quel que
// soit l'onglet ouvert -- pas de tap de navigation supplémentaire pour dire
// "non" (principe de vocabulaire core en CAA).
const responses = [
    { id: "yes", label: "Yes", src: "/static/pictograms/yes.png" },
    { id: "no", label: "No", src: "/static/pictograms/no.png" },
];
```

L'enfant peut composer un message de plusieurs pictogrammes (jusqu'à 5), qui sont concaténés en une phrase (`labels.join(", ")`) avant envoi. Les icônes utilisées proviennent de la banque **ARASAAC** (licence vérifiée et validée pour ce projet). Le choix de couleurs pastel désaturées par catégorie est délibéré, pour ne pas surcharger un public sensible sur le plan sensoriel.

### 5.4 Réponse : texte, voix et avatar animé

La réponse du compagnon est renvoyée sous trois formes simultanées : texte affiché, audio (base64, généré par Kokoro), et une liste de **visèmes** (`mouthCues`) produite par Rhubarb à partir de cet audio. L'animation de bouche est gérée entièrement côté client par la classe `AvatarSpeechPlayer` (`avatar-speech-sync.js`), qui synchronise forme de bouche et lecture audio image par image :

```javascript
// web/static/js/avatar-speech-sync.js
_tick(){
    if (this.audio.paused || this.audio.ended){ this._setMouth("X"); return; }
    const t = this.audio.currentTime;
    let current = this.cues[0];
    for (const cue of this.cues){
        if (cue.start <= t) current = cue; else break;
    }
    if (current) this._setMouth(current.shape);
    this._raf = requestAnimationFrame(() => this._tick());
}
```

Les 7 formes de bouche (A–F, X) suivent la nomenclature standard de Rhubarb Lip Sync ; elles sont dessinées en SVG et superposées à l'avatar Dicebear via une transformation `translate/scale` calibrée empiriquement (`AVATAR_MOUTH_TRANSFORM`, `child.js`), avec un panneau de debug caché (`?debug=1`) pour ajuster cette calibration à la souris.

### 5.5 Fin de séance et suivi de progression

Une séance se termine de deux façons : l'enfant clique sur "See you" (bouton explicite), ou le modèle lui-même insère le tag `<<END_EXERCISE>>` après avoir détecté que l'enfant veut arrêter (voir §6.7). Dans les deux cas, `finalize_session` déclenche l'analyse de la séance (§6.9). Une fermeture d'onglet/navigateur est aussi couverte : l'événement `pagehide` envoie un signal `sendBeacon` best-effort vers `/end` pour éviter de laisser une séance "en cours" orpheline.

L'onglet *Progress* de l'interface enfant (`loadProgress`, `GET /api/progress`) regroupe les thèmes déjà pratiqués en trois statuts (*Feeling confident* / *Practicing* / *Just started*), calculés en priorité à partir du champ `understanding` extrait par le LLM en fin de séance, avec un repli sur la simple fréquence si cette donnée n'existe pas encore pour un thème (`web/app.py:503`, `_status_for_theme`).

---

## 6. Cœur du système : le modèle de langage et le fine-tuning LoRA

C'est la partie centrale du projet : un LLM open-source **spécialisé par une adaptation LoRA** pour tenir le rôle d'un intervenant clinique auprès d'enfants autistes, plutôt qu'un assistant généraliste.

### 6.1 Modèle de base

Le modèle de base est **Qwen2.5-7B-Instruct** (Alibaba), un LLM généraliste de 7 milliards de paramètres :

```python
# config/config.py
LORA_PATH = os.environ.get("LORA_PATH_OVERRIDE") or os.path.join(BASE_DIR, "ASD-iLLM", "lora-weight-livealong")
LLM_MODEL = "Qwen/Qwen2.5-7B-Instruct"
LLM_MAX_TOKENS = 1500
```

*Note : `LORA_PATH` pointe aujourd'hui vers `ASD-iLLM/lora-weight-livealong/`, l'adaptateur ré-entraîné en interne (§7), et non plus directement vers le checkpoint ASD-iLLM original (`ASD-iLLM/lora-weight/`, toujours présent et intact). Les sections 6.2 à 6.10 ci-dessous décrivent le mécanisme LoRA et l'adaptateur ASD-iLLM d'origine, qui reste la fondation sur laquelle §7 continue l'entraînement.*

Utilisé seul, ce modèle est un assistant généraliste : il ne connaît ni les principes cliniques d'intervention ABA (Applied Behavior Analysis), ni le style de dialogue adapté à un enfant autiste. C'est le rôle du LoRA de le spécialiser, sans avoir à ré-entraîner les 7 milliards de paramètres.

### 6.2 Principe du LoRA (Low-Rank Adaptation)

Fine-tuner intégralement un modèle de 7B paramètres demanderait de stocker et mettre à jour des gradients pour chacun de ses poids — coûteux en mémoire et en calcul, et il faudrait distribuer une copie complète (~15 Go) du modèle par variante.

**LoRA** part d'une observation : on n'a pas besoin de modifier directement la matrice de poids `W` d'une couche (de taille `d × k`, potentiellement énorme). On peut geler `W` et n'apprendre qu'une **mise à jour de rang faible** :

```
W_adapté = W_gelé + (alpha / r) · (B · A)
```

où `A` est une matrice `r × k` et `B` une matrice `d × r`, avec `r` (le "rang") très petit devant `d` et `k` (ici `r = 8`). Seules `A` et `B` sont entraînées ; `W` reste inchangé. Le nombre de paramètres entraînables passe ainsi de `d × k` à `r × (d + k)`, soit une réduction de plusieurs ordres de grandeur. `alpha` est un facteur d'échelle qui contrôle l'amplitude de la correction (`alpha / r` = facteur multiplicatif appliqué à `B·A`).

Conséquences pratiques :
- Le fichier de poids LoRA est **petit** (quelques dizaines de Mo) au lieu de plusieurs Go pour un modèle complet.
- Le même modèle de base peut recevoir plusieurs adaptateurs LoRA interchangeables (un par tâche/domaine) sans dupliquer le modèle.
- L'adaptateur peut être **activé/désactivé à la volée** sur un modèle déjà chargé (voir §6.10).

### 6.3 Le jeu de données et l'entraînement du LoRA (ASD-iLLM)

L'adaptateur utilisé (`ASD-iLLM/lora-weight/`) n'a pas été entraîné par LiveAlong lui-même : il provient du travail de recherche **ASD-iLLM** (Lai et al., *EMNLP 2025 Findings*), vendorisé dans le dépôt sous `ASD-iLLM/`. LiveAlong réutilise directement ces poids publiés comme fondation, puis construit toute la couche produit (profils, personnalisation par prompt, sécurité, avatar, etc.) par-dessus.

```markdown
# ASD-iLLM/README.md
we propose a comprehensive framework for training LLMs to conduct dialogue
interventions in accordance with the principles of Applied Behavior Analysis
(ABA) [...]. We collected clinical recordings of dialogue interventions for
autistic children and constructed the topic dialogue dataset ASD-iLLM-8k.
By incorporating the system prompt based on the ABA and ASD-iLLM-8k dataset,
we fine-tuned LLMs to develop ASD-iLLM.
```

Le jeu de données ASD-iLLM-8k : 64,2 heures d'enregistrements cliniques réels transcrits en 751 dialogues multi-tours, nettoyés en 287 dialogues de haute qualité, puis augmentés via GPT-4.1 pour atteindre 8 035 exemples de dialogues thématiques suivant les principes ABA (instruction / aide / renforcement).

Le script d'entraînement fourni dans le dépôt (`ASD-iLLM/sft.py`) illustre la procédure, en s'appuyant sur la librairie **PEFT** (via `swift.tuners`) :

```python
# ASD-iLLM/sft.py
lora_rank = 8
lora_alpha = 32
...
target_modules = find_all_linears(model)
lora_config = LoraConfig(task_type='CAUSAL_LM', r=lora_rank, lora_alpha=lora_alpha,
                         target_modules=target_modules)
model = Swift.prepare_model(model, lora_config)
```

`find_all_linears(model)` repère automatiquement toutes les couches linéaires du transformeur (projections d'attention et du MLP) pour y injecter les matrices `A`/`B` du LoRA. `Swift.prepare_model` gèle le reste du modèle et ne rend entraînables que ces injections.

### 6.4 Les poids LoRA effectivement chargés

Le dossier `ASD-iLLM/lora-weight/` contient l'adaptateur ASD-iLLM original tel que publié par les auteurs (entraîné sur Qwen2.5-7B-Instruct, pas la variante 3B illustrée dans `sft.py`). C'est le point de départ de l'entraînement décrit en §7 ; il n'a jamais été modifié :

```json
// ASD-iLLM/lora-weight/adapter_config.json
{
  "base_model_name_or_path": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
  "peft_type": "LORA",
  "task_type": "CAUSAL_LM",
  "r": 8,
  "lora_alpha": 32,
  "lora_dropout": 0.0,
  "bias": "none",
  "target_modules": [
    "up_proj", "gate_proj", "k_proj", "v_proj",
    "q_proj", "o_proj", "down_proj"
  ]
}
```

Ici, `target_modules` couvre **toutes** les projections d'attention (`q_proj`, `k_proj`, `v_proj`, `o_proj`) et **toutes** les projections du MLP (`gate_proj`, `up_proj`, `down_proj`) de chaque bloc transformeur — c'est-à-dire l'ensemble des couches linéaires du modèle. Le facteur d'échelle effectif est `alpha / r = 32 / 8 = 4`.

Le fichier de poids (`adapter_model.safetensors`) pèse **environ 78 Mo**, à comparer aux ~15 Go du modèle Qwen2.5-7B-Instruct complet — c'est la démonstration concrète de la compacité du LoRA.

L'historique d'entraînement (`trainer_state.json`) montre 5 époques, 2 470 pas, avec une convergence nette :

| Étape | Loss | Token accuracy |
|---|---|---|
| step 1 (début) | 2.55 | 0.53 |
| step 2470 (fin, 5 époques) | 0.49 | 0.83 |

### 6.5 Chargement du modèle en production

C'est `llm/companion.py` qui charge le modèle de base **et** lui applique l'adaptateur LoRA, au démarrage de l'application :

```python
# llm/companion.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from config.config import LLM_MODEL, LORA_PATH, LLM_MAX_TOKENS

tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_quant_type="nf4"
)

base_model = AutoModelForCausalLM.from_pretrained(
    LLM_MODEL,
    quantization_config=quantization_config,
    device_map="auto"
)

model = PeftModel.from_pretrained(base_model, LORA_PATH)
model.eval()
```

Deux points importants :

- **Quantification 4-bit (NF4, via `bitsandbytes`)** : le modèle de base est chargé avec des poids compressés sur 4 bits (calculs effectués en `bfloat16`). C'est ce qui permet de faire tenir un modèle de 7 milliards de paramètres en mémoire GPU limitée — c'est le style **QLoRA** : base quantifiée + adaptateur LoRA en pleine précision par-dessus.
- **`PeftModel.from_pretrained(base_model, LORA_PATH)`** : c'est l'instruction qui "greffe" l'adaptateur LoRA sur le modèle de base. `LORA_PATH` pointe vers `ASD-iLLM/lora-weight/` (voir §6.4). À partir de là, `model` se comporte comme le modèle de base *augmenté* du comportement appris sur ASD-iLLM-8k.

Si le chargement échoue (pas de GPU, dépendances manquantes...), `MODEL_AVAILABLE` passe à `False` et toutes les fonctions du module renvoient un message d'erreur au lieu de planter l'application.

### 6.6 Personnalisation par prompt système, au-dessus du LoRA

Le LoRA donne au modèle son **style clinique général** (ABA, dialogue avec un enfant TSA). La personnalisation *par enfant* (nom, niveau, sensibilités sensorielles, centres d'intérêt, historique des séances précédentes) se fait, elle, **par prompt** — construit dynamiquement à chaque appel dans `run_session` :

```python
# llm/companion.py (extrait de run_session)
system_prompt = f"""
You are a conversational companion that directly interacts with a child with
Autism Spectrum Disorder [...]

Profile of the user:
- Name : {user_profile["name"]}
- Level of autism : {user_profile["levelAutism"]}
- Sensory sensibilities : {", ".join(user_profile["sensory"])}
- Interests : {user_profile["interest"]}
- Level of vocabulary : {user_profile["language"]}
{checkin_note}

Here is what we know about {user_profile["name"]} from the previous sessions :
{insights_summary}.
...
This is the exercise we are doing: {exercise}.
"""
```

Le prompt encode aussi les règles métier : la structure de l'histoire sociale (début/milieu/fin), le jeu de rôle explicite ("Now let's pretend..."), les considérations propres au TSA (communication explicite, intérêt répétitif toléré, théorie de l'esprit explicitée, reconnaissance émotionnelle concrète, pas de métaphores, etc.), et le protocole de fin de séance via un tag spécial :

```python
# llm/companion.py
- If, after you've offered this, the child confirms they want to stop [...]
  close the session warmly [...] and finish your reply with the exact tag
  <<END_EXERCISE>> on its own new line, after your goodbye message.
```

Ce tag est ensuite détecté côté serveur (`web/app.py`) pour déclencher la clôture de séance (§5.5).

### 6.7 Génération de la réponse

```python
# llm/companion.py (run_session)
messages = [{"role": "system", "content": system_prompt}]
for msg in conversation_history:
    messages.append({"role": msg["role"], "content": msg["parts"]})

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt").to("cuda")

with torch.no_grad():
    output = model.generate(
        **inputs,
        max_new_tokens=LLM_MAX_TOKENS,
        do_sample=True,
        temperature=0.7,
        pad_token_id=tokenizer.eos_token_id
    )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)
```

`model.generate` appelle ici le modèle de base **avec le LoRA actif** (aucune option particulière n'est nécessaire : dès que l'adaptateur est chargé via `PeftModel`, il est appliqué par défaut à chaque appel). `do_sample=True` + `temperature=0.7` introduit un peu d'aléatoire pour des réponses plus naturelles.

### 6.8 Filtrage de sécurité avant l'appel au LLM

Avant même d'atteindre `run_session`, chaque message enfant passe par le classifieur de sécurité (§8.3). Si le risque est classé `"crisis"`, le LLM n'est **pas** appelé : une réponse de repli fixe est utilisée à la place, et une alerte est créée pour le thérapeute (`web/app.py:75`, `check_message_safety`).

### 6.9 Réutilisation du même modèle pour l'analyse de séance

Les mêmes objets `model` / `tokenizer` (base + LoRA) sont réutilisés pour deux autres tâches, avec un prompt différent et une génération **déterministe** (`do_sample=False`) car on attend un JSON strict :

- `analyze_session(...)` : résume la séance et extrait difficultés/progrès observés, au format JSON (y compris le champ `understanding` utilisé pour le suivi de progression, §5.5).
- `consolidate_profile(...)` : fusionne ces observations dans le "profil consolidé" persistant (traits stables, difficultés émergentes, difficultés résolues), stocké ensuite dans Firebase.

```python
# llm/companion.py (analyze_session)
output = model.generate(
    **inputs,
    max_new_tokens=LLM_MAX_TOKENS,
    do_sample=False,
    pad_token_id=tokenizer.eos_token_id
)
...
clean = response_text.replace("```json", "").replace("```", "").strip()
return json.loads(clean)
```

*Point ouvert, noté dans `TODO.md` : faut-il que ces deux tâches d'analyse utilisent aussi le LoRA ASD-iLLM (spécialisé dialogue clinique), ou plutôt Qwen2.5-7B "nu" (potentiellement plus fiable pour de la génération JSON structurée) ? Question à trancher avec la maître de stage.*

### 6.10 Preuve empirique de l'effet du LoRA : script de comparaison

Le dépôt contient un script dédié, `poster_lora_comparison.py`, qui exploite une propriété de PEFT : l'adaptateur peut être **désactivé temporairement** sur un modèle déjà chargé, sans le recharger, via le context manager `model.disable_adapter()` :

```python
# poster_lora_comparison.py
from llm.companion import model, tokenizer, MODEL_AVAILABLE, run_session

print("\n--- AVANT (modele de base, LoRA desactive) ---\n")
with model.disable_adapter():
    base_reply = run_session(entry["profile"], entry["exercise"], CONVERSATION_HISTORY)
print(base_reply)

print("\n--- APRES (avec l'adaptateur LoRA) ---\n")
lora_reply = run_session(entry["profile"], entry["exercise"], CONVERSATION_HISTORY)
print(lora_reply)
```

Ce script permet de générer, sur le **même code de production** (`run_session`) et la **même entrée**, une réponse "modèle brut" et une réponse "modèle + LoRA", pour illustrer concrètement l'apport du fine-tuning (style de dialogue clinique, structure ABA, ton adapté à un enfant TSA) par rapport au modèle généraliste.

---

## 7. Entraînement d'un adaptateur LoRA personnalisé (5 personas) — travail réalisé pendant le stage

### 7.1 Contexte et objectif

L'adaptateur décrit en §6 (`ASD-iLLM/lora-weight/`) est le checkpoint publié tel quel par les auteurs du papier ASD-iLLM — aucun entraînement propre au projet LiveAlong n'avait été fait dessus. L'objectif de ce travail était de produire un **véritable adaptateur personnalisé**, en poursuivant l'entraînement de cet adaptateur original sur un jeu de données construit spécifiquement pour 5 profils d'enfants représentatifs de l'application, plutôt que de se contenter du modèle générique.

Démarche en 6 étapes : (1) définir 5 personas, (2) rédiger des exemples de référence à la main, (3) générer des données synthétiques en few-shot à partir de ces exemples, (4) nettoyer le résultat, (5) entraîner, (6) valider par comparaison directe avec l'original.

### 7.2 Outils et environnement

| Élément | Détail |
|---|---|
| GPU | NVIDIA GeForce RTX 5070, 12 227 MiB VRAM, driver 581.80, CUDA 13.0 (niveau driver) |
| Environnement Python | conda `LiveAlong` (`AppData\Local\anaconda3\envs\LiveAlong`), Python 3.12.13 — **distinct** du Python système (3.14, sans CUDA) |
| PyTorch | `torch==2.9.1+cu128` (+ `torchvision==0.24.1+cu128`, `torchaudio==2.9.1+cu128`) — build spécifique compatible `sm_120` (Blackwell), voir §11 |
| Fine-tuning | `transformers==4.57.6`, `peft==0.17.1`, `bitsandbytes==0.50.0`, `accelerate==1.14.0` |
| Modèle de base | `Qwen/Qwen2.5-7B-Instruct`, déjà en cache HuggingFace local (`~/.cache/huggingface/hub`, ~15 Go, partagé avec faster-whisper et Kokoro) — aucun retéléchargement nécessaire |
| Contrainte disque | 5,3–5,4 Go libres sur un disque de 136 Go (97 % plein) tout au long du travail — a directement dicté plusieurs choix : pas de checkpoints intermédiaires au départ, puis `save_total_limit` + nettoyage systématique du dossier scratch une fois les checkpoints réintroduits pour la sélection du meilleur modèle |

L'interpréteur de cet environnement a été invoqué par son chemin complet (`AppData\Local\anaconda3\envs\LiveAlong\python.exe script.py`) plutôt que via `conda activate`, pour contourner le conflit PowerShell/conda documenté en §11.

### 7.3 Étape 1 — Définition des 5 personas

Personas construits en croisant 3 axes (mode de communication × niveau de soutien × sensibilité sensorielle dominante), sur les combinaisons les plus représentatives plutôt que toutes les combinaisons possibles. A et B reprennent tels quels les deux profils déjà utilisés dans `poster_lora_comparison.py` ; C, D et E sont nouveaux :

| Persona | Nom | Niveau | Communication | Sensibilité | Intérêt |
|---|---|---|---|---|---|
| A | Sam | 3 | Verbal, vocabulaire simple | Bruit, lumière | Trains |
| B | Alex | 1 | Verbal, vocabulaire riche | Aucune déclarée | Dinosaures et espace |
| C | Noor | 2 | **Non-verbal**, grille de pictogrammes uniquement | Lumière | Animaux |
| D | Milo | 2 | **Partiellement verbal**, fragments télégraphiques | Aucune déclarée | Insectes (intérêt restreint et intense) |
| E | Priya | 1 | Verbal | Toucher / textures | Musique et chant |

```python
# data/personas.py
PERSONAS = [
    {
        "persona_id": "C",
        "label": "Persona C -- non-verbal (pictogram grid), level 2, light-sensitive",
        "communication_type": "Non-verbal",
        "profile": {
            "name": "Noor",
            "levelAutism": 2,
            "sensory": ["bright lights"],
            "interest": "animals",
            "language": "non-verbal, communicates through the pictogram grid only",
        },
    },
    # ... A, B, D, E de même forme
]

# Vocabulaire pictogrammes réel (web/static/js/pictograms.js), pour que les
# exemples de Persona C restent strictement dans ce que l'app propose réellement :
PICTOGRAM_VOCABULARY = {
    "needs": ["I want", "I need", "more", "stop", "help", "done"],
    "actions": ["play", "eat", "drink", "sleep", "go out", "go"],
    "people": ["mom", "dad", "therapist", "me", "you"],
    "emotions": ["happy", "confused", "sad", "ashamed", "angry", "scared",
                 "disgusted", "surprised", "great"],
    "core": ["yes", "no"],
}
```

### 7.4 Étape 2 — 60 exemples de référence rédigés à la main

12 exemples par persona (60 au total), format `{"profile": {...}, "child_message": "...", "target_response": "..."}`, construits via `data/build_reference_examples.py` (une liste Python de tuples `(persona_id, child_message, target_response)`, assemblée avec le profil complet puis sérialisée en JSONL) :

```python
# data/build_reference_examples.py
EXAMPLES = [
    ("A", "I don't want to wait, it's boring.",
     "That's okay, Sam. Waiting can feel hard. Let's think about trains while we "
     "wait -- a train waits at a station before it goes. [...]"),
    # ...
    # Persona C : child_message = uniquement du vocabulaire pictogrammes réel,
    # concaténé par ", " -- exactement le format produit par child.js
    # (labels.join(", ")) quand l'enfant compose un message.
    ("C", "sad, mom",
     "You feel sad, and you are thinking about mom. That is okay to feel. "
     "Mom will be back soon. Do you want a quiet moment now?"),
    # Persona D : child_message = fragments télégraphiques, jamais de phrase
    # complète -- cohérent avec un profil "partiellement verbal".
    # Paire contrastive ajoutée délibérément (voir §7.7) : distinguer "arrêter
    # cette activité, rester en séance" de "terminer la séance".
    ("D", "no more this game.",
     "No more this game. Okay, Milo. We stop this game, but we stay together. "
     "Want bug book instead?"),
    ("D", "done. go home.",
     "You are done, and you want to go home. Okay, Milo. We finish for today. "
     "See you next time."),
]
```

```
$ python data/build_reference_examples.py
Wrote 60 handwritten examples to .../data/reference_examples.jsonl
Per persona: {'A': 12, 'B': 12, 'C': 12, 'D': 12, 'E': 12}
```

### 7.5 Étape 3 — Génération few-shot de données synthétiques

Script `data/generate_synthetic_data.py`, qui réutilise le modèle/tokenizer déjà chargés par `llm/companion.py`. Pour chaque persona : construction d'un prompt contenant le profil + les 12 exemples de référence en contexte, avec une contrainte explicite additionnelle pour C (vocabulaire pictogrammes strict) et D (fragments courts) :

```python
# data/generate_synthetic_data.py
def build_generation_prompt(persona, examples, n):
    ...
    if persona["persona_id"] == "C":
        constraint = (
            "IMPORTANT: this child is non-verbal and communicates ONLY through a "
            "pictogram grid. Every child_message MUST be a comma-separated sequence "
            f"of 1 to 4 items chosen ONLY from this exact vocabulary: {vocab_flat}."
        )
    elif persona["persona_id"] == "D":
        constraint = (
            "IMPORTANT: this child is partially verbal. Every child_message MUST "
            "stay a short fragment or telegraphic phrase (at most 5-6 words) [...] "
            "NEVER a full, grammatically complete sentence."
        )
    return f"""... Generate {n} NEW child_message/target_response pairs [...]
Answer ONLY with a JSON array [...]"""
```

**Robustesse du parsing.** Le premier essai (12 exemples demandés/persona) a échoué intégralement pour Persona B (`Expecting ',' delimiter`, une apostrophe non échappée cassant le JSON global). Plutôt que de perdre tout le lot à la moindre virgule cassée, `parse_generated_pairs()` retente d'abord un `json.loads` strict puis, en cas d'échec, retombe sur un scan par expression régulière qui récupère individuellement chaque paire bien formée :

```python
# data/generate_synthetic_data.py
PAIR_REGEX = re.compile(
    r'\{\s*"child_message"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"target_response"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}',
    re.DOTALL,
)

def generate_for_persona_with_retries(model, tokenizer, persona, examples):
    """Retente (nouvel échantillonnage à chaque fois) et cumule les résultats,
    dédupliqués par child_message, jusqu'à N_PER_PERSONA ou épuisement des
    tentatives (MAX_ATTEMPTS_PER_PERSONA = 4)."""
```

**Résultats, 2 passes :**

| Passe | Cible/persona | Exemples de référence utilisés | Résultat brut généré | Total (manuscrit + généré) |
|---|---|---|---|---|
| 1 | 12 | 6/persona (30 au total) | A=12, B=0→12 (échec JSON puis retry réussi via `regenerate_persona.py`), C=12, D=12, E=12 → **60** | 90 |
| 2 | 20 | 12/persona (60 au total) | A=21, B=20, C=20, D=21, E=21 → **103** | 163 |

### 7.6 Étape 4 — Nettoyage

`data/clean_training_data.py` combine des vérifications automatiques et une liste d'exclusion manuelle issue d'une relecture ligne par ligne de tous les exemples générés :

```python
# data/clean_training_data.py
def drop_reason(row):
    if row["source"] != "generated":
        return None                                    # les 60 manuscrits ne sont pas filtrés

    text = row["child_message"] + row["target_response"]
    if REPLACEMENT_CHAR in text:
        return "encoding corruption"

    name = row["profile"]["name"]
    if name.lower() in row["child_message"].lower():
        return f"child_message addresses persona by name ({name}) -- companion-voice bleed"

    if row["persona_id"] == "C" and not is_pictogram_valid(row["child_message"]):
        return "child_message uses words outside the real pictogram vocabulary"

    if (row["persona_id"], row["child_message"]) in MANUAL_EXCLUDE:
        return "manual exclude (physical-embodiment / off-brand content)"

    return None
```

Fausse alerte notable, corrigée en cours de route : le caractère `�` repéré à l'œil dans une réponse de Persona C n'était **pas** une corruption — c'est le codepoint Unicode `U+2019` (apostrophe typographique `'`) mal affiché par le terminal Git Bash. Vérifié précisément (`[hex(ord(c)) for c in snippet]` → `0x2019`), donc le filtre `REPLACEMENT_CHAR` (`U+FFFD`, un caractère différent) n'a, à raison, rien supprimé pour ce motif.

**Passe 1 — problèmes trouvés et supprimés (12/90) :**

| Persona | Nombre | Motif |
|---|---|---|
| A | 3 | Suppositions d'incarnation physique / auto-désignation "AI" (manuel) |
| C | 5 | Mots hors du vocabulaire pictogrammes réel (`food`, `water`, `outside`, `toys`, `alone`) |
| B | 4 | `child_message` s'adresse au persona par son prénom ("Alex, can you help me find...") — le compagnon parle à l'enfant, pas l'inverse |

**Passe 2 — problèmes trouvés et supprimés (5/163), tous manuels cette fois (0 violation automatique) :**

| Persona | `child_message` | Motif |
|---|---|---|
| A | "I don't want to share my blocks." | "watch over them" — garde physique d'objets |
| A | "I don't like the new crayon colors." | "I'll hold the paper for you" — action physique |
| B | "I want to share my dinosaur toy with you for a minute." | passation physique de jouet |
| B | "I don't like it when people don't listen to me." | **vraie métaphore** ("talk to a planet that's too far away") — viole la règle "pas de métaphores" du prompt système (§6.6) |
| B | "I asked you to pass the dinosaur toy and you took too long." | le compagnon prétend avoir physiquement raté de passer un objet |

Amélioration notable entre les deux passes : 0 violation de vocabulaire pour Persona C en passe 2 (contre 5/12 en passe 1) et 0 confusion de rôle pour B (contre 4/12) — attribuable au contexte few-shot doublé (12 exemples au lieu de 6).

**Résultat final :** `data/lora_training_data.clean.jsonl`, **158 lignes** (60 manuscrites + 98 générées) : A=31, B=29, C=32, D=33, E=33.

### 7.7 Étape 5 — Entraînement : quatre tentatives, un bug de méthodologie trouvé et corrigé

C'est l'étape la plus instructive de ce travail — un vrai bug a été trouvé grâce au suivi de la loss de validation, documenté ici tel quel plutôt que masqué.

**v1 (première tentative, avant la demande d'approfondissement) :** `q_proj`/`v_proj` uniquement, 78 exemples (passe 1), 3 epochs, pas de split de validation.

```python
# ASD-iLLM/train_livealong_lora.py (v1)
model = PeftModel.from_pretrained(base_model, ORIGINAL_LORA_PATH, is_trainable=True)
for name, param in model.named_parameters():
    is_lora = "lora_A" in name or "lora_B" in name
    is_target = any(s in name for s in ("q_proj", "v_proj"))
    param.requires_grad = bool(is_lora and is_target)
# 2 523 136 / 4 373 157 376 paramètres entraînables
```

Résultat : 30 pas, 1,4 min, `train_loss` 2,55 → 0,49. Sauvegardé dans `ASD-iLLM/lora-weight-livealong/`, puis **branché en production** (`config/config.py::LORA_PATH` redirigé vers ce dossier).

**v2 ("plus sérieux" — tous les modules, dataset doublé) :** 158 exemples (passe 2), les 7 modules cibles (20 185 088 paramètres entraînables), 4 epochs, `eval_strategy="epoch"`.

```
train_loss: 1.533 -> 0.044
eval_loss par epoch : [1.233, 1.377, 1.980, 2.157]
```

**Surapprentissage net et sans ambiguïté** : `train_loss` s'effondre vers 0 (mémorisation) pendant que `eval_loss` **empire à chaque epoch après la première**. Le script sauvegardait alors bêtement l'état final (`save_strategy="no"`, aucune sélection de checkpoint) — c'est-à-dire le **pire** epoch par la métrique de validation, et ce résultat a écrasé `lora-weight-livealong/` (donc la production).

**v3 (correction n°1 — sélection du meilleur checkpoint) :** `eval_strategy`/`save_strategy="steps"` tous les 5 pas, `load_best_model_at_end=True` sur `eval_loss`, 2 epochs. Mais la `train_loss` démarrait déjà anormalement basse (0,11 dès le premier pas). Diagnostic : `ORIGINAL_LORA_PATH` était importé depuis `config.config.LORA_PATH` — or cette valeur avait été changée entre-temps (déploiement de v1 en production, §7.9) pour pointer vers `lora-weight-livealong/`. **v2 avait donc continué l'entraînement à partir de v1, et v3 à partir de v2** — trois passes empilées sur le même petit jeu de données au lieu de trois tentatives indépendantes depuis l'original.

Vérifié précisément avant correction :

```python
>>> from config.config import LORA_PATH
>>> LORA_PATH
'...\\ASD-iLLM\\lora-weight-livealong'   # pas l'original !
```

```
$ python -c "import os, datetime; st = os.stat('ASD-iLLM/lora-weight/adapter_model.safetensors'); print(datetime.datetime.fromtimestamp(st.st_mtime))"
2026-07-09 14:54:08.608958   # inchangé depuis le tout début -- l'original n'a jamais été écrasé
```

**Correction n°2 (la vraie correction) :**

```python
# ASD-iLLM/train_livealong_lora.py (v4, final)
from config.config import LLM_MODEL   # PAS LORA_PATH

# Volontairement PAS importé depuis config.config : cette valeur est le
# defaut de PRODUCTION, qui change à chaque redéploiement. Continuer
# l'entraînement "depuis l'original" exige un chemin fixe, indépendant de
# ce que la prod pointe au moment de l'exécution.
ORIGINAL_LORA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lora-weight")
```

**v4 (résultat final, retenu) :** même méthodologie que v3, mais correctement repartie de l'original intact.

```python
# ASD-iLLM/train_livealong_lora.py (v4) -- extrait TrainingArguments
training_args = TrainingArguments(
    per_device_train_batch_size=2, gradient_accumulation_steps=4,
    num_train_epochs=2, learning_rate=1.5e-4, lr_scheduler_type="cosine",
    eval_strategy="steps", eval_steps=5,
    save_strategy="steps", save_steps=5, save_total_limit=2,
    load_best_model_at_end=True, metric_for_best_model="eval_loss",
    greater_is_better=False, gradient_checkpointing=True, bf16=True, seed=42,
)
```

```
158 total rows -> 134 train / 24 val (seed=42, stratifié par persona)
train_loss: 2.229 -> 0.539
eval_loss par pas : [(5, 1.5), (10, 1.329), (15, 1.28), (20, 1.246), (25, 1.243), (30, 1.244), (34, 1.243)]
Best checkpoint: .../checkpoint-25 (eval_loss=1.243)
Training finished in 1.9 minutes.
```

Courbe saine cette fois : décroissance régulière puis plateau net à partir du pas 20 (1,246 → 1,243 → 1,244 → 1,243), sans divergence. Meilleur point sélectionné automatiquement et sauvegardé — pas le dernier pas.

### 7.8 Étape 6 — Tests comparatifs (v4 vs original)

`data/test_livealong_lora.py` charge le modèle de base une seule fois puis les **deux** adaptateurs comme adaptateurs PEFT nommés (`load_adapter(..., adapter_name=...)` + `set_adapter(...)`), pour comparer directement original vs nouveau sans recharger le modèle de base entre les deux.

**Persona A** (`"I don't want to wait, it's boring."`) :
- Original : *"Sam, you're at the toy store and there's a long line. What do you think would happen if you didn't want to wait?"*
- v4 : *"Waiting can feel boring, but it helps everyone take turns fairly. Like a train waiting at a station, we all wait our turn."*

v4 valide directement le ressenti et utilise une comparaison explicite/littérale ("like a train") conforme à la règle "pas de métaphores" du prompt système — amélioration qualitative nette par rapport à l'original, qui introduit un scénario non sollicité ("toy store") sans validation préalable.

**Persona C** (`"no, help"`) :
- Original : *"Okay, Noor, let's tell a story about waiting in line together. Are you ready?"*
- v4 : *"I can help you wait in line, Noor. We stand together, side by side. Ready?"*

Différence modeste : v4 réagit un peu plus directement au mot "help" du message, mais aucune des deux réponses ne traite vraiment explicitement le "no".

**Persona D** (`"no more this."`) — le test critique, censé valider la paire d'exemples correctrice de §7.4 :
- Original : *"Okay, no more this. Let's try something new."* (framing correct : changer d'activité, pas de fin)
- v4 : *"No more this. We stop now. Thank you for playing, Milo."*

**Constat honnête, en comparant directement au véritable original (pas à v1) : la correction visée n'a pas clairement fonctionné.** L'original géré déjà correctement ce cas ("try something new" = pause, pas fin). v4 introduit au contraire une formulation plus orientée clôture ("we stop now... thank you for playing", proche d'un "au revoir") que l'original ne produisait pas sur ce même message. Reproduit à l'identique sur le test de fumée en production (`run_session` complet) : *"No more this, Milo. That's okay. We can stop here. See you next time!"*. Avec seulement 2 exemples contrastifs sur 158 lignes, et `do_sample=True` (un seul tirage testé), ce résultat ne permet pas de conclure à une régression généralisée, mais il ne permet pas non plus de valider la correction visée.

### 7.9 Déploiement en production et vérification

```python
# config/config.py
LORA_PATH = os.environ.get("LORA_PATH_OVERRIDE") or os.path.join(BASE_DIR, "ASD-iLLM", "lora-weight-livealong")
```

Vérifié par un appel réel au code de production (pas un script isolé) :

```
$ python -c "
from config.config import LORA_PATH; print(LORA_PATH)
from llm.companion import MODEL_AVAILABLE, run_session
print(MODEL_AVAILABLE)
print(run_session({'name': 'Sam', 'levelAutism': 3, 'sensory': ['loud noises'],
                    'interest': 'trains', 'language': 'simple, short sentences'},
                   'A story about waiting in line.',
                   [{'role': 'user', 'parts': \"I don't want to wait.\"}]))
"
...\ASD-iLLM\lora-weight-livealong
True
Sam, it's okay to feel that way. Sometimes waiting can be hard. Let me tell you a
story about waiting in line, and then we can practice together.
```

L'adaptateur ASD-iLLM original (`ASD-iLLM/lora-weight/`) reste intact et accessible en repli immédiat (`LORA_PATH_OVERRIDE`, ou modification directe de la valeur par défaut dans `config/config.py`).

### 7.10 Bilan honnête

**Ce qui a fonctionné :**
- Pipeline reproductible de bout en bout (personas → exemples manuscrits → génération few-shot avec retries → nettoyage → entraînement → validation → déploiement), chaque étape scriptée et rejouable.
- Une vraie continuation d'entraînement (poids de départ = adaptateur ASD-iLLM publié, pas un LoRA initialisé aléatoirement), confirmée en dernier ressort en v4.
- Détection réelle d'un surapprentissage (v2) et d'un bug de méthodologie (v2/v3, chemin source incorrect) grâce au split de validation ajouté spécifiquement pour ce travail — sans lui, les deux seraient passés inaperçus jusqu'à un test manuel.
- Courbe de validation finale saine (décroissance puis plateau, pas de divergence).
- Amélioration qualitative visible et reproductible sur Persona A.

**Ce qui reste limité :**
- Persona D : la correction ciblée (distinguer "pause" et "fin de séance") ne s'est pas clairement traduite dans le comportement du modèle — voir §7.8.
- 158 exemples reste un très petit jeu de données pour un fine-tuning ; le plateau de validation à `eval_loss ≈ 1.24` n'indique pas un modèle très affiné, seulement un modèle qui ne diverge plus.
- La génération few-shot (étape 3) n'est pas parfaitement fiable : échec JSON total sur B en passe 1, nécessitant un script de reprise séparé avant que le fallback par regex ne soit intégré directement dans le script principal.
- Un seul tirage par cas de test en §7.8 (`do_sample=True`) ; aucune évaluation quantitative à grande échelle n'a été faite sur le modèle entraîné (seulement 3 personas × 1 message chacun).

### 7.11 Inventaire des fichiers créés

| Fichier | Rôle |
|---|---|
| `data/personas.py` | Les 5 personas + vocabulaire pictogrammes de référence |
| `data/build_reference_examples.py` | Génère `reference_examples.jsonl` à partir des 60 exemples écrits à la main |
| `data/reference_examples.jsonl` | Les 60 exemples manuscrits (sortie du précédent) |
| `data/generate_synthetic_data.py` | Génération few-shot avec retries + fallback regex ; produit `lora_training_data.jsonl` |
| `data/regenerate_persona.py` | Reprise ciblée pour un seul persona (outil de secours) |
| `data/clean_training_data.py` | Nettoyage automatique + liste d'exclusion manuelle ; produit `lora_training_data.clean.jsonl` |
| `data/lora_training_data.jsonl` / `.clean.jsonl` | Données brutes (163 lignes) / nettoyées (158 lignes) |
| `ASD-iLLM/train_livealong_lora.py` | Script d'entraînement final (v4), avec split train/val et sélection du meilleur checkpoint |
| `ASD-iLLM/lora-weight-livealong/` | Adaptateur résultant, ~93 Mo, branché en production |
| `data/test_livealong_lora.py` | Comparaison original vs nouveau, 2 adaptateurs chargés sur le même modèle de base |
| `config/config.py` | `LORA_PATH` pointe désormais vers `lora-weight-livealong/`, avec override par variable d'environnement |

---

## 8. Les autres briques IA/ML du pipeline

### 8.1 Vue d'ensemble

Le LLM+LoRA (§6) est le composant central, mais trois autres modèles interviennent dans la chaîne, plus un module classifieur classique :

| Composant | Type de modèle | Rôle |
|---|---|---|
| Qwen2.5-7B-Instruct + LoRA ASD-iLLM | LLM (7B) + adaptateur LoRA | Génération du dialogue, analyse de séance, consolidation du profil |
| Whisper (`base.en`) | Modèle de reconnaissance vocale | Transcription voix → texte |
| TF-IDF + Régression logistique | ML classique (scikit-learn) | Détection de détresse dans les messages |
| Kokoro | Modèle de synthèse vocale | Texte → audio |
| Rhubarb | Heuristique phonétique (non-IA) | Audio → visèmes pour l'animation |
| `recommendation_service.py` | Règles pondérées (non-IA) | Choix du prochain thème d'exercice |

### 8.2 Reconnaissance vocale — Whisper

Pour les messages vocaux, l'audio envoyé par le téléphone/navigateur est transcrit en anglais avec `faster-whisper` (implémentation optimisée de Whisper, OpenAI) :

```python
# web/app.py
whisper_model = WhisperModel("base.en", device="cuda", compute_type="float16")
...
segments, _ = whisper_model.transcribe(input_path, language="en")
user_input = "".join([segment.text for segment in segments])
```

Le modèle `base.en` est un modèle Whisper de petite taille, spécialisé anglais, exécuté en `float16` sur GPU.

### 8.3 Classifieur de sécurité (détection de détresse)

Avant que le message de l'enfant soit envoyé au LLM, il passe par un classifieur à deux niveaux (`llm/safety_classifier/`) :

```python
# llm/safety_classifier/__init__.py
def classify_message(text):
    matched_rule = matches_crisis_keyword(text)   # 1. filtre par mots-clés
    if matched_rule:
        return {"risk_level": "crisis", "matched_rule": matched_rule}

    predicted = str(_pipeline.predict([text])[0])  # 2. modèle ML
    return {"risk_level": predicted, "matched_rule": None}
```

Le modèle ML (`model.joblib`) est un pipeline scikit-learn classique — **pas** un LLM :

```python
# llm/safety_classifier/train.py
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
])
```

⚠️ **Point de vigilance à conserver dans le rapport** : d'après les commentaires du code source lui-même, ce classifieur n'est aujourd'hui entraîné que sur les catégories `"none"` / `"mild_distress"` (pas d'exemples réels de `"crisis"` dans les données d'entraînement), et la liste de mots-clés est vide en attendant une validation clinique. Le mécanisme de repli (`CRISIS_SAFE_RESPONSE`) est explicitement marqué comme *placeholder non approuvé* dans le code, en attente de validation par la psychologue référente du stage. Le circuit est câblé de bout en bout et testable (voir §9), mais **la détection réelle de crise n'est pas encore opérationnelle**.

### 8.4 Synthèse vocale — Kokoro TTS

```python
# llm/tts_service.py
from kokoro import KPipeline
pipeline = KPipeline(lang_code='a')
...
generator = pipeline(text, voice='af_heart', speed=1.0)
```

Kokoro est un modèle de synthèse vocale (text-to-speech) open-source ; la voix `af_heart` est utilisée pour générer l'audio de la réponse du compagnon.

### 8.5 Lip-sync — Rhubarb (pas un modèle IA)

`llm/lip_sync.py` appelle un exécutable externe, **Rhubarb Lip Sync**, qui analyse l'audio généré pour produire des "visèmes" (`mouthCues`) synchronisant les mouvements de bouche de l'avatar :

```python
# llm/lip_sync.py
subprocess.run(
    [RHUBARB_PATH, "-f", "json", "-o", str(cues_path), str(wav_path)],
    check=True, capture_output=True,
)
```

Il s'agit d'un outil basé sur une analyse phonétique du signal audio (pas d'apprentissage automatique) — à distinguer clairement des composants IA/ML ci-dessus si le rapport doit être précis sur ce point.

---

## 9. Sécurité, confidentialité et limites d'usage

- **Cookies de session `httponly` + `SameSite=Strict`** : le jeton de session n'est jamais accessible en JavaScript côté client.
- **Rate limiting par utilisateur** (`Flask-Limiter`, clé = `uid` Firebase ou adresse IP en repli) sur toutes les routes sensibles (`/start` 10/min, `/message` et `/message_voice` 30/min, `/therapist/create_profile` 5/min, etc.), pour limiter l'abus et la charge sur le GPU.
- **Consentement parental obligatoire**, vérifié côté serveur, avant toute création de profil.
- **Quotas d'usage quotidiens** (`MAX_SESSIONS_PER_DAY = 3`, `MAX_MINUTES_PER_DAY = 45`, `database/firebase_client.py`) — explicitement documentés dans le code comme des valeurs *par défaut à faire valider par la psychologue référente*, pas une constante technique figée. Un dépassement déclenche un bandeau d'information (`usage_nudge`) côté enfant, sans bloquer la séance.
- **Pipeline de sécurité en 2 niveaux** avant chaque appel au LLM (§8.3), avec traçabilité complète des alertes (`SafetyAlerts`, acquittement horodaté par le thérapeute).
- **Séparation stricte des rôles** : chaque route API vérifie explicitement `current_user["role"]`, en plus de l'authentification.

---

## 10. Tests automatisés

La suite `tests/` (pytest, ~750 lignes cumulées) couvre :

- `test_app_session_state.py`, `test_early_end.py` : cycle de vie d'une séance (état en mémoire, fin manuelle vs fin décidée par le LLM via `<<END_EXERCISE>>`) ;
- `test_safety_integration.py` : qu'un message classé `"crisis"` court-circuite bien l'appel au LLM et crée une alerte ;
- `test_safety_classifier.py` : comportement du pipeline TF-IDF + régression logistique ;
- `test_recommendation_service.py` : le système de score du choix d'exercice (§5.1) ;
- `test_progress.py` : le calcul des statuts de progression (§5.5) ;
- `test_usage_tracking.py` : les quotas de séances/minutes quotidiens ;
- `test_companion.py` : le module `llm/companion.py`.

L'infrastructure de test (`tests/conftest.py`) fournit un **Firestore factice en mémoire** (`FakeDB`/`FakeCollection`/`FakeDocRef`, réimplémentant juste `collection/document/get/set/update`) pour tester la logique métier sans dépendre d'un vrai projet Firebase, ainsi que des variables d'environnement de test et des mocks pour les appels au LLM et à la synthèse vocale — ce qui permet de tester les routes Flask (`app.test_client()`) de bout en bout sans GPU ni réseau.

---

## 11. Historique technique et difficultés rencontrées

D'après les notes de suivi (`TODO.md`), le passage d'un LLM par API vers un LLM open-source auto-hébergé (Qwen2.5-7B + LoRA, §6) a nécessité un travail d'infrastructure non trivial :

- Installation de PyTorch avec support GPU sur une carte **RTX 5070** (architecture Blackwell, `sm_120`), non couverte par les builds PyTorch standards au moment du stage.
- Conflit entre l'installation Python 3.14 système et les environnements conda dans PowerShell / le terminal intégré VSCode — contournement trouvé en utilisant **Anaconda Prompt** directement.
- Version PyTorch retenue : `torch==2.9.1+cu128` (roue spécifique `cu128` compatible `sm_120`), installée via l'index PyTorch dédié CUDA 12.8.
- Environnement conda dédié (`livealong`, Python 3.11) avec `ms-swift`, `transformers`, `peft`, `accelerate`.

Cet épisode illustre une part significative du travail d'ingénierie du projet, indépendante du code applicatif : faire tourner un LLM 7B avec adaptateur LoRA en local sur du matériel grand public récent, ce qui a nécessité de suivre l'évolution rapide de l'écosystème CUDA/PyTorch plutôt que de s'appuyer sur une API LLM hébergée (approche initiale du projet, visible dans `ASD-iLLM/llm_api.py`, conservée comme repli).

---

## 12. Limites connues et pistes futures

D'après `TODO.md` et les commentaires laissés dans le code :

- **Interface enfant (`child.html`)** : remplacer le système actuel d'apparition/disparition d'éléments par un système de grisage (`disabled`) pour une interface plus prévisible ; revoir la navigation par flèches ; les boutons/zones devraient rester toujours visibles.
- **Détection de crise** : le classifieur de sécurité n'est pour l'instant validé que sur les catégories `"none"`/`"mild_distress"` — la liste de mots-clés et les exemples d'entraînement pour `"crisis"` doivent être fournis/validés par la psychologue référente avant tout usage réel (voir §8.3).
- **Choix d'usage du LoRA pour l'analyse** : arbitrage à faire entre utiliser le modèle spécialisé ASD-iLLM ou le modèle Qwen "nu" pour `analyze_session`/`consolidate_profile` (génération JSON structurée), voir §6.9.
- **Système de recommandation** : actuellement basé sur des règles pondérées explicites (§5.1) — un point de discussion ouvert avec la maître de stage porte sur son évolution éventuelle.
- **Suivi émotionnel** : à revoir/discuter également avec l'encadrement clinique.
- **Pictogrammes** : les catégories *Needs*, *Actions* et *People* n'ont pour l'instant que des chemins d'image prévisibles (`/static/pictograms/<id>.png`) préparés dans le code, en attendant le dépôt des visuels ARASAAC correspondants — seule la catégorie *Emotions* est entièrement illustrée à ce stade.
- **Création de profil** : pistes pour enrichir/compléter le formulaire de profil.
- **Adaptateur LoRA personnalisé (§7)** : la distinction "pause d'activité" vs "fin de séance" pour les profils partiellement verbaux/non-verbaux n'est pas résolue de façon fiable avec seulement 2 exemples contrastifs — à renforcer avec davantage d'exemples de ce type, sur plusieurs personas, avant tout usage au-delà de la démonstration. Plus largement, 158 exemples reste un jeu de données d'entraînement minimal : une évaluation quantitative plus large (au-delà de 3 personas × 1 message) serait nécessaire avant de considérer cet adaptateur comme autre chose qu'une première itération.
- **Leçon méthodologique à retenir** : tout script qui doit repartir d'un checkpoint de référence fixe doit référencer ce chemin indépendamment de la configuration de production, qui elle est censée changer. C'est l'inverse qui a causé le bug décrit en §7.7 (deux passes d'entraînement accidentellement enchaînées l'une sur l'autre).

---

## 13. Conclusion

LiveAlong combine, sur trois mois de développement, une application web complète (authentification par rôles, tableau de bord thérapeute, interface enfant multimodale, suivi longitudinal) et une chaîne IA à plusieurs étages. Le composant central reste le couple **modèle de base généraliste (Qwen2.5-7B-Instruct) + adaptateur LoRA** : parti de l'adaptateur ASD-iLLM publié (style et principes cliniques ABA appris sur un corpus réel d'interventions), le projet est allé plus loin en poursuivant son entraînement en interne sur un jeu de données construit spécifiquement pour 5 profils d'enfants représentatifs (§7) — pour un coût de stockage/maintenance minime (~93 Mo) et un adaptateur activable/désactivable indépendamment du modèle de base grâce à PEFT. Ce travail a aussi mis en évidence, de façon concrète et documentée, deux réalités du fine-tuning sur petit jeu de données : le surapprentissage guette dès qu'on ouvre trop de paramètres entraînables sans split de validation pour le détecter, et une correction ciblée (Persona D) ne se traduit pas automatiquement dans le comportement du modèle avec seulement quelques exemples contrastifs. La personnalisation fine par enfant (profil, historique, sensibilités, émotion du jour) reste ensuite injectée à l'exécution via le prompt système, sans ré-entraînement — et complétée par une couche produit dédiée (sécurité, avatar, pictogrammes CAA, suivi thérapeute) qui transforme ce modèle en un outil clinique utilisable, avec des garde-fous et des limites explicitement documentées pour la suite du travail.
