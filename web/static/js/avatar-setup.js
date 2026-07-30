import { Style, Avatar } from 'https://cdn.jsdelivr.net/npm/@dicebear/core@10/+esm';
import definition from 'https://cdn.jsdelivr.net/npm/@dicebear/styles@10/dist/big-smile.min.json' with { type: 'json' };

const avatarStyle = new Style(definition);

const HAIR_VARIANTS = ["bangs","bowlCutHair","braids","bunHair","curlyBob","curlyShortHair","froBun","halfShavedHead","mohawk","shavedHead","shortHair","straightHair","wavyBob"];
const EYES_VARIANTS = ["angry","cheery","confused","normal","sad","sleepy","starstruck","winking"];
const ACCESSORIES_VARIANTS = ["catEars","faceMask","glasses","mustache","sailormoonCrown","sunglasses"];
const HAIR_COLORS = ["#220f00","#3a1a00","#71472d","#e2ba87","#605de4","#238d80","#d56c0c","#e9b729"];
const SKIN_COLORS = ["#ffe4c0","#f5d7b1","#efcc9f","#e2ba87","#c99c62","#a47539","#8c5a2b","#643d19"];

let state = {
    hairVariant: "shortHair",
    hairColor: "#220f00",
    eyesVariant: "normal",
    skinColor: "#f5d7b1",
    accessoriesVariant: null // null = pas d'accessoire
};

function buildOptions(overrides = {}) {
    const s = { ...state, ...overrides };
    const options = {
        seed: "livealong-fixed-seed", // fixe : tout est choisi explicitement, le seed ne sert qu'en interne
        mouthVariant: [],             // la bouche reste gérée par avatar-speech-sync.js
        hairVariant: [s.hairVariant],
        hairColor: [s.hairColor],
        eyesVariant: [s.eyesVariant],
        skinColor: [s.skinColor],
    };
    if (s.accessoriesVariant) {
        options.accessoriesVariant = [s.accessoriesVariant];
        options.accessoriesProbability = 100;
    } else {
        options.accessoriesProbability = 0;
    }
    return options;
}

function svgToElement(svgString) {
    const doc = new DOMParser().parseFromString(svgString, "image/svg+xml");
    doc.documentElement.querySelector("metadata")?.remove();
    return doc.documentElement;
}

function renderMainPreview() {
    const avatar = new Avatar(avatarStyle, buildOptions());
    const container = document.getElementById("avatar-preview");
    container.innerHTML = "";
    container.appendChild(svgToElement(avatar.toString()));
}

function renderVariantRow(containerId, componentKey, variantList, includeNone = false) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";

    if (includeNone) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "swatch-btn" + (state[componentKey] === null ? " selected" : "");
        btn.textContent = "Aucun";
        btn.addEventListener("click", () => { state[componentKey] = null; refreshAll(); });
        container.appendChild(btn);
    }

    variantList.forEach(variant => {
        const overrides = { [componentKey]: variant };
        const avatar = new Avatar(avatarStyle, buildOptions(overrides));
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "swatch-btn" + (state[componentKey] === variant ? " selected" : "");
        btn.appendChild(svgToElement(avatar.toString()));
        btn.title = variant;
        btn.addEventListener("click", () => { state[componentKey] = variant; refreshAll(); });
        container.appendChild(btn);
    });
}

function renderColorRow(containerId, componentKey, colorList) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    colorList.forEach(color => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "color-btn" + (state[componentKey] === color ? " selected" : "");
        btn.style.backgroundColor = color;
        btn.addEventListener("click", () => { state[componentKey] = color; refreshAll(); });
        container.appendChild(btn);
    });
}

function refreshAll() {
    renderMainPreview();
    renderVariantRow("hair-row", "hairVariant", HAIR_VARIANTS);
    renderColorRow("haircolor-row", "hairColor", HAIR_COLORS);
    renderVariantRow("eyes-row", "eyesVariant", EYES_VARIANTS);
    renderColorRow("skincolor-row", "skinColor", SKIN_COLORS);
    renderVariantRow("accessories-row", "accessoriesVariant", ACCESSORIES_VARIANTS, true);
}

refreshAll();

document.getElementById("btn-confirm-avatar").addEventListener("click", async () => {
    const btnConfirm = document.getElementById("btn-confirm-avatar");
    const originalContent = btnConfirm.innerHTML;
    btnConfirm.disabled = true;
    btnConfirm.innerHTML = '<i class="bi bi-hourglass-split"></i> ...';

    const options = buildOptions();
    try {
        const response = await fetch("/api/avatar/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ options })
        });
        if (!response.ok) throw new Error("save failed");
        window.location.assign("/child_interface");
    } catch (error) {
        console.error("Failed to save avatar:", error);
        alert("An error occured, please try again.");
        btnConfirm.disabled = false;
        btnConfirm.innerHTML = originalContent;
    }
});