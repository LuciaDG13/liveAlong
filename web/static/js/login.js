import {signIn, verifyWithBackend } from "./auth.js";

document.getElementById("login-button").addEventListener("click", async () => {
    const email = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    try {
        const token = await signIn(email, password);
        sessionStorage.setItem("auth_token", token);
        const result = await verifyWithBackend(token);
        console.log("Verification result:", result);
        if (result && result.redirect_url) {
            window.location.href = result.redirect_url;  // ← manquant
        } else {
            alert("Login failed. Please try again.");
        }
    } catch (error) {
        alert("Login failed: " + error.message);
    }
});