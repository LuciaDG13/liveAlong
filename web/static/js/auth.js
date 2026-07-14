import {firebaseAuth} from "./firebase-init.js";
import {signInWithEmailAndPassword, signOut as firebaseSignOut } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-auth.js";

async function signIn(email, password) {
    try {
        const userCredential = await signInWithEmailAndPassword(firebaseAuth, email, password);
        const token = await userCredential.user.getIdToken();
        return token;
    } catch (error) {
        console.error("Error signing in:", error);
        throw error;
    }
}

function clearClientSession() {
    sessionStorage.removeItem("auth_token");
    sessionStorage.removeItem("selected_user_id");
    document.cookie = "session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
}

async function signOut() {
    try {
        await firebaseSignOut(firebaseAuth);
    } catch (error) {
        console.error("Error signing out:", error);
    }
}

async function verifyWithBackend(idToken) {
    try{
        const response = await fetch("/auth/verify", {
            method: "POST",
            headers: {"Content-Type": "Application/json"},
            body: JSON.stringify({idToken})
        });
        const data = await response.json();
        console.log(`Voici a quoi ressemble le data: ${data}`) /* Debugging line */
        return data;
    } catch (error) {
        console.error("Error verifying token with backend:", error);
    }
}

async function requireAuth(expectedRole) {
    console.log("On arrive à la fonction d'authentification");
    const token = sessionStorage.getItem("auth_token");
    
    if (!token) {
        window.location.href = "/";
        return;
    }
    
    const result = await verifyWithBackend(token);
    console.log("Données reçues du serveur (result) :", result); // Debugging line
    
    const isTherapistValid = expectedRole === "therapist" && result.redirect_url.includes("therapist");
    const isChildValid = expectedRole === "child" && result.redirect_url.includes("child_interface");

    if (!result || result.error || (!isTherapistValid && !isChildValid)) {
        console.log("Accès refusé ou rôle incorrect, redirection vers l'accueil...");
        window.location.href = "/";
        return;
    }

    const nameDisplay = document.getElementById("user-display-name");
    if (nameDisplay) {
        /* A MODIFIER */
        nameDisplay.textContent = result.name || result.displayName || (expectedRole === "therapist" ? "Therapist" : "Child");
    }

    const logoLink = document.getElementById("link-logo");
    if (logoLink) {
        logoLink.href = expectedRole === "therapist" ? "/therapist" : "/child_interface";
    }
}

document.addEventListener("click", async (event) => {
    const logoutButton = event.target.closest && event.target.closest("#btn-logout");
    const logoutLink = event.target.closest && event.target.closest(".header-back[data-confirm-logout='true']");

    if (logoutButton) {
        event.preventDefault();
        const shouldLogout = window.confirm("You are about to log out and return to the login page. Continue?");
        if (!shouldLogout) return;

        try {
            await signOut();
            clearClientSession();
            window.location.href = "/";
        } catch (error) {
            console.error("Error during logout:", error);
        }
    }

    if (logoutLink) {
        event.preventDefault();
        const shouldLogout = window.confirm("You are about to log out and return to the login page. Continue?");
        if (!shouldLogout) return;

        try {
            await signOut();
            clearClientSession();
            window.location.href = "/";
        } catch (error) {
            console.error("Error during logout:", error);
        }
    }
});

export { signIn, signOut, verifyWithBackend, requireAuth, clearClientSession };