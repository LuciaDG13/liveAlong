// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-analytics.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-firestore.js"; // ← ajout
import { getAuth } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-auth.js"; // ← ajout

// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
    apiKey: "AIzaSyDgRkTjSDr3leLlos4mmrfo6Jd473yh9Go",
    authDomain: "livealong-a8e0b.firebaseapp.com",
    projectId: "livealong-a8e0b",
    storageBucket: "livealong-a8e0b.firebasestorage.app",
    messagingSenderId: "918557098127",
    appId: "1:918557098127:web:d9e2ca81781fc7e7abb0fa",
    measurementId: "G-41JEXX3KL2"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
export const db = getFirestore(app);
export const firebaseAuth = getAuth(app);