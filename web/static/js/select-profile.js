const searchInput = document.getElementById("profile-search");
const profileList = document.getElementById("profile-list");

let allProfiles = [];

// Évite l'injection HTML quand on affiche le nom d'un profil
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

async function loadProfiles() {
    try {
        const response = await fetch("/api/profiles");
        const data = await response.json();
        allProfiles = data.profiles || [];
        renderProfiles(allProfiles);
    } catch (error) {
        console.error("Failed to load profiles:", error);
        profileList.innerHTML = `<p class="profile-list-message">Unable to load profiles. Please try again.</p>`;
    }
}

function renderProfiles(profiles) {
    if (profiles.length === 0) {
        profileList.innerHTML = `<p class="profile-list-message">No profiles match your search.</p>`;
        return;
    }

    profileList.innerHTML = profiles.map(profile => `
        <button type="button" class="profile-card" data-id="${escapeHtml(profile.id)}">
            <span class="profile-card-name">${escapeHtml(profile.name || "Unnamed profile")}</span>
        </button>
    `).join("");
}

// Filtrage local : pas besoin de retaper Firestore à chaque caractère
searchInput.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase();
    const filtered = allProfiles.filter(profile =>
        (profile.name || "").toLowerCase().includes(query)
    );
    renderProfiles(filtered);
});

// Délégation d'événement : les .profile-card sont créées dynamiquement,
// donc on écoute les clics sur le conteneur parent plutôt que sur chaque carte
profileList.addEventListener("click", (event) => {
    const card = event.target.closest(".profile-card");
    if (!card) return;

    const userId = card.dataset.id;
    sessionStorage.setItem("selected_user_id", userId);
    window.location.href = "/child_interface";
});

loadProfiles();