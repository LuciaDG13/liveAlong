const searchInput = document.getElementById("profile-search");
const profileList = document.getElementById("profile-list");
const profileDetail = document.getElementById("profile-detail");
const searchWrapper = document.getElementById("profile-search-wrapper");
const scrollTopButton = document.getElementById("btn-scroll-top");

let allProfiles = [];

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function formatValue(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    if (Array.isArray(value)) {
        return value.join(", ");
    }
    return String(value);
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

function showListView() {
    profileList.classList.remove("hidden");
    searchWrapper.classList.remove("hidden");
    profileDetail.classList.add("hidden");
}

function toggleScrollTopButton() {
    if (!scrollTopButton) return;

    if (window.scrollY > 220) {
        scrollTopButton.classList.remove("hidden");
    } else {
        scrollTopButton.classList.add("hidden");
    }
}

function showDetailView() {
    profileList.classList.add("hidden");
    searchWrapper.classList.add("hidden");
    profileDetail.classList.remove("hidden");
}

function renderProfileSummary(profile) {
    const summaryFields = [
        ["Name", profile.name],
        ["Date of birth", profile.date_of_birth],
        ["Gender", profile.gender],
        ["Pronoun", profile.pronoun],
        ["Communication type", profile["communication-type"]],
        ["Language level", profile["language-level"]],
        ["Level Autism", profile.levelAutism],
        ["Interests", profile.interests],
        ["Sensory", profile.sensory],
        ["Physical contact", profile["physical-contact"]],
        ["Clinical context", profile["clinical-context"]],
        ["Triggers", profile.triggers],
        ["Email", profile.email],
    ];

    const consolidated = profile.consolidated_profile || {};
    const insights = profile.session_insights || [];
    const latestInsight = insights[insights.length - 1] || {};
    const recapRows = summaryFields
        .map(([label, value]) => `
            <tr>
                <th>${escapeHtml(label)}</th>
                <td>${escapeHtml(formatValue(value))}</td>
            </tr>
        `)
        .join("");

    const consolidatedRows = [
        ["Stable traits", consolidated.stable_traits],
        ["Emerging difficulties", consolidated.emerging_difficulties],
        ["Resolved difficulties", consolidated.resolved_difficulties],
        ["Last session progress", latestInsight.progress],
    ]
        .map(([label, value]) => `
            <tr>
                <th>${escapeHtml(label)}</th>
                <td>${escapeHtml(formatValue(value))}</td>
            </tr>
        `)
        .join("");

    return `
        <div class="profile-detail-card">
            <div class="profile-detail-header">
                <button type="button" class="profile-detail-back" aria-label="Back to profile list">
                    <i class="bi bi-arrow-left"></i>
                </button>
                <h2 class="profile-detail-title">Profile recap</h2>
            </div>
            <div class="profile-detail-table-wrapper">
                <table class="profile-detail-table">
                    <tbody>
                        ${recapRows}
                        ${consolidatedRows}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

function renderConversationSessions(sessions) {
    if (!sessions || sessions.length === 0) {
        return `
            <div class="conversation-card">
                <h2 class="profile-detail-title">Conversation history</h2>
                <p class="profile-list-message">No conversation has been recorded yet for this profile.</p>
            </div>
        `;
    }

    const sessionsMarkup = sessions.map(session => {
        const messagesMarkup = (session.messages || []).map(message => {
            const roleLabel = message.role === "assistant" ? "AI" : "Child";
            const bubbleClass = message.role === "assistant" ? "phone-bubble assistant" : "phone-bubble user";
            return `
                <div class="phone-message-row">
                    <div class="${bubbleClass}">
                        <span class="phone-role">${escapeHtml(roleLabel)}</span>
                        <div>${escapeHtml(formatValue(message.content))}</div>
                    </div>
                </div>
            `;
        }).join("");

        return `
            <article class="phone-session-card">
                <div class="phone-session-header">
                    <span class="phone-session-theme">${escapeHtml(session.theme || "Session")}</span>
                    <span class="phone-session-date">${escapeHtml(session.date || "Unknown date")}</span>
                </div>
                <div class="phone-thread">
                    ${messagesMarkup || `<p class="profile-list-message">No messages in this session.</p>`}
                </div>
            </article>
        `;
    }).join("");

    return `
        <div class="conversation-card">
            <h2 class="profile-detail-title">Conversation history</h2>
            ${sessionsMarkup}
        </div>
    `;
}

async function loadProfileDetails(profileId) {
    try {
        const response = await fetch(`/api/profiles/${profileId}/details`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to load the profile details.");
        }

        showDetailView();
        profileDetail.innerHTML = `
            ${renderProfileSummary(data.profile)}
            ${renderConversationSessions(data.sessions)}
        `;

        const backButton = profileDetail.querySelector(".profile-detail-back");
        if (backButton) {
            backButton.addEventListener("click", () => {
                showListView();
            });
        }
    } catch (error) {
        console.error("Failed to load profile detail:", error);
        showDetailView();
        profileDetail.innerHTML = `<p class="profile-list-message">Unable to load this profile detail. Please try again.</p>`;
    }
}

searchInput.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase();
    const filtered = allProfiles.filter(profile =>
        (profile.name || "").toLowerCase().includes(query)
    );
    renderProfiles(filtered);
});

profileList.addEventListener("click", async (event) => {
    const card = event.target.closest(".profile-card");
    if (!card) return;

    const userId = card.dataset.id;
    await loadProfileDetails(userId);
});

if (scrollTopButton) {
    scrollTopButton.addEventListener("click", () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
    window.addEventListener("scroll", toggleScrollTopButton, { passive: true });
    toggleScrollTopButton();
}

loadProfiles();
showListView();