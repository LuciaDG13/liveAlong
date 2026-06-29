document.addEventListener("DOMContentLoaded", async function() {
    renderGrid();
    const data = await startSession();
    // data.response contient le premier message
    console.log(data); // A supprimer
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
}

function showResponseState() {
    document.getElementById("chat-box").classList.add("hidden");
    document.getElementById("response-zone").classList.remove("hidden");
    document.getElementById("btn-back").classList.remove("hidden");
    document.getElementById("btn-next").classList.add("hidden");
    document.getElementById("btn-micro").removeAttribute("hidden");
}

document.getElementById("btn-next").onclick=() => {
    showResponseState();
}

document.getElementById("btn-back").onclick=() => {
    showMessageState();
}

document.getElementById("btn-end-session").onclick = async () => {
    await endSession();
    displayMessage("Bravo ! La session est terminée.");
    document.getElementById("btn-next").classList.add("hidden");
    document.getElementById("btn-back").classList.add("hidden");
    document.getElementById("btn-end-session").setAttribute("hidden", "");
}