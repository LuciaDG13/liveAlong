# Rapport fichier par fichier — LiveAlong

Ce document complète [RAPPORT_IA_LORA.md](RAPPORT_IA_LORA.md) (organisé par thème : architecture, IA/LoRA, sécurité, tests...) avec une lecture **fichier par fichier** : objectif et fonctionnement de chaque fichier de code du dépôt. Pour l'histoire complète de l'entraînement LoRA personnalisé (personas, données, bug de méthodologie, résultats), voir `RAPPORT_IA_LORA.md` §7 — ce document n'en redonne qu'un résumé pointeur pour éviter la duplication.

## 0. Logique générale

LiveAlong est une application Flask à deux interfaces (enfant / thérapeute), adossée à Firebase (Auth + Firestore) et à un pipeline IA local (LLM + LoRA, Whisper, Kokoro TTS, classifieur de sécurité). Le flux d'un tour de dialogue :

```
Enfant (voix / texte / pictogrammes)
  → web/app.py (route /message ou /message_voice)
    → [voix] llm/lip_sync.py appelle Whisper pour transcrire
    → llm/safety_classifier vérifie le message
    → llm/companion.py::run_session() génère la réponse (LLM + LoRA)
    → llm/tts_service.py + llm/lip_sync.py génèrent audio + visèmes
  → réponse JSON renvoyée au navigateur (web/static/js/child.js l'affiche/anime)
```

Chaque dossier du dépôt correspond à une responsabilité : `config/` (paramètres), `database/` (accès Firestore), `llm/` (IA), `web/` (serveur Flask + frontend), `user_profiles/` (lecture de profil), `tests/` (pytest), `ASD-iLLM/` (dépôt de recherche vendorisé + notre entraînement), `data/` (notre pipeline de données pour le LoRA personnalisé).

---

## 1. Racine du projet

### `main.py`
**Objectif :** point d'entrée CLI pour tester une session de bout en bout sans passer par le serveur web (utile en développement).
**Fonctionnement :** charge un profil fixe (`user_id` codé en dur), crée une session Firestore, lance une boucle `input()`/`print()` dans le terminal qui appelle `run_session()` à chaque message, puis `analyze_session()` + `consolidate_profile()` + `update_profile_insights()` quand l'utilisateur tape `"fin"`. C'est le squelette minimal du flux repris ensuite par `web/app.py`.

### `README.md`
**Objectif :** présentation d'une phrase du projet + instructions d'installation (`pip install -r requirements.txt`).

### `TODO.md`
**Objectif :** notes de suivi de stage, pas de la documentation figée. Contient trois catégories : améliorations UX à faire sur `child.html`, points à trancher avec la maîtresse de stage (recommandation, suivi émotionnel, migration LLM), et le journal de la migration vers un LLM local (RTX 5070/Blackwell, conflit PowerShell/conda — voir RAPPORT_IA_LORA.md §11).

### `requirements.txt`
**Objectif :** dépendances Python de l'application web (Flask, firebase-admin, transformers, peft, bitsandbytes, faster-whisper, kokoro, sendgrid, dicebear, pdfplumber, pytest...).

### `package.json`
**Objectif :** dépendances JS *documentées* pour le frontend (`firebase`, `@mui/icons-material`) — en pratique le frontend charge ces librairies directement via CDN/ESM dans les fichiers HTML/JS (`import ... from "https://cdn.jsdelivr.net/..."`), ce fichier sert surtout de référence de versions.

### `poster_lora_comparison.py`
**Objectif :** script ponctuel pour générer un exemple avant/après LoRA à des fins de poster/démonstration.
**Fonctionnement :** importe `model`, `tokenizer`, `run_session` depuis `llm/companion.py` (donc utilise l'adaptateur actuellement configuré en production), puis pour 2 profils (Sam, Alex) génère une réponse avec `model.disable_adapter()` (modèle nu) et une réponse normale (adaptateur actif), sur la même entrée. Détaillé dans RAPPORT_IA_LORA.md §6.10.

### `poster_lora_diagram.svg`, `poster_lora_visual.html`, `poster_lora_visual.png`
**Objectif :** supports visuels statiques (schéma LoRA, page HTML de présentation, export image) produits pour le poster de stage — pas de logique applicative, pas détaillés ligne à ligne ici.

---

## 2. `config/`

### `config.py`
**Objectif :** point d'entrée unique pour tous les paramètres de configuration (clés API, chemins, constantes du modèle) — **exclu du suivi Git** (`.gitignore`).
**Fonctionnement :**
```python
API_KEY = _require_env("GOOGLE_API_KEY")
SENDGRID_API_KEY = _require_env("SENDGRID_API_KEY")
SENDGRID_SENDER = _require_env("SENDGRID_SENDER")
FIREBASE_CREDENTIALS_PATH = _require_env("FIREBASE_CREDENTIALS_PATH")
LORA_PATH = os.environ.get("LORA_PATH_OVERRIDE") or os.path.join(BASE_DIR, "ASD-iLLM", "lora-weight-livealong")
LLM_MODEL = "Qwen/Qwen2.5-7B-Instruct"
LLM_MAX_TOKENS = 1500
RHUBARB_PATH = os.path.join(BASE_DIR, "Rhubarb", "rhubarb.exe")
```
`_require_env()` lève une `RuntimeError` explicite si une variable d'environnement obligatoire manque, plutôt que de laisser l'app démarrer dans un état à moitié configuré. `LORA_PATH` accepte un override par variable d'environnement (`LORA_PATH_OVERRIDE`) — ajouté pour pouvoir tester un nouvel adaptateur sans modifier le chemin par défaut utilisé en production (voir RAPPORT_IA_LORA.md §7.9).

### `__init__.py`
Vide — marque `config` comme package Python importable.

---

## 3. `database/`

### `firebase_client.py`
**Objectif :** unique point d'accès à Firestore et à Firebase Auth (aucun autre fichier n'importe `firebase_admin` directement) — implémente toutes les opérations de lecture/écriture pour les 5 collections (voir RAPPORT_IA_LORA.md §2).
**Fonctionnement (fonctions principales) :**
- `get_exercise`, `get_exercises_by_level` : lecture de `SocialStories`.
- `create_session`, `save_message`, `close_session` : cycle de vie d'une séance ; `close_session` calcule la durée écoulée (`_elapsed_minutes`) et met à jour les compteurs d'usage quotidien.
- `get_usage_today`, `_bump_usage_session_count`, `_add_usage_minutes`, `_usage_flag` : quotas journaliers (`MAX_SESSIONS_PER_DAY = 3`, `MAX_MINUTES_PER_DAY = 45`), avec remise à zéro automatique si la date stockée n'est pas celle du jour.
- `create_user_profile`, `create_auth_account` (avec `set_custom_user_claims(role='child')`), `send_temp_password` (SendGrid), `delete_child_profile` : gestion du cycle de vie d'un profil enfant.
- `update_profile_insights` : ajoute les insights de fin de séance à `session_insights[]` et remplace `consolidated_profile`.
- `save_emotion_entry`, `get_emotion_entries_for_user` : check-ins émotionnels.
- `create_safety_alert`, `get_unacknowledged_alerts`, `acknowledge_alert` : alertes de sécurité.

### `__init__.py`
Vide.

---

## 4. `user_profiles/`

### `user_profile.py`
**Objectif :** adapte le document Firestore brut d'un profil au format attendu par `llm/companion.py::run_session()`.
**Fonctionnement :** `get_user_profile(user_id)` lit `Profiles/{user_id}`, puis dérive deux champs synthétiques absents du document brut :
- `profile["sensory"]` = liste des valeurs non vides parmi les 5 champs `sensory-*` (auditif/visuel/tactile/olfactif/gustatif) ;
- `profile["sensory_categories"]` = les *noms* des catégories concernées (utilisé par `recommendation_service.py` pour détecter les conflits sensoriels avec une histoire).

### `__init__.py`
Vide.

---

## 5. `utils/`

### `__init__.py`
Fichier vide — package placeholder, actuellement inutilisé (aucun autre fichier n'importe `utils`).

---

## 6. `llm/`

### `companion.py`
**Objectif :** cœur du système IA — charge le LLM + adaptateur LoRA et expose les 3 fonctions utilisées par le reste de l'app. Détaillé en profondeur dans RAPPORT_IA_LORA.md §6.
**Fonctionnement (résumé) :**
- Au chargement du module : `AutoModelForCausalLM.from_pretrained` en 4-bit NF4 (`bitsandbytes`) + `PeftModel.from_pretrained(base_model, LORA_PATH)`. Si ça échoue (pas de GPU, dépendances absentes...), `MODEL_AVAILABLE = False` et les 3 fonctions ci-dessous renvoient un message d'erreur au lieu de planter.
- `run_session(user_profile, exercise, conversation_history, today_emotion=None)` : construit le prompt système (profil + exercice + résumé des insights précédents), génère avec `do_sample=True, temperature=0.7`.
- `analyze_session(user_profile, conversation_history, theme)` : demande un résumé JSON structuré (`summary`, `difficulties`, `progress`, `recommended_next_Theme`, `understanding`) en génération déterministe (`do_sample=False`).
- `consolidate_profile(user_profile, new_insights)` : fusionne les nouveaux insights dans le profil consolidé persistant (`stable_traits`, `emerging_difficulties`, `resolved_difficulties`), lit `new_insights.get('difficulties'|'progress'|'understanding')` — aligné sur le schéma réel produit par `analyze_session` (corrigé en cours de stage, un précédent bug lisait des clés jamais produites).

### `tts_service.py`
**Objectif :** synthèse vocale (texte → audio).
**Fonctionnement :** initialise un `KPipeline` Kokoro (`lang_code='a'`) au chargement du module. `synthesize_speech(text)` génère l'audio par segments, les concatène (`numpy`), les encode en WAV puis en base64. Renvoie `None` si le pipeline n'a pas pu s'initialiser ou si `text` est vide — jamais d'exception propagée vers l'appelant.

### `lip_sync.py`
**Objectif :** synchronisation labiale — convertit l'audio généré en une liste de "visèmes" (formes de bouche + timing).
**Fonctionnement :** `synthesize_speech_with_lip_sync(text)` appelle `tts_service.synthesize_speech`, écrit l'audio dans un fichier `.wav` temporaire, exécute l'exécutable externe **Rhubarb Lip Sync** (`subprocess.run([RHUBARB_PATH, "-f", "json", ...])`), lit le JSON de sortie (`mouthCues`), puis nettoie les fichiers temporaires (`finally`). Pas un modèle IA — analyse phonétique classique du signal audio.

### `safety_classifier/__init__.py`
**Objectif :** classification de risque (`"none"` / `"mild_distress"` / `"crisis"`) sur chaque message enfant, en 2 couches. Détaillé en RAPPORT_IA_LORA.md §8.3.
**Fonctionnement :** `classify_message(text)` vérifie d'abord `matches_crisis_keyword` (mots-clés déterministes), puis si rien ne matche, appelle le pipeline scikit-learn chargé depuis `model.joblib`. "Fail open" : si le modèle ne charge pas, renvoie toujours `"none"` plutôt que de bloquer l'app.

### `safety_classifier/keywords.py`
**Objectif :** filtre déterministe à haut rappel pour du langage de crise non ambigu.
**Fonctionnement :** `CRISIS_KEYWORDS = []` — **volontairement vide**. Le commentaire en tête de fichier est explicite : toute phrase ajoutée ici doit être validée avec la psychologue référente au préalable, pas ajoutée unilatéralement. `matches_crisis_keyword(text)` fait une recherche de sous-chaîne insensible à la casse.

### `safety_classifier/train.py`
**Objectif :** (ré)entraîne le classifieur depuis `data/train.csv` / `data/eval.csv`.
**Fonctionnement :** `Pipeline([TfidfVectorizer(ngram_range=(1,2)), LogisticRegression(class_weight="balanced")])`, entraîné puis sauvegardé via `joblib.dump`. Le jeu d'entraînement ne contient actuellement aucun exemple `"crisis"` (voir `data/README.md`), donc le modèle ne peut distinguer que `"none"` / `"mild_distress"`.

---

## 7. `web/` (backend Flask)

### `app.py`
**Objectif :** toutes les routes HTTP de l'application — c'est le fichier qui relie authentification, base de données, IA et frontend.
**Fonctionnement (par groupe de routes) :**
- **Pages** : `/`, `/child_interface`, `/therapist`, `/therapist/profiles`, `/child_interface/avatar-setup` — rendent les templates, protégés par `page_login_required` (sauf `/`).
- **Session enfant** : `/start` (choisit l'exercice via `recommend_exercise`, crée la session, appelle `run_session` pour le premier message), `/message` et `/message_voice` (transcrivent la voix via Whisper puis traitent comme `/message`), `/end` (clôture manuelle). Toutes vérifient `current_user["role"] == "child"` et sont limitées en débit (`@limiter.limit`).
- **État en mémoire** : `active_sessions` (dict global) + `get_state(uid)`/`clear_state(uid)` — état de conversation par utilisateur, isolé (testé dans `tests/test_app_session_state.py`).
- **Sécurité** : `check_message_safety` appelle `classify_message` avant `run_session` ; si `"crisis"`, court-circuite avec `CRISIS_SAFE_RESPONSE` (placeholder explicitement marqué non approuvé pour de vrais enfants) et crée une alerte.
- **Thérapeute** : `/therapist/create_profile` (création + consentement parental obligatoire + rollback si email/profil échoue), `/api/profiles`, `/api/profiles/<id>/details`, `/api/profiles/<id>/alerts/<id>/acknowledge`, `/therapist/delete_profile/<id>`.
- **Auth** : `/auth/verify` (échange le token Firebase contre un cookie de session httponly).
- **Divers** : `/api/avatar/save`, `/api/emotion/checkin`, `/api/progress` (calcule les statuts `confident`/`practicing`/`started` par thème via `_status_for_theme`/`_status_for_count`).
- Initialise aussi `whisper_model = WhisperModel("base.en", device="cuda", compute_type="float16")` et `limiter = Limiter(key_func=rate_limit_key, ...)` (clé = uid Firebase, repli sur IP).

### `auth.py`
**Objectif :** vérification de session et décorateurs de protection des routes.
**Fonctionnement :** `get_decoded_session()` lit le cookie `session`, le vérifie via `firebase_admin.auth.verify_session_cookie`. `login_required` (renvoie 401 JSON si absent/invalide) et `page_login_required` (redirige vers `/`) sont deux décorateurs qui injectent `current_user` dans la fonction de route.

### `avatar_service.py`
**Objectif :** génère le SVG d'un avatar procédural.
**Fonctionnement :** `generate_avatar_svg(seed, options)` construit un objet `Avatar` de la librairie `dicebear` (style `"big-smile"`), avec `mouthVariant=[]` — la bouche est volontairement laissée vide côté génération, gérée séparément et dynamiquement par `avatar-speech-sync.js` côté client.

### `recommendation_service.py`
**Objectif :** choisit le thème de la prochaine séance par un système de score explicite (pas un modèle appris). Détaillé en RAPPORT_IA_LORA.md §5.1.
**Fonctionnement :** `score_story()` additionne/soustrait des points selon 6 règles (répétition récente, difficulté émergente du profil consolidé, conflit sensoriel, correspondance d'intérêt, émotion négative passée sur ce thème, et une règle conditionnelle sur l'émotion du jour). `recommend_exercise()` trie et retourne le meilleur score. Entièrement déterministe, testé dans `tests/test_recommendation_service.py`.

### `pdf_to_firestore.py`
**Objectif :** outil CLI (pas appelé par l'app web) pour transcrire une histoire sociale depuis un PDF source vers Firestore, pour les 3 niveaux TSA à la fois.
**Fonctionnement :** `extract_pdf_text` (via `pdfplumber`) extrait le texte source ; pour chaque niveau (1/2/3), `get_story_for_level` propose soit un brouillon généré par le LLM local (`--llm`, via `generate_llm_draft`, import paresseux de `llm.companion` pour ne payer le coût de chargement du modèle qu'en mode LLM), soit un squelette vide à remplir à la main (`build_manual_skeleton`), suivant le gabarit narratif "Carol Gray" (`CAROL_GRAY_TEMPLATE`) et des consignes de simplification par niveau (`LEVEL_GUIDANCE`). `open_for_editing` ouvre le brouillon dans l'éditeur par défaut (Notepad sous Windows) et attend une validation manuelle (`input()`) avant de continuer — **rien n'est écrit dans Firestore sans confirmation explicite** (`"Save these 3 documents to Firestore now?"`).

---

## 8. `web/templates/` (pages HTML, rendues par Flask)

| Fichier | Rôle |
|---|---|
| `login.html` | Formulaire email/mot de passe, appelle `login.js`. Pas de logique métier, juste le formulaire + import du script. |
| `index.html` | Écran de sélection de profil (Enfant / Thérapeute) après connexion réussie — deux zones cliquables superposées à une illustration (`image-zone-left`/`-right`). |
| `select-profile.html` | Coquille pour le tableau de bord thérapeute (liste + détail de profil) — toute la logique est dans `select-profile.js`. |
| `therapist.html` | Page d'accueil thérapeute : 2 boutons ("Create Profile" / "View Profiles"), pas de logique propre. |
| `creation-profile.html` | Formulaire multi-étapes (321 lignes) de création de profil enfant — champs identité, communication, sensoriel, contexte clinique, avatar de départ ; logique portée par `creation-profile.js`. |
| `avatar-setup.html` | Éditeur d'avatar (coiffure/yeux/couleurs/accessoires) affiché après la première connexion enfant ; logique dans `avatar-setup.js`. |
| `child.html` | La page principale de l'enfant : onglets Home/Chat/Progress, zone avatar, zone micro + pictogrammes, écran de fin — voir RAPPORT_IA_LORA.md §5 pour le détail complet de cette interface. |

Toutes ces pages partagent `web/static/css/common.css` et chargent Bootstrap/Bootstrap Icons via CDN ; les pages protégées importent `auth.js` et appellent `requireAuth("child"|"therapist")`.

---

## 9. `web/static/js/` (frontend)

### `firebase-init.js`
**Objectif :** initialise le SDK Firebase côté client (config publique — voir RAPPORT_IA_LORA.md §9 sur la non-sensibilité de cette clé). Exporte `db` (Firestore, non utilisé directement ailleurs — tout passe par l'API Flask) et `firebaseAuth`.

### `auth.js`
**Objectif :** authentification côté client et protection des pages.
**Fonctionnement :** `signIn` (Firebase `signInWithEmailAndPassword`), `verifyWithBackend` (POST `/auth/verify`), `requireAuth(expectedRole)` (vérifie le token stocké en `sessionStorage`, redirige vers `/` si invalide ou si le rôle ne correspond pas à la page), `signOut`/`clearClientSession`, et un écouteur global de clic pour tout bouton/lien `#btn-logout` ou `[data-confirm-logout]` (avec confirmation `window.confirm`).

### `api.js`
**Objectif :** 3 wrappers `fetch` minces vers les routes de session (`startSession`, `sendMessage`, `endSession`) — centralise les appels réseau utilisés par `child.js`.

### `login.js`
**Objectif :** logique du bouton de connexion sur `login.html`. Appelle `signIn` puis `verifyWithBackend`, redirige vers `result.redirect_url`, désactive le bouton pendant la requête.

### `select-profile.js` (374 lignes)
**Objectif :** tableau de bord thérapeute complet. Détaillé en RAPPORT_IA_LORA.md §4.2.
**Fonctionnement :** `loadProfiles`/`renderProfiles` (liste + badges alerte/usage), `loadProfileDetails` (agrège récapitulatif, alertes, heatmap émotionnelle 12 semaines construite en JS pur, historique de conversation), gestion de la recherche (filtrage côté client), acquittement d'alerte, suppression de profil avec confirmation.

### `creation-profile.js`
**Objectif :** logique du formulaire multi-étapes de création de profil.
**Fonctionnement :** navigue entre les `.form-step` (`currentStep`), valide chaque étape via l'API native `checkValidity()`/`reportValidity()` avant d'avancer, génère un récapitulatif final (`generateRecap`, avec échappement HTML), avertit avant de quitter la page si le formulaire a été modifié (`isDirty` + `beforeunload`), puis `POST /therapist/create_profile` à la soumission.

### `avatar-setup.js`
**Objectif :** éditeur d'avatar interactif.
**Fonctionnement :** importe la librairie Dicebear directement en ESM depuis un CDN, maintient un `state` local (coiffure/yeux/couleurs/accessoire), régénère un aperçu SVG (`renderMainPreview`) et des rangées de vignettes cliquables (`renderVariantRow`/`renderColorRow`) à chaque changement, puis `POST /api/avatar/save` à la confirmation.

### `avatar-speech-sync.js`
**Objectif :** anime la bouche de l'avatar en synchronisation avec l'audio joué. Détaillé en RAPPORT_IA_LORA.md §5.4.
**Fonctionnement :** `RHUBARB_MOUTHS` définit 7 formes de bouche en SVG (nomenclature Rhubarb A–F, X) ; la classe `AvatarSpeechPlayer` charge les `mouthCues` renvoyés par le backend et, à chaque frame (`requestAnimationFrame`), sélectionne la forme dont le `start` est le plus proche (sans le dépasser) du `audio.currentTime` courant.

### `speech.js`
**Objectif :** capture vocale avec détection automatique de fin de parole. Détaillé en RAPPORT_IA_LORA.md §5.3.
**Fonctionnement :** `MediaRecorder` + `AudioContext`/`AnalyserNode` pour mesurer le niveau sonore en continu ; une phase de calibration de 400 ms mesure le bruit ambiant (`ambientNoiseLevel`), puis l'enregistrement s'arrête automatiquement après 4 s sans dépasser ce niveau + une marge. Envoie le blob audio à `POST /message_voice`.

### `pictograms.js`
**Objectif :** grille de communication alternative et améliorée (CAA). Détaillé en RAPPORT_IA_LORA.md §5.3.
**Fonctionnement :** deux tableaux de données (`pictograms` par catégorie, `responses` = Oui/Non), rendus respectivement dans une grille filtrée par onglet (`renderGrid`/`switchPictogramCategory`) et une barre fixe toujours visible (`renderCoreBar`) ; `addToSelection` limite à 5 pictogrammes sélectionnés ; `renderEmotionCheckin` réutilise la catégorie "emotions" pour l'écran d'accueil.

### `child.js` (286 lignes)
**Objectif :** orchestre toute l'interface enfant (onglets, session, avatar, fin de séance, progression). Détaillé en RAPPORT_IA_LORA.md §5.
**Fonctionnement :** `switchTab`/`showChatState` gèrent la navigation ; `revealMainSession` attend la promesse de démarrage de session et déclenche l'affichage de l'avatar + première réponse ; `renderAvatar` injecte le SVG de l'avatar et y ajoute dynamiquement un groupe `<g id="avatar-mouth">` (avec un panneau de calibrage caché derrière `?debug=1`) ; `renderAIResponse` joue l'audio synchronisé ou affiche l'écran de fin si `<<END_EXERCISE>>` a été détecté côté serveur ; `notifyChildSessionEnd` envoie un signal `sendBeacon` sur `pagehide` pour ne pas laisser de séance orpheline en cas de fermeture d'onglet.

---

## 10. `web/static/css/`

8 fichiers, un par page (`login.css`, `index.css`, `select-profile.css`, `therapist.css`, `creation-profile.css`, `avatar-setup.css`, `child.css`) + `common.css` (partagé : header, barre de navigation `#app-nav-bar`, variables de couleur). Pas de logique applicative — `child.css` est le plus dense (grille de pictogrammes, barre core, tuiles de progression, heatmap) et documente en commentaires plusieurs choix délibérés (ex. couleurs pastel désaturées pour un public sensible, `.hidden` en `visibility` plutôt que `display` pour ne pas faire bouger la mise en page).

---

## 11. `tests/`

| Fichier | Ce qui est testé |
|---|---|
| `conftest.py` | Fixtures partagées : `FakeDB`/`FakeCollection`/`FakeDocRef` (Firestore factice en mémoire, juste `collection/document/get/set/update`), variables d'environnement de test, fixtures `mocked_app_module`/`mocked_firebase_client`. |
| `test_companion.py` | Que `llm.companion` bascule proprement en mode dégradé (`MODEL_AVAILABLE = False`) si le chargement du modèle échoue, sans planter l'app. |
| `test_app_session_state.py` | Que `active_sessions` est bien isolé par utilisateur (`get_state`/`clear_state`) et qu'une requête `/message` d'un enfant ne fuite jamais dans l'historique d'un autre. |
| `test_early_end.py` | Que le tag `<<END_EXERCISE>>` déclenche bien `finalize_session` et est retiré du texte renvoyé ; qu'une réponse normale ne termine pas la session ; que `close_session` enregistre correctement `ended_by`. |
| `test_safety_integration.py` | Qu'un message classé `"crisis"` court-circuite `run_session` et crée une alerte, de bout en bout via `app.test_client()`. |
| `test_safety_classifier.py` | Comportement du pipeline TF-IDF + régression logistique, repli si le modèle est absent, priorité du filtre par mots-clés sur le modèle ML, et que `CRISIS_KEYWORDS` est toujours vide (test-sentinelle explicite pour ne pas l'oublier). |
| `test_recommendation_service.py` | Chaque règle de `score_story` isolément (répétition, difficulté émergente, conflit sensoriel, intérêt, émotion négative passée/du jour). |
| `test_progress.py` | Le regroupement des thèmes par statut (`confident`/`practicing`/`started`) dans `/api/progress`. |
| `test_usage_tracking.py` | `_usage_flag`, `_elapsed_minutes` (y compris les cas limites : horodatage invalide, dérive d'horloge donnant une durée négative), et le comportement des compteurs journaliers à cheval sur un changement de date. |

---

## 12. `ASD-iLLM/` (dépôt de recherche vendorisé + entraînement LiveAlong)

Dossier entièrement exclu du suivi Git (`.gitignore: ASD-iLLM/`). Contient à la fois le dépôt publié par les auteurs du papier ASD-iLLM (EMNLP 2025) et le travail d'entraînement propre à LiveAlong.

### Fichiers vendorisés (auteurs originaux, non modifiés)
| Fichier | Rôle |
|---|---|
| `README.md`, `LICENSE` | Présentation du papier et licence du dépôt original. |
| `sft.py` | Script d'entraînement LoRA original (Qwen2.5-3B, `LoraConfig(r=8, alpha=32)`, `Seq2SeqTrainer`) — illustre la méthode, pas exécuté par LiveAlong. |
| `inference.py` | Classe `LLMInference` + script de test en ligne de commande, basés sur `ms-swift` plutôt que `transformers`/`peft` bruts. |
| `llm_api.py` | Appel à un LLM via API OpenAI-compatible (`gpt-4o-mini` etc.) — approche initiale du projet avant la bascule vers un modèle local. |
| `eval.py`, `utils.py`, `data_synthesis_and_augmentation.py` | Scripts d'évaluation et de synthèse de données des auteurs (prompts en chinois, pipeline propre à leur méthodologie de recherche) — non exécutés par LiveAlong. |
| `lora-weight/` | L'adaptateur ASD-iLLM original publié — voir RAPPORT_IA_LORA.md §6.4. Jamais modifié. |

### Fichiers propres à LiveAlong
| Fichier | Rôle |
|---|---|
| `train_livealong_lora.py` | Script d'entraînement final (v4) : poursuit l'entraînement de `lora-weight/` sur `data/lora_training_data.clean.jsonl`, split train/val stratifié par persona, sélection automatique du meilleur checkpoint par `eval_loss`. Récit complet du développement (4 versions, un bug de méthodologie trouvé et corrigé) en RAPPORT_IA_LORA.md §7.7. |
| `lora-weight-livealong/` | Résultat de ce script, ~93 Mo — adaptateur branché en production (`config/config.py::LORA_PATH`). |

---

## 13. `data/` (pipeline de données pour le LoRA personnalisé)

Tous ces fichiers sont le produit du travail décrit en détail dans RAPPORT_IA_LORA.md §7 — résumé ici, pointeur pour le récit complet (résultats, chiffres, bilan honnête).

| Fichier | Rôle |
|---|---|
| `personas.py` | Définit les 5 personas (profils + vocabulaire pictogrammes réel de `pictograms.js`). |
| `build_reference_examples.py` | Assemble 60 exemples écrits à la main (12/persona) en `reference_examples.jsonl`. |
| `generate_synthetic_data.py` | Génération few-shot avec le modèle de `llm.companion`, retries automatiques + repli par expression régulière si le JSON casse ; produit `lora_training_data.jsonl`. |
| `regenerate_persona.py` | Outil de secours pour régénérer un seul persona a posteriori. |
| `clean_training_data.py` | Filtres automatiques (corruption, confusion de rôle, vocabulaire pictogrammes) + liste d'exclusion manuelle ; produit `lora_training_data.clean.jsonl` (158 lignes), le fichier réellement utilisé pour l'entraînement. |
| `test_livealong_lora.py` | Compare directement l'adaptateur original et le nouveau (2 adaptateurs PEFT nommés chargés sur le même modèle de base). |
| `lora_training_data.jsonl` / `.clean.jsonl` | Données brutes / nettoyées. |

---

## 14. Fichiers de configuration et secrets (non versionnés)

| Fichier | Rôle |
|---|---|
| `.env` | Valeurs réelles des variables requises par `config/config.py` (clés API, chemin des credentials Firebase). |
| `.env.example` | Gabarit vide, versionné, documentant les clés attendues. |
| `livealong-a8e0b-firebase-adminsdk-*.json` | Clé de service Firebase Admin (accès serveur complet à Firestore/Auth) — exclue du Git. |
| `.gitignore` | Exclut notamment `config/config.py`, `.env`, la clé Firebase Admin, tout `ASD-iLLM/`, et le dossier `RHUBARB/`. |
