const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const SpeechRecognitionEvent = window.SpeechRecognitionEvent || window.webkitSpeechRecognitionEvent;
const recognition = new SpeechRecognition();
recognition.lang = 'fr-FR';
recognition.interimResults = true;
recognition.continuous = false;

const startButton = document.getElementById("btn-micro");
const text = document.getElementById("preview-text");

let transcribedText = "";

let recording = false;

startButton.onclick = () => {
    if (!recording) {
        recognition.start();
        startButton.classList.remove("bi-mic");
        startButton.classList.add("bi-mic-fill");
        console.log("start of the recording"); // A supprimer
        recording = true;
    }
    else {
        recognition.stop();
        startButton.classList.remove("bi-mic-fill");
        startButton.classList.add("bi-mic");
        recording = false;
        console.log("end of the recording");
    }
    
};

recognition.onresult = (event) => {
    transcribedText = event.results[event.results.length -1][0].transcript;
    // results est un tableau de résultats
    // Syntaxe de Web Speech API => results[dernier résultat] [meilleure hypothèse].transcript
    text.textContent= transcribedText;
};

recognition.onspeechend = () => {    
    recognition.stop();
    document.getElementById("preview-voice").removeAttribute("hidden");

};

recognition.onerror = (event) => {
    console.error(`Error: ${event.error}`);
};

document.getElementById("btn-confirm-voice").onclick = async () => {
    document.getElementById("preview-voice").setAttribute("hidden", "");
    const data = await sendMessage(transcribedText);
    displayMessage(data.response);
    transcribedText = "";
    showMessageState();
};

document.getElementById("btn-cancel-voice").onclick = () => {
    document.getElementById("preview-voice").setAttribute("hidden", "");
    transcribedText = "";
    recognition.start()
};