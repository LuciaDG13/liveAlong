"""ETAPE 3 -- few-shot synthetic data generation.

Reuses the model/tokenizer already loaded by llm/companion.py (base
Qwen2.5-7B-Instruct + the *current production* LoRA adapter, see
config/config.py::LORA_PATH) to generate, per persona, N new
child_message/target_response pairs in the style of that persona's
hand-written reference examples (data/reference_examples.jsonl).

Run from the project root with the LiveAlong conda env:
    python data/generate_synthetic_data.py

Writes data/lora_training_data.jsonl = the 30 hand-written examples +
the newly generated ones, each tagged with persona_id/source, ready for
ETAPE 4 (cleaning) and ETAPE 5 (training).
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch  # noqa: E402

from personas import PERSONAS, PICTOGRAM_VOCABULARY  # noqa: E402

REFERENCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_examples.jsonl")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lora_training_data.jsonl")

N_PER_PERSONA = 20
GEN_MAX_NEW_TOKENS = 3200
GEN_TEMPERATURE = 0.85
MAX_ATTEMPTS_PER_PERSONA = 4


def load_reference_examples():
    by_persona = {}
    with open(REFERENCE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            by_persona.setdefault(row["persona_id"], []).append(row)
    return by_persona


def build_generation_prompt(persona, examples, n):
    profile = persona["profile"]
    examples_block = "\n".join(
        f'{i + 1}. child_message: "{ex["child_message"]}"\n   target_response: "{ex["target_response"]}"'
        for i, ex in enumerate(examples)
    )

    constraint = ""
    if persona["persona_id"] == "C":
        vocab_flat = ", ".join(
            f'"{w}"' for group in PICTOGRAM_VOCABULARY.values() for w in group
        )
        constraint = (
            "\nIMPORTANT: this child is non-verbal and communicates ONLY through a "
            "pictogram grid. Every child_message MUST be a comma-separated sequence of "
            "1 to 4 items chosen ONLY from this exact vocabulary (no other words, no "
            f"full sentences): {vocab_flat}.\n"
        )
    elif persona["persona_id"] == "D":
        constraint = (
            "\nIMPORTANT: this child is partially verbal. Every child_message MUST stay "
            "a short fragment or telegraphic phrase (at most 5-6 words), with simple or "
            "missing grammar (e.g. 'no more this.', 'want beetle.'). NEVER a full, "
            "grammatically complete sentence.\n"
        )

    return f"""
You are helping build training data for an AI companion that talks with a
child with Autism Spectrum Disorder (ASD), following ABA-informed dialogue
principles (clear instruction, appropriate assistance, positive
reinforcement), a warm tone, and concrete language with no metaphors,
adapted to the child's profile below.

Persona profile:
- Name: {profile['name']}
- Support level (levelAutism): {profile['levelAutism']}
- Sensory sensitivities: {', '.join(profile['sensory']) or 'none declared'}
- Interest: {profile['interest']}
- Communication: {profile['language']}

Real example turns for this persona (study the style, vocabulary level, and
how the companion responds):
{examples_block}
{constraint}
Generate {n} NEW child_message/target_response pairs for this SAME persona,
in the same style, covering DIFFERENT situations than the examples above
(vary the themes: greetings, sharing, changes of plan, saying no, asking for
help, ending a session, etc.). Do not repeat the examples above. Keep each
target_response brief (2-4 sentences), matching the tone above.

Answer ONLY with a JSON array, no text before or after, in this exact format:
[
  {{"child_message": "...", "target_response": "..."}},
  ...
]
"""


PAIR_REGEX = re.compile(
    r'\{\s*"child_message"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"target_response"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}',
    re.DOTALL,
)


def _json_unescape(raw_string_body):
    """raw_string_body is the text between the quotes of a JSON string --
    wrap it back into a quoted literal and let json.loads handle \\n, \\", etc."""
    return json.loads('"' + raw_string_body + '"')


def parse_generated_pairs(response_text):
    """Try a strict JSON array parse first; if that fails (e.g. one bad
    escape breaks the whole array, as seen with Persona B), fall back to a
    regex scan that salvages every individually well-formed
    {"child_message": ..., "target_response": ...} object instead of losing
    the whole batch."""
    clean = response_text.replace("```json", "").replace("```", "").strip()
    start, end = clean.find("["), clean.rfind("]")
    if start != -1 and end != -1:
        try:
            parsed = json.loads(clean[start:end + 1])
            pairs = [
                (item["child_message"], item["target_response"])
                for item in parsed
                if isinstance(item, dict) and "child_message" in item and "target_response" in item
            ]
            if pairs:
                return pairs
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    pairs = []
    for match in PAIR_REGEX.finditer(response_text):
        try:
            pairs.append((_json_unescape(match.group(1)), _json_unescape(match.group(2))))
        except json.JSONDecodeError:
            continue
    return pairs


def generate_for_persona(model, tokenizer, persona, examples, n):
    prompt = build_generation_prompt(persona, examples, n)
    messages = [{"role": "system", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=GEN_MAX_NEW_TOKENS,
            do_sample=True,
            temperature=GEN_TEMPERATURE,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    response_text = tokenizer.decode(new_tokens, skip_special_tokens=True)

    pairs = parse_generated_pairs(response_text)
    if not pairs:
        raise ValueError(f"No usable pairs found in model output:\n{response_text[:500]}")

    return [
        {
            "persona_id": persona["persona_id"],
            "source": "generated",
            "profile": persona["profile"],
            "child_message": child_message,
            "target_response": target_response,
        }
        for child_message, target_response in pairs
    ]


def generate_for_persona_with_retries(model, tokenizer, persona, examples):
    """Keep retrying (fresh sampling each time) and accumulating rows,
    deduplicated by child_message, until we reach N_PER_PERSONA or run out
    of attempts."""
    pid = persona["persona_id"]
    collected = {}
    for attempt in range(1, MAX_ATTEMPTS_PER_PERSONA + 1):
        still_needed = N_PER_PERSONA - len(collected)
        if still_needed <= 0:
            break
        try:
            rows = generate_for_persona(model, tokenizer, persona, examples, still_needed)
        except Exception as exc:
            print(f"    attempt {attempt}/{MAX_ATTEMPTS_PER_PERSONA} for persona {pid} failed: {exc}")
            continue
        new_count = 0
        for row in rows:
            key = row["child_message"].strip().lower()
            if key not in collected:
                collected[key] = row
                new_count += 1
        print(f"    attempt {attempt}/{MAX_ATTEMPTS_PER_PERSONA} for persona {pid}: "
              f"+{new_count} new (total {len(collected)}/{N_PER_PERSONA})")
    return list(collected.values())


def main():
    from llm.companion import model, tokenizer, MODEL_AVAILABLE

    if not MODEL_AVAILABLE:
        print("MODEL_AVAILABLE is False -- the base model + LoRA adapter could not be "
              "loaded. Nothing was generated. See the console output above for the "
              "loading error.")
        sys.exit(1)

    reference_by_persona = load_reference_examples()
    handwritten_rows = [row for rows in reference_by_persona.values() for row in rows]

    generated_rows = []
    for persona in PERSONAS:
        pid = persona["persona_id"]
        examples = reference_by_persona.get(pid, [])
        print(f"--- Generating up to {N_PER_PERSONA} examples for persona {pid} "
              f"({persona['profile']['name']}) ---")
        rows = generate_for_persona_with_retries(model, tokenizer, persona, examples)
        print(f"    final: {len(rows)}/{N_PER_PERSONA} usable rows")
        generated_rows.extend(rows)

    all_rows = handwritten_rows + generated_rows
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(all_rows)} total rows to {OUTPUT_PATH} "
          f"({len(handwritten_rows)} handwritten + {len(generated_rows)} generated)")


if __name__ == "__main__":
    main()
