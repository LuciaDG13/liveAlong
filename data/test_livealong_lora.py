"""ETAPE 6 -- quick check that the new adapter (ASD-iLLM/lora-weight-livealong/)
behaves differently from the original ASD-iLLM adapter it was continued from.

Loads the base model ONCE, then loads BOTH adapters onto it as named PEFT
adapters (no extra VRAM for the base weights) and switches between them with
model.set_adapter(...), plus model.disable_adapter() for the raw base model.
This directly compares "original ASD-iLLM" vs "new livealong adapter" (not
just "base model" vs "new adapter", which poster_lora_comparison.py alone
would show) -- that's the actual comparison ETAPE 6 asks to verify.

Run from the project root with the LiveAlong conda env:
    python data/test_livealong_lora.py
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # noqa: E402
from peft import PeftModel  # noqa: E402

from config.config import LLM_MODEL, LLM_MAX_TOKENS  # noqa: E402
from config.config import BASE_DIR  # noqa: E402
from personas import PERSONAS_BY_ID  # noqa: E402

ORIGINAL_LORA_PATH = os.path.join(BASE_DIR, "ASD-iLLM", "lora-weight")
NEW_LORA_PATH = os.path.join(BASE_DIR, "ASD-iLLM", "lora-weight-livealong")

# At least 2-3 of the 5 personas: A (existing, regression check) + the two
# genuinely new/most distinctive ones (C: non-verbal, D: partially verbal).
TEST_PERSONA_IDS = ["A", "C", "D"]

CHILD_MESSAGE_BY_PERSONA = {
    "A": "I don't want to wait, it's boring.",
    "B": "Can we talk about something harder next time?",
    "C": "no, help",
    "D": "no more this.",
    "E": "This tag is scratchy, I can't focus.",
}

EXERCISE = "A story about waiting in line."


def generate(model, tokenizer, profile, child_message):
    sensory = ", ".join(profile["sensory"]) if profile["sensory"] else "none declared"
    system_prompt = (
        "You are a conversational companion for a child with Autism Spectrum "
        "Disorder, following ABA-informed principles (clear instruction, "
        "appropriate assistance, positive reinforcement). Be warm, concrete, "
        "and avoid metaphors.\n"
        f"Profile of the child:\n- Name: {profile['name']}\n"
        f"- Level of autism: {profile['levelAutism']}\n"
        f"- Sensory sensibilities: {sensory}\n- Interests: {profile['interest']}\n"
        f"- Communication: {profile['language']}\n"
        f"This is the exercise: {EXERCISE}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": child_message},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=min(LLM_MAX_TOKENS, 300),
            do_sample=True,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


def main():
    if not os.path.isdir(NEW_LORA_PATH):
        print(f"New adapter not found at {NEW_LORA_PATH} -- run "
              f"ASD-iLLM/train_livealong_lora.py first.")
        sys.exit(1)

    print(f"Loading base model {LLM_MODEL} (4-bit NF4)...")
    tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL, quantization_config=quantization_config, device_map="auto"
    )

    print(f"Loading original ASD-iLLM adapter from {ORIGINAL_LORA_PATH}...")
    model = PeftModel.from_pretrained(base_model, ORIGINAL_LORA_PATH, adapter_name="original")
    print(f"Loading new livealong adapter from {NEW_LORA_PATH}...")
    model.load_adapter(NEW_LORA_PATH, adapter_name="livealong")
    model.eval()

    for pid in TEST_PERSONA_IDS:
        persona = PERSONAS_BY_ID[pid]
        profile = persona["profile"]
        child_message = CHILD_MESSAGE_BY_PERSONA[pid]

        print("=" * 70)
        print(f"Persona {pid} -- {profile['name']} ({persona['label']})")
        print(f'child_message: "{child_message}"')
        print("=" * 70)

        print("\n--- BASE MODEL (no adapter) ---\n")
        with model.disable_adapter():
            print(generate(model, tokenizer, profile, child_message))

        print("\n--- ORIGINAL ASD-iLLM adapter ---\n")
        model.set_adapter("original")
        print(generate(model, tokenizer, profile, child_message))

        print("\n--- NEW livealong adapter (continued training, q_proj/v_proj) ---\n")
        model.set_adapter("livealong")
        print(generate(model, tokenizer, profile, child_message))
        print()


if __name__ == "__main__":
    main()
