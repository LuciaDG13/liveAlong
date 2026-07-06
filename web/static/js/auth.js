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
        return data;
    } catch (error) {
        console.error("Error verifying token with backend:", error);
    }
}

async function requireAuth(expectedRole) {
    console.log ("On arrive à la fonction d'authentification") // Debugging line
    const token = sessionStorage.getItem("auth_token");
    console.log("Toujours la fonction d'authentification")// Debugging line
    if (!token) {
        console.log("pas de token"); // Debugging line
        window.location.href = "/";
        console.log("On est censés être redirigés vers le nouvel url")
        return;
    }
    console.log("Juste avant la focntion verifywithebackend") // Debugging line
    const result = await verifyWithBackend(token);
    console.log("Juste après la fonction verifywithbackend") // Debugging line
    if (!result || result.error || result.redirect_url !== `/${expectedRole === "therapist" ? "therapist" : "child_interface"}`) {
        console.log("ya une erreur ou quelque chose")
        window.location.href = "/";
    }
}

export { signIn, signOut, verifyWithBackend, requireAuth };