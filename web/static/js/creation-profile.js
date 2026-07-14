const STEP_ACTIVE_CLASS = "step-active";
const DOT_ACTIVE_CLASS = "active";
const HIDDEN_BTN_CLASS = "hidden-btn";

const steps = document.querySelectorAll(".form-step");
const dots = document.querySelectorAll(".dot");
const btnNext = document.getElementById("btn-next");
const btnBack = document.getElementById("btn-back");
const backLink = document.getElementById("creation-profile-back-link");
const form = document.getElementById("multi-step-form");
let currentStep = 0;
let isDirty = false;

// Fonction par précaution
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function getLabel(fieldName) {
    const label = document.querySelector(`label[for="${fieldName}"]`);
    return label ? label.textContent.replace(/:\s*$/, "") : fieldName;
}

function markDirty() {
    isDirty = true;
}

function confirmLeavePage() {
    if (!isDirty) return true;
    return window.confirm("You are leaving this page. Unsaved information will be lost. Continue?");
}

function goToTherapistPage() {
    if (confirmLeavePage()) {
        window.location.assign("/therapist");
    }
}

// Navigation entre les étapes du formulaire

function updateForm() {
    steps.forEach((step, index) => {
        step.classList.toggle(STEP_ACTIVE_CLASS, index === currentStep);
    });

    dots.forEach((dot, index) => {
        dot.classList.toggle(DOT_ACTIVE_CLASS, index <= currentStep);
    });

    const isFirstStep = currentStep === 0;
    btnBack.classList.toggle(HIDDEN_BTN_CLASS, isFirstStep);

    const isLastStep = currentStep === steps.length - 1;
    btnNext.classList.toggle("bi-check-circle-fill", isLastStep);
    btnNext.classList.toggle("bi-arrow-right-circle-fill", !isLastStep);
    btnNext.setAttribute("aria-label", isLastStep ? "Submit profile" : "Next step");

    if (isLastStep) {
        generateRecap();
    }
}

function generateRecap() {
    const formData = new FormData(document.getElementById("multi-step-form"));
    const recapContainer = document.getElementById("recap-container");

    let html = "<dl class='recap-list'>";
    for (const [key, value] of formData.entries()) {
        if (key === "confirm-data") continue;

        const label = escapeHtml(getLabel(key));
        const safeValue = value ? escapeHtml(value) : "<em>Not provided</em>";
        html += `<dt>${label}</dt><dd>${safeValue}</dd>`;
    }
    html += "</dl>";
    recapContainer.innerHTML = html;
}

// Sauvegarde du profil via l'API

async function saveProfile(form) {
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    delete payload["confirm-data"];

    btnNext.disabled = true;

    try {
        const response = await fetch("/therapist/create_profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload) 
        });

        if (!response.ok) {
            throw new Error(`Server responded with status ${response.status}`);
        }

        isDirty = false;
        alert("Profile successfully saved!");
        window.location.assign("/therapist/profiles");
    } catch (error) {
        console.error("Failed to save profile:", error);
        alert("Something went wrong while saving the profile. Please try again.");
    } finally {
        btnNext.disabled = false;
    }
}

// ---Événements---

btnNext.addEventListener("click", () => {
    const currentInputs = steps[currentStep].querySelectorAll("input[required], select[required], textarea[required]");
    let valid = true;
    currentInputs.forEach(input => {
        if (!input.checkValidity()) {
            input.reportValidity();
            valid = false;
        }
    });

    if (!valid) return;

    if (currentStep < steps.length - 1) {
        currentStep++;
        updateForm();
    } else {
        const form = document.getElementById("multi-step-form");
        if (form.checkValidity()) {
            saveProfile(form);
        } else {
            form.reportValidity();
        }
    }
});

btnBack.addEventListener("click", () => {
    if (currentStep > 0) {
        currentStep--;
        updateForm();
    } else {
        goToTherapistPage();
    }
});

if (backLink) {
    backLink.addEventListener("click", (event) => {
        event.preventDefault();
        goToTherapistPage();
    });
}

if (form) {
    form.addEventListener("input", markDirty);
    form.addEventListener("change", markDirty);
}

window.addEventListener("beforeunload", (event) => {
    if (isDirty) {
        event.preventDefault();
        event.returnValue = "";
    }
});

updateForm();