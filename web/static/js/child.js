let childSessionEnded = false;
let avatarPlayer = null;

function logConsole(label, text) {
    console.log(`%c[LiveAlong] ${label} :`, "color:#4A7569;font-weight:bold;", text);
}

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

function notifyChildSessionEnd() {
    if (childSessionEnded) return;
    childSessionEnded = true;
    if (navigator.sendBeacon) {
        navigator.sendBeacon("/end", new Blob(["{}"], { type: "application/json" }));
    } else {
        fetch("/end", { method: "POST", keepalive: true });
    }
}

document.addEventListener("DOMContentLoaded", async function() {
    initUIEvents();
    renderGrid();
    const userId = sessionStorage.getItem("selected_user_id");
    const data = await startSession(userId);

    renderAvatar(data.avatar_svg, "translate(-110,-179) scale(2.85)");
    renderAIResponse(data);
});

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

    if (audioEl && typeof AvatarSpeechPlayer !== "undefined") {
        avatarPlayer = new AvatarSpeechPlayer(mouthGroup, audioEl);
    }
}

function renderAIResponse(data) {
    logConsole("Reponse de l'IA: ", data.response);
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
            document.getElementById("selected-pictograms").innerHTML = "";
            document.getElementById("buttons-pict").classList.remove("visible");
        };
    }

    const btnCancelPict = document.getElementById("button-cancel-pict");
    if (btnCancelPict) {
        btnCancelPict.onclick = () => {
            document.getElementById("selected-pictograms").innerHTML = "";
            document.getElementById("buttons-pict").classList.remove("visible");
        };
    }

    document.getElementById("btn-home").onclick = () => endChildSessionAndRedirect("/");

    document.getElementById("btn-end-session").onclick = async () => {
        const btnEnd = document.getElementById("btn-end-session");
        btnEnd.disabled = true;
        btnEnd.innerHTML = '<i class="bi bi-hourglass-split"></i> ...';
        const data = await endSession();
        childSessionEnded = true;
        logConsole("Session", "Session terminée");
        renderAIResponse(data);

        document.getElementById("mic-zone").setAttribute("hidden", "");
        document.getElementById("pictogram-zone").setAttribute("hidden", "");
        document.getElementById("btn-end-session").setAttribute("hidden", "");
        document.getElementById("end-screen").removeAttribute("hidden");
        document.getElementById("btn-new-conversation").focus();
    };

    document.getElementById("btn-new-conversation").onclick = async () => {
        document.getElementById("end-screen").setAttribute("hidden", "");
        document.getElementById("mic-zone").removeAttribute("hidden");
        document.getElementById("pictogram-zone").removeAttribute("hidden");
        document.getElementById("btn-end-session").removeAttribute("hidden");
        childSessionEnded = false;

        const userId = sessionStorage.getItem("selected_user_id");
        const data = await startSession(userId);
        renderAvatar(data.avatar_svg, "translate(-110,-179) scale(2.85)");
        renderAIResponse(data);
    };
};


window.addEventListener("pagehide", notifyChildSessionEnd);