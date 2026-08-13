const grid = document.getElementById("pictogram_grid");

// Affiche/masque l'indice "plus de pictos en dessous" (.pictogram-scroll-hint,
// cf. child.css) selon que la grille déborde et selon la position de scroll --
// évite qu'un enfant ne se rende jamais compte qu'il manque des pictogrammes
// hors champ.
function updateGridScrollHint() {
    const overflowing = grid.scrollHeight > grid.clientHeight + 1;
    const atBottom = grid.scrollTop + grid.clientHeight >= grid.scrollHeight - 1;
    grid.classList.toggle("has-more-below", overflowing && !atBottom);
}
grid.addEventListener("scroll", updateGridScrollHint);

// Métadonnées des catégories : label affiché sur l'onglet, icône de
// navigation (juste pour l'onglet, pas pour les pictogrammes eux-mêmes) et
// couleur associée. La couleur est appliquée à la fois sur l'onglet et sur
// les cartes pictos de la catégorie (cf. child.css, sélecteurs
// [data-category]) pour que le repère visuel reste cohérent dans toute
// l'interface. Tons volontairement pastel/désaturés (pas de couleurs vives
// ou clignotantes) pour ne pas surcharger un public sensible sur le plan
// sensoriel.
//
// Tout le texte affiché à l'enfant (labels, catégories) doit rester en
// anglais, comme le reste de l'app (cf. "Answer in English" dans le prompt
// système de companion.py) -- seuls les commentaires sont en français.
const categories = [
    { id: "needs", label: "Needs", icon: "bi-life-preserver" },
    { id: "actions", label: "Actions", icon: "bi-joystick" },
    { id: "people", label: "People", icon: "bi-people-fill" },
    { id: "emotions", label: "Emotions", icon: "bi-emoji-smile" },
];

// Tableau plat : un pictogramme = un objet {id, label, src, category}.
// `category` sert au filtrage de renderGrid() selon l'onglet actif.
//
// NOTE -- les images n'existent pas encore pour les catégories needs /
// actions / people (seules les 8 émotions ont déjà un fichier réel dans
// web/static/pictograms/). Le chemin est prévisible (/static/pictograms/<id>.png)
// pour pouvoir déposer les fichiers ARASAAC directement sans retoucher le
// code -- voir la liste des mots-clés de recherche fournie séparément.
const pictograms = [
    // --- Needs (vocabulaire core, haute fréquence) ---
    { id: "i-want", label: "I want", src: "/static/pictograms/i-want.png", category: "needs" },
    { id: "i-need", label: "I need", src: "/static/pictograms/i-need.png", category: "needs" },
    { id: "more", label: "More", src: "/static/pictograms/more.png", category: "needs" },
    { id: "stop", label: "Stop", src: "/static/pictograms/stop.png", category: "needs" },
    { id: "help", label: "Help", src: "/static/pictograms/help.png", category: "needs" },
    { id: "done", label: "Done", src: "/static/pictograms/done.png", category: "needs" },

    // --- Actions ---
    { id: "play", label: "Play", src: "/static/pictograms/play.png", category: "actions" },
    { id: "eat", label: "Eat", src: "/static/pictograms/eat.png", category: "actions" },
    { id: "drink", label: "Drink", src: "/static/pictograms/drink.png", category: "actions" },
    { id: "sleep", label: "Sleep", src: "/static/pictograms/sleep.png", category: "actions" },
    { id: "go-out", label: "Go out", src: "/static/pictograms/go-out.png", category: "actions" },
    { id: "go", label: "Go", src: "/static/pictograms/go.png", category: "actions" },

    // --- People ---
    { id: "mom", label: "Mom", src: "/static/pictograms/mom.png", category: "people" },
    { id: "dad", label: "Dad", src: "/static/pictograms/dad.png", category: "people" },
    { id: "therapist", label: "Therapist", src: "/static/pictograms/therapist.png", category: "people" },
    { id: "me", label: "Me", src: "/static/pictograms/me.png", category: "people" },
    { id: "you", label: "You", src: "/static/pictograms/you.png", category: "people" },


    // --- Emotions (images déjà existantes, conservées telles quelles) ---
    { id: "happy", label: "Happy", src: "/static/pictograms/happy.png", category: "emotions" },
    { id: "confused", label: "Confused", src: "/static/pictograms/confused.png", category: "emotions" },
    { id: "sad", label: "Sad", src: "/static/pictograms/sad.png", category: "emotions" },
    { id: "ashamed", label: "Ashamed", src: "/static/pictograms/ashamed.png", category: "emotions" },
    { id: "angry", label: "Angry", src: "/static/pictograms/angry.png", category: "emotions" },
    { id: "scared", label: "Scared", src: "/static/pictograms/scared.png", category: "emotions" },
    { id: "disgusted", label: "Disgusted", src: "/static/pictograms/disgusted.png", category: "emotions" },
    { id: "surprised", label: "Surprised", src: "/static/pictograms/surprised.png", category: "emotions" },
    {id: "great", label: "Great", src: "/static/pictograms/great.png", category: "emotions" },
];

// Réponses oui/non : vocabulaire le plus utilisé de tous, donc affiché à
// part dans une barre fixe (#pictogram-core-bar), toujours visible quel que
// soit l'onglet ouvert -- pas de tap de navigation supplémentaire pour dire
// "non" (principe de vocabulaire core en CAA).
const responses = [
    { id: "yes", label: "Yes", src: "/static/pictograms/yes.png" },
    { id: "no", label: "No", src: "/static/pictograms/no.png" },
];

let activeCategory = categories[0].id;

function getPictogramsByCategory(categoryId) {
    return pictograms.filter(p => p.category === categoryId);
}

function createPictogramVisual(pictogram, sizeClass) {
    const img = document.createElement("img");
    img.src = pictogram.src;
    img.alt = pictogram.label;
    img.classList.add(sizeClass);
    return img;
}

function addToSelection(pictogram) {
    const selection = document.getElementById("selected-pictograms");

    const deja = selection.children.length;
    if (deja >= 5) return;
    if (deja == 0) {
        document.getElementById("buttons-pict").classList.add("visible");        
        document.getElementById("btn-micro").setAttribute("hidden", "");
    }

    selection.appendChild(createPictogramVisual(pictogram, "pictogram-visual-sm"));
}

function renderCoreBar() {
    const bar = document.getElementById("pictogram-core-bar");
    if (!bar) return;
    bar.innerHTML = "";

    responses.forEach(pictogram => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "pictogram-core-btn";

        btn.appendChild(createPictogramVisual(pictogram, "pictogram-visual-md"));

        const p = document.createElement("p");
        p.textContent = pictogram.label;
        btn.appendChild(p);

        btn.addEventListener("click", function() {
            addToSelection(pictogram);
        });

        bar.appendChild(btn);
    });
}

// Onglets de catégories (needs / actions / people / emotions).
function renderCategoryTabs() {
    const tabs = document.getElementById("pictogram-category-tabs");
    if (!tabs) return;
    tabs.innerHTML = "";

    categories.forEach(category => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "pictogram-tab-btn";
        btn.classList.toggle("is-active", category.id === activeCategory);
        btn.dataset.category = category.id;

        const icon = document.createElement("i");
        icon.className = `bi ${category.icon}`;
        icon.setAttribute("aria-hidden", "true");
        btn.appendChild(icon);

        const span = document.createElement("span");
        span.textContent = category.label;
        btn.appendChild(span);

        btn.addEventListener("click", function() {
            switchPictogramCategory(category.id);
        });

        tabs.appendChild(btn);
    });
}

function switchPictogramCategory(categoryId) {
    activeCategory = categoryId;
    document.querySelectorAll(".pictogram-tab-btn").forEach(btn => {
        btn.classList.toggle("is-active", btn.dataset.category === categoryId);
    });
    renderGrid();
}

// Affiche uniquement les pictogrammes de la catégorie active.
function renderGrid() {
    grid.innerHTML = "";
    grid.scrollTop = 0;

    getPictogramsByCategory(activeCategory).forEach(pictogram => {
        const div = document.createElement("div");
        div.classList.add("pictogram-item");
        div.dataset.category = pictogram.category;
        grid.appendChild(div);

        div.appendChild(createPictogramVisual(pictogram, "pictogram-visual-lg"));

        const p = document.createElement("p");
        p.textContent = pictogram.label;
        div.appendChild(p);
        div.addEventListener("click", function() {
            addToSelection(pictogram);
        });
    });

    updateGridScrollHint();
}

// Check-in d'humeur (onglet Home) : reprend uniquement les pictogrammes de
// la catégorie "emotions", indépendamment de l'onglet actif dans la grille
// de communication.
function renderEmotionCheckin() {
    const grid = document.getElementById("emotion-checkin-grid");
    getPictogramsByCategory("emotions").forEach(pictogram => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "emotion-checkin-btn";

        const img = document.createElement("img");
        img.src = pictogram.src;
        img.alt = pictogram.label;
        btn.appendChild(img);

        const p = document.createElement("p");
        p.textContent = pictogram.label;
        btn.appendChild(p);

        btn.addEventListener("click", async () => {
            await fetch("/api/emotion/checkin", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ emotion: pictogram.id })
            });
            todayEmotion = pictogram.id;
            const userId = sessionStorage.getItem("selected_user_id");
            sessionPromise = startSession(userId, todayEmotion);
            revealMainSession();
        });

        grid.appendChild(btn);
    });
}
