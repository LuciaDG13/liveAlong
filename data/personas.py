"""5 personas used to build the LiveAlong-specific LoRA training data.

Cross 3 axes (communication mode x support level x dominant sensory
sensitivity), covering the most representative combinations rather than
every possible combination. Personas A and B are the exact profiles already
used in poster_lora_comparison.py -- reused here as-is so both scripts stay
consistent.

Each profile dict uses the same shape consumed by llm/companion.py::run_session
(name, levelAutism, sensory, interest, language). "communication_type" and
"persona_id" are extra metadata, not read by run_session, kept here for the
data-generation/training scripts and for traceability in the JSONL files.
"""

PERSONAS = [
    {
        "persona_id": "A",
        "label": "Persona A -- level 3, simple vocabulary, noise-sensitive",
        "communication_type": "Verbal",
        "profile": {
            "name": "Sam",
            "levelAutism": 3,
            "sensory": ["loud noises", "bright lights"],
            "interest": "trains",
            "language": "simple, short sentences",
        },
    },
    {
        "persona_id": "B",
        "label": "Persona B -- level 1, rich vocabulary, no declared sensitivity",
        "communication_type": "Verbal",
        "profile": {
            "name": "Alex",
            "levelAutism": 1,
            "sensory": [],
            "interest": "dinosaurs and space",
            "language": "rich vocabulary, longer sentences",
        },
    },
    {
        "persona_id": "C",
        "label": "Persona C -- non-verbal (pictogram grid), level 2, light-sensitive",
        "communication_type": "Non-verbal",
        "profile": {
            "name": "Noor",
            "levelAutism": 2,
            "sensory": ["bright lights"],
            "interest": "animals",
            "language": "non-verbal, communicates through the pictogram grid only",
        },
    },
    {
        "persona_id": "D",
        "label": "Persona D -- partially verbal, level 2, no declared sensitivity, strong restricted interest",
        "communication_type": "Partially verbal",
        "profile": {
            "name": "Milo",
            "levelAutism": 2,
            "sensory": [],
            "interest": "insects, especially beetles",
            "language": "partially verbal, short fragments and single words, echolalia",
        },
    },
    {
        "persona_id": "E",
        "label": "Persona E -- level 1, verbal, touch/texture-sensitive",
        "communication_type": "Verbal",
        "profile": {
            "name": "Priya",
            "levelAutism": 1,
            "sensory": ["clothing tags", "sticky textures", "unexpected touch"],
            "interest": "music and singing",
            "language": "verbal, age-typical vocabulary",
        },
    },
]

PERSONAS_BY_ID = {p["persona_id"]: p for p in PERSONAS}

# The real pictogram vocabulary available to non-verbal children in the app
# (web/static/js/pictograms.js) -- kept here so hand-written and generated
# examples for Persona C stay realistic: raw pictogram sequences joined with
# ", " (matching child.js's `labels.join(", ")`), never full sentences.
PICTOGRAM_VOCABULARY = {
    "needs": ["I want", "I need", "more", "stop", "help", "done"],
    "actions": ["play", "eat", "drink", "sleep", "go out", "go"],
    "people": ["mom", "dad", "therapist", "me", "you"],
    "emotions": ["happy", "confused", "sad", "ashamed", "angry", "scared", "disgusted", "surprised", "great"],
    "core": ["yes", "no"],
}
