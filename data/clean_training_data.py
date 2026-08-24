"""ETAPE 4 -- minimal cleaning pass over data/lora_training_data.jsonl.

Combines automated checks with a short manual exclude list (judgment calls
made after reading every generated row by hand -- see the conversation/PR
notes, not re-derivable from the data alone) and writes
data/lora_training_data.clean.jsonl, the file ASD-iLLM/train_livealong_lora.py
actually trains on.

Automated checks (applied only to source=="generated" rows -- the 30
handwritten rows are trusted as-is):
1. Drop rows containing the Unicode replacement character (encoding
   corruption seen in a couple of Persona C generations).
2. Drop rows where child_message contains the persona's own first name --
   a child would not address themselves in the third person; this is a
   generation bug (companion-voice bleeding into the child_message field),
   observed on Persona B ("Alex, can you help me find...").
3. Persona C only (non-verbal, pictogram grid): drop rows where any
   comma-separated token in child_message is not in the exact pictogram
   vocabulary from web/static/js/pictograms.js (data/personas.py).

Manual exclude list: a few Persona A rows that assume the companion can
hand over a physical object, or that have it self-identify as "AI" --
off-brand/incoherent given the app is a text+voice avatar, not caught by
the automated checks above.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from personas import PICTOGRAM_VOCABULARY  # noqa: E402

INPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lora_training_data.jsonl")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lora_training_data.clean.jsonl")

REPLACEMENT_CHAR = "�"

ALLOWED_PICTOGRAMS = {
    w.lower() for group in PICTOGRAM_VOCABULARY.values() for w in group
}

# Exact child_message strings to drop -- judgment calls from manually
# reading every generated row across both generation rounds, not reliably
# detectable automatically (physical-embodiment claims, off-brand framing,
# and -- new in round 2 -- an actual metaphor slipping past a "no metaphors"
# system-prompt rule that only a human read can reliably catch).
MANUAL_EXCLUDE = {
    # Round 1
    ("A", "Hi, who are you?"),                          # companion self-identifies as "AI" -- off-brand
    ("A", "Can I have a toy car?"),                      # implies the companion can hand over a physical object
    ("A", "Can you help me find my favorite toy?"),      # same physical-embodiment issue
    # Round 2
    ("A", "I don't want to share my blocks."),           # "watch over them" -- physical custodial claim
    ("A", "I don't like the new crayon colors."),        # "I'll hold the paper for you" -- physical claim
    ("B", "I want to share my dinosaur toy with you for a minute."),  # physical toy handoff
    ("B", "I don't like it when people don’t listen to me."),          # actual metaphor ("talk to a planet too far away") -- violates the "no metaphors" system-prompt rule
    ("B", "I asked you to pass the dinosaur toy and you took too long."),   # companion claims to have physically failed to pass an object
}


def is_pictogram_valid(child_message):
    tokens = [t.strip().lower() for t in child_message.split(",")]
    return all(t in ALLOWED_PICTOGRAMS for t in tokens)


def drop_reason(row):
    if row["source"] != "generated":
        return None

    text = row["child_message"] + row["target_response"]
    if REPLACEMENT_CHAR in text:
        return "encoding corruption"

    name = row["profile"]["name"]
    if name.lower() in row["child_message"].lower():
        return f"child_message addresses persona by name ({name}) -- companion-voice bleed"

    if row["persona_id"] == "C" and not is_pictogram_valid(row["child_message"]):
        return "child_message uses words outside the real pictogram vocabulary"

    if (row["persona_id"], row["child_message"]) in MANUAL_EXCLUDE:
        return "manual exclude (physical-embodiment / off-brand content)"

    return None


def main():
    kept, dropped = [], []
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            reason = drop_reason(row)
            if reason:
                dropped.append((row, reason))
            else:
                kept.append(row)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Kept {len(kept)} / {len(kept) + len(dropped)} rows -> {OUTPUT_PATH}\n")
    print("Dropped:")
    for row, reason in dropped:
        print(f"  [{row['persona_id']}] \"{row['child_message']}\"  -- {reason}")

    from collections import Counter
    print("\nPer persona (kept):", Counter(r["persona_id"] for r in kept))


if __name__ == "__main__":
    main()
