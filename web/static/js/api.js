/* StartSession, sendMessages(text), endSession() */

async function startSession(){
    try {
        const response = await fetch("/start", {method:"POST"});
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Network error", error);
    }
}


// La fonction attend message pas user_input => est censé se voir dans app.py
async function sendMessage(text){
    try {
        const response = await fetch("/message", {
            method:"POST",            
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message:text })
        })
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Network error", error);
    }
}

async function endSession(){
    try {
        const response = await fetch("/end", {
            method:"POST",
        })
        const data = await response.json();
        return data;
    } catch (error){
        console.error("Network error", error);
    }
}