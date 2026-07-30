let mediaRecorder;
let audioChunks = [];
let recording = false;
let audioContext, analyser, micSource, silenceCheckId;
let lastSoundTime = 0
let hasDetectedSound = false;

const SILENCE_LIMIT = 4000;
const CALIBRATION_DURATION = 400;
const NOISE_MARGIN = 8;

let ambientNoiseLevel=0;
let calibrating = false;
let calibrationSamples = [];

const startButton = document.getElementById("btn-micro");

function resetMicButton() {
    startButton.classList.remove("bi-mic-fill");
    startButton.classList.add("bi-mic");
    startButton.className = "bi bi-mic";
}

function getVolumeLevel() {
    if (!analyser) return 0;

    const dataArray = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(dataArray);

    let sumDeviation = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sumDeviation += Math.abs(dataArray[i] - 128);
    }
    return sumDeviation / dataArray.length;
}

function monitorSilence(){
    const level = getVolumeLevel();
    if(calibrating){
        calibrationSamples.push(level);
        return;
    }
    const treshold = ambientNoiseLevel + NOISE_MARGIN;

    if(level>treshold){
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
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error("Ce navigateur ne prend pas en charge l'accès au microphone.");
            }

            const stream = await navigator.mediaDevices.getUserMedia({audio:true});
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            micSource = audioContext.createMediaStreamSource(stream); // Conversion en une source api web audio
            analyser = audioContext.createAnalyser(); //  Creation d'une sonde qui va mesurer les donnees
            analyser.fftSize = 2048;
            micSource.connect(analyser); // Brancher la sonde sur le micro

            hasDetectedSound = false;
            calibrationSamples = [];
            calibrating = true;

            setTimeout(() => {
                calibrating = false;
                ambientNoiseLevel = calibrationSamples.length
                    ? calibrationSamples.reduce((a, b) => a + b, 0) / calibrationSamples.length
                    : 0;
                lastSoundTime = Date.now(); // le chrono de silence démarre après la calibration
            }, CALIBRATION_DURATION);

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                stream.getTracks().forEach(track => track.stop());

                if (!hasDetectedSound) {
                    resetMicButton();
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
                } catch (error) {
                    console.error("Erreur durant le traitement vocal :", error);
                } finally {
                    resetMicButton();
                }
            };

            mediaRecorder.start();
            startButton.classList.remove("bi-mic");
            startButton.classList.add("bi-mic-fill");
            recording = true;

            silenceCheckId = setInterval(monitorSilence, 200);
        } catch (error) {
            console.error("Erreur d'accès au microphone :", error);
            resetMicButton();
            alert("Le microphone n'est pas accessible. Vérifiez les autorisations du navigateur et qu'un micro est bien branché.");
        }
    } else {
        stopRecording();
    }
};

// Désactivation des anciens boutons de confirmation textuelle devenus inutiles
document.getElementById("btn-confirm-voice").onclick = () => {};
document.getElementById("btn-cancel-voice").onclick = () => {};