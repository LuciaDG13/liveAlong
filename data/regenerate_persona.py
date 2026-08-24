"""Standalone recovery tool: regenerate (with retries) just ONE persona's
examples and append them to the existing data/lora_training_data.jsonl,
without touching rows already generated for other personas. Useful if a
full generate_synthetic_data.py run finished with one persona short.

generate_synthetic_data.py itself now retries automatically for every
persona (generate_for_persona_with_retries) -- this script just exposes
that same function for a single persona on demand.

Usage (from the project root, LiveAlong conda env):
    python data/regenerate_persona.py B
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_synthetic_data import (  # noqa: E402
    N_PER_PERSONA,
    OUTPUT_PATH,
    generate_for_persona_with_retries,
    load_reference_examples,
)
from personas import PERSONAS_BY_ID  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("Usage: python data/regenerate_persona.py <persona_id>")
        sys.exit(1)
    persona_id = sys.argv[1]

    from llm.companion import model, tokenizer, MODEL_AVAILABLE
    if not MODEL_AVAILABLE:
        print("MODEL_AVAILABLE is False, aborting.")
        sys.exit(1)

    persona = PERSONAS_BY_ID[persona_id]
    reference_by_persona = load_reference_examples()
    examples = reference_by_persona.get(persona_id, [])

    rows = generate_for_persona_with_retries(model, tokenizer, persona, examples)
    if not rows:
        print(f"Got 0/{N_PER_PERSONA} usable rows for persona {persona_id}.")
        sys.exit(1)

    with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Appended {len(rows)}/{N_PER_PERSONA} rows for persona {persona_id} to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
