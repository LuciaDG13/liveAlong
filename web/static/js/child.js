let childSessionEnded = false;

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
    const message = document.getElementById("last-message");
    message.textContent = data.response;
    showMessageState();
});

function displayMessage(text) {
    document.getElementById("last-message").textContent = text;
}

document.getElementById("button-confirm-pict").onclick = async () => {
    const imgs = document.querySelectorAll("#selected-pictograms img");
    const labels = Array.from(imgs).map(img => img.alt);
    const messageText = labels.join(", "); // ex: "Happy, Sad"
    const data = await sendMessage(messageText);
    displayMessage(data.response);
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