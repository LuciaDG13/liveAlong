// --- 1. Formes de bouche Rhubarb (A-X) ---------------------------------
// Rhubarb utilise 6 formes de base (A-F) + 3 optionnelles (G, H, X).
// Ci-dessous : les 'd' de <path> à réutiliser dans le SVG de l'avatar,
// dans le même repère que le fichier avatar-enfant-tsa.html
// (bouche centrée autour de x=150, y=185-195).
const RHUBARB_MOUTHS = {
  A: `<path d="M126,188 Q150,190 174,188" style="stroke:var(--avatar-outline);stroke-width:5;fill:none" stroke-linecap="round"/>`,
  B: `<path d="M128,183 Q150,189 172,183 Q150,195 128,183 Z" style="stroke:var(--avatar-outline);fill:var(--avatar-mouth-interior)"/>`,
  C: `<path d="M124,178 Q150,169 176,178 Q150,203 124,178 Z" style="stroke:var(--avatar-outline);fill:var(--avatar-mouth-interior)"/>`,
  D: `<path d="M120,170 Q150,155 180,170 Q150,224 120,170 Z" style="stroke:var(--avatar-outline);fill:var(--avatar-mouth-interior-dark)"/>`,
  E: `<path d="M126,180 Q150,173 174,180 Q150,199 126,180 Z" style="stroke:var(--avatar-outline);fill:var(--avatar-mouth-interior)"/>`,
  F: `<path d="M138,183 Q150,178 162,183 Q150,196 138,183 Z" style="stroke:var(--avatar-outline);fill:var(--avatar-mouth-interior)"/>`,
  X: `<path d="M126,187 Q150,190 174,187" style="stroke:var(--avatar-outline);stroke-width:5;fill:none" stroke-linecap="round"/>`
};
// --- 2. Lecteur synchronisé --------------------------------------------
class AvatarSpeechPlayer {
  /**
   * @param {SVGElement} mouthGroupEl - élément <g id="avatar-mouth"> dans l'avatar
   * @param {HTMLAudioElement} audioEl - élément <audio> qui joue la phrase
   */
  constructor(mouthGroupEl, audioEl){
    this.mouthEl = mouthGroupEl;
    this.audio = audioEl;
    this.cues = [];       // [{start: secondes, shape: "A"}, ...]
    this._raf = null;
  }

  /**
   * Charge le minutage produit par Rhubarb (format JSON natif de l'outil)
   * et convertit en une liste triée de repères temporels.
   * Exemple de sortie Rhubarb (--exportFormat json) :
   * { "mouthCues": [ { "start": 0.00, "end": 0.12, "value": "X" }, ... ] }
   */
  loadRhubarbCues(rhubarbJson){
    this.cues = rhubarbJson.mouthCues
      .map(c => ({ start: c.start, shape: c.value }))
      .sort((a, b) => a.start - b.start);
    this._setMouth("X"); // position de repos par défaut
  }

  play(){
    this.audio.currentTime = 0;
    this.audio.play();
    this._tick();
  }

  stop(){
    this.audio.pause();
    cancelAnimationFrame(this._raf);
    this._setMouth("X");
  }

  _tick(){
    if (this.audio.paused || this.audio.ended){
      this._setMouth("X");
      return;
    }
    const t = this.audio.currentTime;
    // trouve le dernier repère dont le "start" est <= au temps courant
    let current = this.cues[0];
    for (const cue of this.cues){
      if (cue.start <= t) current = cue; else break;
    }
    if (current) this._setMouth(current.shape);
    this._raf = requestAnimationFrame(() => this._tick());
  }

  _setMouth(shape){
    this.mouthEl.innerHTML = RHUBARB_MOUTHS[shape] || RHUBARB_MOUTHS.X;
  }
}

// Utilisable en module ES ou en script classique
if (typeof module !== "undefined") module.exports = { AvatarSpeechPlayer, RHUBARB_MOUTHS };