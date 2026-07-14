let mediaRecorder;
let audioChunks = [];
let recording = false;

const startButton = document.getElementById("btn-micro");

startButton.onclick = async () => {
    if (!recording) {
        // Déclencher le micro du téléphone
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            
            // Animation visuelle : montre que l'ordinateur central calcule
            startButton.className = "bi bi-hourglass-split"; 

            const formData = new FormData();
            formData.append("audio", audioBlob, "user_voice.wav");

            try {
                // Envoi du fichier audio brut vers ton Flask
                const response = await fetch("/message_voice", {
                    method: "POST",
                    body: formData
                });

                // Réception de la réponse sous forme de fichier Audio
                const audioResponseBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioResponseBlob);
                
                // Lecture automatique de la voix générée par Kokoro
                const audio = new Audio(audioUrl);
                audio.play();

                // On rafraîchit l'état de l'interface (défini dans ton child.js)
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
    } else {
        mediaRecorder.stop();
        recording = false;
    }
};

// Désactivation des anciens boutons de confirmation textuelle devenus inutiles
document.getElementById("btn-confirm-voice").onclick = () => {};
document.getElementById("btn-cancel-voice").onclick = () => {};