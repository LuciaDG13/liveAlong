let childSessionEnded = false;
let avatarPlayer = null;

/**
 * Affiche un message stylisé dans la console
 */
function logConsole(label, text) {
    console.log(`%c[LiveAlong] ${label} :`, "color:#4A7569;font-weight:bold;", text);
}

/**
 * Termine la session de l'enfant et redirige l'utilisateur
 */
function endChildSessionAndRedirect(targetUrl = "/") {
    if (childSessionEnded) {
        window.location.assign(targetUrl);
        return;
    }

    childSessionEnded = true;
    endSession().finally(() => {
        window.location.assign(targetUrl);
    });
}

/**
 * Envoie une requête de fermeture en arrière-plan lors de la fermeture de la page
 */
function notifyChildSessionEnd() {
    if (childSessionEnded) return;
    childSessionEnded = true;
    if (navigator.sendBeacon) {
        navigator.sendBeacon("/end", new Blob(["{}"], { type: "application/json" }));
    } else {
        fetch("/end", { method: "POST", keepalive: true });
    }
}

/**
 * Initialisation au chargement du DOM
 */
document.addEventListener("DOMContentLoaded", async function() {
    initUIEvents();

    renderGrid();
    const userId = sessionStorage.getItem("selected_user_id");
    const data = await startSession(userId);
    
    // Vous pouvez ajuster les coordonnées X et Y de la bouche ici : renderAvatar(svg, x, y)
    renderAvatar(data.avatar_svg, 130, 85); 
    renderAIResponse(data);
    showMessageState();
});

/**
 * Injecte l'avatar SVG, configure le groupe de la bouche et instancie le player
 * @param {string} avatarSvg - Le code SVG brut reçu du serveur
 * @param {number} mouthX - Décalage horizontal (translate X)
 * @param {number} mouthY - Décalage vertical (translate Y)
 */
function renderAvatar(avatarSvg, mouthX = 0, mouthY = 0) {
    if (!avatarSvg) return;

    const container = document.getElementById("avatar-container");
    const audioEl = document.getElementById("avatar-audio");

    // 1. Injection du SVG
    container.innerHTML = avatarSvg;
    if (audioEl) container.appendChild(audioEl); // Réattachement du tag audio après le innerHTML

    const svgEl = container.querySelector("svg");
    if (!svgEl) return;

    // 2. Création et positionnement du groupe <g id="avatar-mouth">
    const mouthGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    mouthGroup.setAttribute("id", "avatar-mouth");
    
    // Application de la transformation translate pour la bouche
    mouthGroup.setAttribute("transform", `translate(${mouthX}, ${mouthY})`);
    svgEl.appendChild(mouthGroup);

    // 3. Initialisation sécurisée de l'AvatarSpeechPlayer
    if (audioEl && typeof AvatarSpeechPlayer !== "undefined") {
        avatarPlayer = new AvatarSpeechPlayer(mouthGroup, audioEl);
    }
}

/**
 * Traite la réponse de l'IA (lecture de l'audio + lip-sync)
 */
function renderAIResponse(data) {
    logConsole("Reponse de l'IA: ", data.response);
    if (!data.audio) return;

    const audioSrc = "data:audio/wav;base64," + data.audio;
    const avatarAudioEl = document.getElementById("avatar-audio");

    if (avatarPlayer && data.mouthCues && avatarAudioEl) {
        // Mode synchro labiale précis (avec Rhubarb / mouthCues)
        avatarAudioEl.src = audioSrc;
        avatarPlayer.loadRhubarbCues({ mouthCues: data.mouthCues });
        avatarPlayer.play();
    } else {
        // Mode de secours si l'avatar ou les mouthCues sont absents
        const audio = new Audio(audioSrc);
        audio.play();
    }
}

// Boutons et pictogrammes
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
            showMessageState();
            document.getElementById("selected-pictograms").innerHTML = "";
        };
    }

    const btnCancelPict = document.getElementById("button-cancel-pict");
    if (btnCancelPict) {
        btnCancelPict.onclick = () => {
            document.getElementById("selected-pictograms").innerHTML = "";
            document.getElementById("buttons-pict").setAttribute("hidden", "");
        };
    }

    document.getElementById("btn-next").onclick = showResponseState;
    document.getElementById("btn-back").onclick = showMessageState;
    document.getElementById("btn-home").onclick = () => endChildSessionAndRedirect("/");

    document.getElementById("btn-end-session").onclick = async () => {
        await endSession();
        childSessionEnded = true;
        logConsole("Session", "Session terminée");
        document.getElementById("btn-next").classList.add("hidden");
        document.getElementById("btn-back").classList.add("hidden");
        document.getElementById("btn-end-session").setAttribute("hidden", "");
        document.getElementById("btn-home").focus();
    };
}

// Gestion de l'état des affichages
function showMessageState() {
    document.getElementById("chat-box").classList.remove("hidden");
    document.getElementById("response-zone").classList.add("hidden");
    document.getElementById("btn-next").classList.remove("hidden");
    document.getElementById("btn-back").classList.add("hidden");
    document.getElementById("btn-end-session").removeAttribute("hidden");
}

function showResponseState() {
    document.getElementById("chat-box").classList.add("hidden");
    document.getElementById("response-zone").classList.remove("hidden");
    document.getElementById("btn-back").classList.remove("hidden");
    document.getElementById("btn-next").classList.add("hidden");
    document.getElementById("btn-micro").removeAttribute("hidden");
}

window.addEventListener("pagehide", notifyChildSessionEnd);