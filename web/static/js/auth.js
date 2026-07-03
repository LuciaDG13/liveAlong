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

async function verifyWithBackend(token) {
    try{
        const response = await fetch("/auth/verify", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            },
        });
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error verifying token with backend:", error);
    }
}

async function requireAuth(expectedRole) {
    const token = sessionStorage.getItem("auth_token");
    if (!token) {
        console.log("pas de token"); // Debugging line
        window.location.href = "/";
        return;
    }
    const result = await verifyWithBackend(token);
    if (!result || result.error || result.redirect_url !== `/${expectedRole === "therapist" ? "therapist" : "child_interface"}`) {
        window.location.href = "/";
    }
}

export { signIn, signOut, verifyWithBackend, requireAuth };