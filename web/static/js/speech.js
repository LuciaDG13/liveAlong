let mediaRecorder;
let audioChunks = [];
let recording = false;
let audioContext, analyser, micSource, silenceCheckId;
let lastSoundTime = 0
let hasDetectedSound = false;

const SILENCE_LIMIT = 7000;
const SOUND_TRESHOLD = 12;

const startButton = document.getElementById("btn-micro");

// Quand on se rapproche de 0, le programme va considerer qu'on est autour de 128
function getVolumeLevel() {
    const dataArray = new Uint8Array(analyzer.fftSize);
    analyser.getByteTimeDomainData(dataArray);

    let SumDeviation =0;
    for (let i=0; i<dataArray.length; i++) {
        sumDeviation += Math.abs(dataArray[i]-128);
    }
    return sumDeviation/dataArray.length
}

function monitorSilence(){
    const level = getVolumeLevel();
    if(level>SOUND_TRESHOLD){
        lastSoundTime = Date.now();
        hasDetectedSound=true;
    }
    if (Date.now() - lastSoundTime >= SILENCE_LIMIT) {
        stopRecording();
    }
}

function stopRecording(){
    if (!recording) return;
    recording = false;
    clearInterval(silenceCheckId);
    mediaRecorder.stop();
    if (audioContext) audioContext.close();
}

startButton.onclick = async () => {
    if (!recording) {
        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        audioContext = new (window.AudioContext || window.webkitAudioContext) ();
        micSource = audioContext.createMediaStreamSource(stream); // Conversion en une source api web audio
        analyser = audioContext.createAnalyser(); //  Creation d'une sonde qui va mesurer les donnees
        analyser.fftSize = 2048;
        micSource.connect(analyser); // Brancher la sonde sur le micro

        hasDetectedSound = false;
        lastSoundTime = Date.now();

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach(track => track.stop());

            if (!hasDetectedSound) {
                startButton.className = "bi bi-mic";
                return;
            }
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            startButton.className = "bi bi-hourglass-split"; 

            const formData = new FormData();
            formData.append("audio", audioBlob, "user_voice.wav");

            try {
                const response = await fetch("/message_voice", {
                    method: "POST",
                    body: formData
                });

                const data = await response.json();
                if (data.user_input) {
                console.log("%c[LiveAlong] Transcription reconnue :", "color:#4A7569;font-weight:bold;", data.user_input);
}
                renderAIResponse(data);
                showMessageState();
            } catch (error) {
                console.error("Erreur durant le traitement vocal :", error);
            } finally {
                startButton.className = "bi bi-mic";
            }
        };

        mediaRecorder.start();
        startButton.classList.remove("bi-mic");
        startButton.classList.add("bi-mic-fill");
        recording = true;

        silenceCheckId = setInterval(monitorSilence, 200);

    } else {
        stopRecording();
    }
};

// Désactivation des anciens boutons de confirmation textuelle devenus inutiles
document.getElementById("btn-confirm-voice").onclick = () => {};
document.getElementById("btn-cancel-voice").onclick = () => {};