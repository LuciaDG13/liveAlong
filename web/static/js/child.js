let childSessionEnded = false;
let avatarPlayer = null;
let pendingSessionData = null;

// Custom mouth shapes (avatar-speech-sync.js) are drawn around local point
// (150, 187.75). Measured empirically against the dicebear "big-smile"
// avatar (viewBox 0 0 480 480): averaged mouth position across 40 generated
// seeds is ~(112, 84). translate/scale below maps the former onto the latter.
const AVATAR_MOUTH_TRANSFORM = "translate(35,-43) scale(2)";
function logConsole(label, text) {
    console.log(`%c[LiveAlong] ${label} :`, "color:#4A7569;font-weight:bold;", text);
}

function escapeHtmlChild(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

const PROGRESS_STATUS_GROUPS = [
    { key: "confident", label: "Feeling confident" },
    { key: "practicing", label: "Practicing" },
    { key: "started", label: "Just started" },
];

async function loadProgress() {
    const activitiesEl = document.getElementById("progress-activities");
    const skillsEl = document.getElementById("progress-skills");

    activitiesEl.innerHTML = `<p class="badge-empty">Loading...</p>`;
    skillsEl.innerHTML = "";

    try {
        const response = await fetch("/api/progress");
        const data = await response.json();
        const themesByStatus = data.themes_by_status || {};

        const groupsWithThemes = PROGRESS_STATUS_GROUPS
            .map(group => ({ ...group, themes: themesByStatus[group.key] || [] }))
            .filter(group => group.themes.length > 0);

        activitiesEl.innerHTML = groupsWithThemes.length
            ? groupsWithThemes.map(group => `
                <div class="progress-group">
                    <div class="progress-group-label status-${group.key}">
                        <span class="status-dot"></span>${group.label}
                    </div>
                    <div class="badge-row">
                        ${group.themes.map(theme => `<span class="badge-chip">${escapeHtmlChild(theme)}</span>`).join("")}
                    </div>
                </div>
            `).join("")
            : `<p class="badge-empty">No activities practiced yet.</p>`;

        skillsEl.innerHTML = (data.skills_growing && data.skills_growing.length)
            ? data.skills_growing.map(skill => `<span class="badge-chip skill">${escapeHtmlChild(skill)}</span>`).join("")
            : `<p class="badge-empty">Keep practicing, your skills will show up here!</p>`;
    } catch (error) {
        console.error("Failed to load progress:", error);
        activitiesEl.innerHTML = `<p class="badge-empty">Unable to load your progress right now.</p>`;
    }
}

function notifyChildSessionEnd() {
    if (childSessionEnded) return;
    childSessionEnded = true;
    if (navigator.sendBeacon) {
        navigator.sendBeacon("/end", new Blob(["{}"], { type: "application/json" }));
    } else {
        fetch("/end", { method: "POST", keepalive: true });
    }
}

let sessionPromise = null;
let todayEmotion = null;

function switchTab(tab) {
    document.querySelectorAll(".tab-pane").forEach(pane => {
        pane.classList.toggle("active-tab", pane.id === `tab-${tab}`);
    });
    document.querySelectorAll(".tab-nav-btn").forEach(btn => {
        btn.classList.toggle("is-active", btn.dataset.tab === tab);
    });
    if (tab === "progress") {
        loadProgress();
    }
}

function showChatState(state) {
    document.getElementById("chat-placeholder").toggleAttribute("hidden", state !== "placeholder");
    document.getElementById("session-loading").toggleAttribute("hidden", state !== "loading");
    document.getElementById("main-area").toggleAttribute("hidden", state !== "active");
}

document.addEventListener("DOMContentLoaded", async function() {
    initUIEvents();
    renderCoreBar();
    renderCategoryTabs();
    renderGrid();
    renderEmotionCheckin();
});

async function revealMainSession() {
    switchTab("chat");
    showChatState("loading");

    const data = await sessionPromise;
    if (data.communication_type === "Non-verbal") {
        document.getElementById("pictogram-zone")?.classList.add("priority");
    }
    showChatState("active");

    if (data.usage_nudge) {
        document.getElementById("usage-nudge-banner").removeAttribute("hidden");
    }

    renderAvatar(data.avatar_svg, AVATAR_MOUTH_TRANSFORM);
    renderAIResponse(data);
}

// Panneau de réglage temporaire pour calibrer la position/taille de la
// bouche à la souris. Actif uniquement avec ?debug=1 dans l'URL — jamais
// visible pour un enfant en usage normal.
function setupMouthDebugPanel(mouthGroup) {
    mouthGroup.innerHTML = RHUBARB_MOUTHS.B; // forme visible pour le calibrage

    let panel = document.getElementById("mouth-debug-panel");
    if (!panel) {
        panel = document.createElement("div");
        panel.id = "mouth-debug-panel";
        panel.style.cssText = "position:fixed;bottom:12px;left:12px;z-index:9999;background:#fff;"
            + "border:2px solid #4A7569;border-radius:8px;padding:10px;font:13px monospace;"
            + "box-shadow:0 2px 8px rgba(0,0,0,.2);";
        panel.innerHTML = `
            <div>Position X <input id="dbg-tx" type="range" min="-400" max="400" step="1"></div>
            <div>Position Y <input id="dbg-ty" type="range" min="-400" max="400" step="1"></div>
            <div>Taille <input id="dbg-scale" type="range" min="0.2" max="5" step="0.05"></div>
            <div id="dbg-output" style="margin-top:8px;user-select:all;background:#EBF3F0;padding:4px;"></div>
            <p style="margin:6px 0 0;color:#556B66;">Copie la ligne ci-dessus dans AVATAR_MOUTH_TRANSFORM (child.js) une fois satisfaite.</p>
        `;
        document.body.appendChild(panel);
    }

    const match = /translate\(([-\d.]+),\s*([-\d.]+)\)\s*scale\(([-\d.]+)\)/.exec(mouthGroup.getAttribute("transform")) || [];
    const txInput = document.getElementById("dbg-tx");
    const tyInput = document.getElementById("dbg-ty");
    const scaleInput = document.getElementById("dbg-scale");
    txInput.value = match[1] || 0;
    tyInput.value = match[2] || 0;
    scaleInput.value = match[3] || 1;

    function apply() {
        const transform = `translate(${txInput.value},${tyInput.value}) scale(${scaleInput.value})`;
        mouthGroup.setAttribute("transform", transform);
        document.getElementById("dbg-output").textContent = transform;
    }
    [txInput, tyInput, scaleInput].forEach(input => input.addEventListener("input", apply));
    apply();
}

function renderAvatar(avatarSvg, mouthTransform = "translate(0,0)") {
    if (!avatarSvg) return;

    const container = document.getElementById("avatar-container");
    const audioEl = document.getElementById("avatar-audio");

    container.innerHTML = avatarSvg;
    if (audioEl) container.appendChild(audioEl);

    const svgEl = container.querySelector("svg");
    if (!svgEl) return;

    const mouthGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    mouthGroup.setAttribute("id", "avatar-mouth");
    mouthGroup.setAttribute("transform", mouthTransform);
    svgEl.appendChild(mouthGroup);

    if (new URLSearchParams(window.location.search).get("debug") === "1") {
        setupMouthDebugPanel(mouthGroup);
    }

    if (audioEl && typeof AvatarSpeechPlayer !== "undefined") {
        avatarPlayer = new AvatarSpeechPlayer(mouthGroup, audioEl);
    }
}

function showEndScreen() {
    document.getElementById("mic-zone").setAttribute("hidden", "");
    document.getElementById("pictogram-zone").setAttribute("hidden", "");
    document.getElementById("btn-end-session").setAttribute("hidden", "");
    document.getElementById("end-screen").removeAttribute("hidden");
    document.getElementById("btn-new-conversation").focus();
}

function resetEndSessionButton() {
    const btnEnd = document.getElementById("btn-end-session");
    btnEnd.disabled = false;
    btnEnd.innerHTML = "👋 See you";
}

function renderAIResponse(data) {
    logConsole("Reponse de l'IA: ", data.response);

    if (data.session_ended) {
        childSessionEnded = true;
        showEndScreen();
    }

    if (!data.audio) return;

    const audioSrc = "data:audio/wav;base64," + data.audio;
    const avatarAudioEl = document.getElementById("avatar-audio");

    if (avatarPlayer && data.mouthCues && avatarAudioEl) {
        avatarAudioEl.src = audioSrc;
        avatarPlayer.loadRhubarbCues({ mouthCues: data.mouthCues });
        avatarPlayer.play();
    } else {
        const audio = new Audio(audioSrc);
        audio.play();
    }
}

function clearPictogramSelection() {
    document.getElementById("selected-pictograms").innerHTML = "";
    document.getElementById("buttons-pict").classList.remove("visible");
    document.getElementById("btn-micro").removeAttribute("hidden");
}

function initUIEvents() {
    const btnConfirmPict = document.getElementById("button-confirm-pict");
    if (btnConfirmPict) {
        btnConfirmPict.onclick = async () => {
            const imgs = document.querySelectorAll("#selected-pictograms img");
            const labels = Array.from(imgs).map(img => img.alt);
            const messageText = labels.join(", ");
            logConsole("Message envoyé (pictogrammes)", messageText);

            const data = await sendMessage(messageText);
            renderAIResponse(data);
            clearPictogramSelection();
        };
    }

    const btnCancelPict = document.getElementById("button-cancel-pict");
    if (btnCancelPict) {
        btnCancelPict.onclick = () => {
            clearPictogramSelection();
        };
    }

    document.getElementById("btn-dismiss-usage-nudge").onclick = () => {
        document.getElementById("usage-nudge-banner").setAttribute("hidden", "");
    };

    document.querySelectorAll(".tab-nav-btn").forEach(btn => {
        btn.onclick = () => switchTab(btn.dataset.tab);
    });

    document.getElementById("btn-end-session").onclick = async () => {
        const btnEnd = document.getElementById("btn-end-session");
        btnEnd.disabled = true;
        btnEnd.innerHTML = '<i class="bi bi-hourglass-split"></i> ...';
        const data = await endSession();
        childSessionEnded = true;
        logConsole("Session", "Session terminée");
        renderAIResponse(data);
        showEndScreen();
    };

    document.getElementById("btn-new-conversation").onclick = async () => {
        document.getElementById("end-screen").setAttribute("hidden", "");
        document.getElementById("mic-zone").removeAttribute("hidden");
        document.getElementById("pictogram-zone").removeAttribute("hidden");
        resetEndSessionButton();
        document.getElementById("btn-end-session").removeAttribute("hidden");
        childSessionEnded = false;

        const userId = sessionStorage.getItem("selected_user_id");
        const data = await startSession(userId, todayEmotion);
        if (data.usage_nudge) {
            document.getElementById("usage-nudge-banner").removeAttribute("hidden");
        }
        renderAvatar(data.avatar_svg, AVATAR_MOUTH_TRANSFORM);
        renderAIResponse(data);
    };
};


window.addEventListener("pagehide", notifyChildSessionEnd);