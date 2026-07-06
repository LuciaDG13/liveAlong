import {signIn, verifyWithBackend } from "./auth.js";

document.getElementById("login-button").addEventListener("click", async () => {
    const email = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    console.log("Récupération de l'adresse email et du mdp OK") // Debugging line
    try {
        const token = await signIn(email, password);
        console.log("Sign In OK") // Debugging line
        sessionStorage.setItem("auth_token", token);
        console.log("Récupération de l'autorisation OK") // Debugging line
        const result = await verifyWithBackend(token);
        console.log("Verification result:", result);
        if (result && result.redirect_url) {
            console.log("j'arrive bien là") // Debugging line
            window.location.href = result.redirect_url;  // ← manquant
            console.log("Mais est-ce que j'arrive là ?") // Debugging line
        } else {
            alert("Login failed. Please try again.");
        }
    } catch (error) {
        alert("Login failed: " + error.message);
    }
});