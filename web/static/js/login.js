import {signIn, verifyWithBackend, clearClientSession, signOut } from "./auth.js";

document.addEventListener("DOMContentLoaded", () => {
    clearClientSession();
    signOut().catch(() => {});
});

document.getElementById("login-button").addEventListener("click", async () => {
    const loginButton = document.getElementById("login-button");
    if (loginButton.disabled) return;

    const email = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    loginButton.disabled = true;
    const originalText = loginButton.textContent;
    loginButton.textContent = "Connecting...";

    try {
        const token = await signIn(email, password);
        sessionStorage.setItem("auth_token", token);
        const result = await verifyWithBackend(token);
        console.log("Verification result:", result);
        if (result && result.redirect_url) {
            window.location.href = result.redirect_url;
            return;
        } else {
            alert("Login failed. Please try again.");
        }
    } catch (error) {
        alert("Login failed: " + error.message);
    } finally {
        loginButton.disabled = false;
        loginButton.textContent = originalText;
    }
});