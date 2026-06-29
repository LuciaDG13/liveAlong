const grid = document.getElementById("pictogram_grid");

const pictograms = [
    { id: "happy", label: "Happy", src: "/static/pictograms/happy.png"},
    { id: "confused", label: "Confused", src: "/static/pictograms/confused.png"},
    { id: "sad", label: "Sad", src: "/static/pictograms/sad.png"},
    { id: "ashamed", label: "Ashamed", src: "/static/pictograms/ashamed.png"},
    { id: "angry", label: "Angry", src: "/static/pictograms/angry.png"},
    {id: "scared", label:"Scared", src: "/static/pictograms/scared.png"},
    {id:"disgusted", label:"Disgusted", src:"/static/pictograms/disgusted.png"},
    {id: "surprised", label:"Surprised", src:"/static/pictograms/surprised.png"}

]

function addToSelection(pictogram) {
    const selection = document.getElementById("selected-pictograms");

    const deja = selection.querySelectorAll("img").length;
    if (deja>=5) return;
    if (deja==0) {
        document.getElementById("buttons-pict").removeAttribute("hidden");
    }
    
    const img = document.createElement("img");

    img.src = pictogram.src;
    img.alt = pictogram.label;
    img.style.width = "40px";
    selection.appendChild(img);

    
}

function renderGrid() {
    for (let i=0; i<pictograms.length; i++) {
        const div = document.createElement("div");
        div.classList.add("col-3");
        grid.appendChild(div);

        const img = document.createElement("img");
        img.src = pictograms[i].src;
        img.alt = pictograms[i].label;
        img.style.width = "80px";
        img.style.height = "80px";
        img.style.objectFit = "contain";
        div.appendChild(img);

        const p = document.createElement("p");
        p.textContent = pictograms[i].label;
        div.appendChild(p);

        div.addEventListener("click", function() {
            addToSelection(pictograms[i]);
        });
    }
}
