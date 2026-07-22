// --- 1. Formes de bouche Rhubarb (A-X) ---------------------------------
// Rhubarb utilise 6 formes de base (A-F) + 3 optionnelles (G, H, X).
// Ci-dessous : les 'd' de <path> à réutiliser dans le SVG de l'avatar,
// dans le même repère que le fichier avatar-enfant-tsa.html
// (bouche centrée autour de x=150, y=185-195).
const RHUBARB_MOUTHS = {
  // A : bouche fermée (M, B, P, silence)
  A: `<path d="M124,188 Q150,192 176,188" stroke="#3A2E22" stroke-width="6" fill="none" stroke-linecap="round"/>`,
  // B : légèrement entrouverte (K, S, T, consonnes serrées)
  B: `<path d="M126,186 Q150,196 174,186 Q150,190 126,186 Z" fill="#3A2E22"/>`,
  // C : ouverte moyenne (E, AE)
  C: `<path d="M120,182 Q150,206 180,182 Q150,196 120,182 Z" fill="#3A2E22"/>`,
  // D : grande ouverture (AA, O, exclamation)
  D: `<ellipse cx="150" cy="190" rx="16" ry="20" fill="#3A2E22"/>`,
  // E : bouche arrondie moyenne (O court, ER)
  E: `<ellipse cx="150" cy="188" rx="12" ry="14" fill="#3A2E22"/>`,
  // F : lèvres resserrées en avant (OU, W)
  F: `<ellipse cx="150" cy="188" rx="8" ry="9" fill="#3A2E22"/>`,
  // X : position de repos (pause dans la parole)
  X: `<path d="M126,187 Q150,190 174,187" stroke="#3A2E22" stroke-width="5" fill="none" stroke-linecap="round"/>`
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