let childSessionEnded = false;

// Ajouter un script pour avatar-speech-sync
// Il faudra ajouter un id="avatar-mouth" et un id="avatar-audio"

const avatarMouthEl = document.getElementById("avatar-mouth");
const avatarAudioEl = document.getElementById("avatar-audio");
const avatarPlayer = (avatarMouthEl && avatarAudioEl)
    ? new AvatarSpeechPlayer(avatarMouthEl, avatarAudioEl)
    : null;

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
    renderGrid();
    const userId = sessionStorage.getItem("selected_user_id");
    const data = await startSession(userId);
    renderAIResponse(data);
    showMessageState();
});

function displayMessage(text) {
    document.getElementById("last-message").textContent = text;
}
function renderAIResponse(data) {
    displayMessage(data.response);
    if (!data.audio) return;

    const audioSrc = "data:audio/wav;base64," + data.audio;

    if (avatarPlayer && data.mouthCues) {
        // Chemin complet : audio + lip-sync précis (mouthCues fournis par le backend)
        avatarAudioEl.src = audioSrc;
        avatarPlayer.loadRhubarbCues({ mouthCues: data.mouthCues });
        avatarPlayer.play();
    } else {
        // Repli : pas encore de mouthCues (ou avatar absent de la page) -> comportement d'origine
        const audio = new Audio(audioSrc);
        audio.play();
    }
}


document.getElementById("button-confirm-pict").onclick = async () => {
    const imgs = document.querySelectorAll("#selected-pictograms img");
    const labels = Array.from(imgs).map(img => img.alt);
    const messageText = labels.join(", "); // ex: "Happy, Sad"
    const data = await sendMessage(messageText);
    renderAIResponse(data);
    showMessageState();
    document.getElementById("selected-pictograms").innerHTML="";
}

document.getElementById("button-cancel-pict").onclick = () => {
    document.getElementById("selected-pictograms").innerHTML="";
    document.getElementById("buttons-pict").setAttribute("hidden", "");
}

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

document.getElementById("btn-next").onclick = () => {
    showResponseState();
}

document.getElementById("btn-back").onclick = () => {
    showMessageState();
}

document.getElementById("btn-home").onclick = () => {
    endChildSessionAndRedirect("/");
}

document.getElementById("btn-end-session").onclick = async () => {
    await endSession();
    childSessionEnded = true;
    displayMessage("Congratulation! This session has ended");
    document.getElementById("btn-next").classList.add("hidden");
    document.getElementById("btn-back").classList.add("hidden");
    document.getElementById("btn-end-session").setAttribute("hidden", "");
    document.getElementById("btn-home").focus();
}

window.addEventListener("pagehide", notifyChildSessionEnd);
window.addEventListener("beforeunload", notifyChildSessionEnd);