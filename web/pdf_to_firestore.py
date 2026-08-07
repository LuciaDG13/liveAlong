"""
pdf_to_firestore.py

Pipeline: PAAutism PDF -> extracted text -> draft transcription (Carol Gray
template, optionally LLM-assisted) -> manual review -> Firestore.

Produces 3 documents in the "SocialStories" collection (one per levelAutism:
1, 2, 3), sharing the same theme, each with its own tailored story text.

USAGE
-----
Manual mode (no LLM, you write the story yourself using the template):
    python pdf_to_firestore.py path/to/story.pdf

LLM-assisted mode (drafts a first version using your local model, you review
and edit before saving -- nothing is written to Firestore without your
explicit confirmation):
    python pdf_to_firestore.py path/to/story.pdf --llm

Run from the project root (same place you run app.py), so that the
"database" package is importable exactly like in app.py.
"""

import argparse
import os
import re
import sys
import tempfile
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pdfplumber
from database.firebase_client import db


LEVEL_GUIDANCE = {
    1: (
        "Level 1 autism: keep language close to the original wording. "
        "Perspective sentences (what others think/feel) can be a bit more "
        "nuanced. Sentences can be a normal length."
    ),
    2: (
        "Level 2 autism: use shorter, more concrete sentences. Reduce "
        "inferred-perspective sentences to the simplest, clearest ones. "
        "Avoid idioms or figurative language entirely."
    ),
    3: (
        "Level 3 autism: use very short sentences, one idea per sentence, "
        "extremely literal language. Write as if each sentence will be "
        "paired with a single pictogram. No figurative language at all."
    ),
}

CAROL_GRAY_TEMPLATE = """\
Use this structure (Carol Gray social story format):
1. Descriptive sentence(s) - state the facts of the situation (when, where, what happens).
2. Descriptive sentence(s) - 1-2 more concrete details.
3. Perspective sentence(s) - what other people involved probably think or feel.
4. Affirmative sentence(s) - why this matters / a shared value or rule.
5. Directive/coaching sentence(s) - a gentle suggestion, phrased as "I can try to..." (never "I must" or "I will").
6. Affirmative sentence(s) - reassurance that the child can handle this situation.

Keep a low ratio of directive sentences compared to descriptive/perspective/affirmative
ones (roughly 1 directive sentence for every 2-5 other sentences) -- this should read as
a supportive narrative, not a list of instructions.
"""


def extract_pdf_text(pdf_path):
    """Extract raw text from the PDF. Prints a warning if nothing usable is found
    (likely a scanned/image-only PDF -- see pdf-reading skill for OCR fallback)."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    full_text = "\n".join(text_parts).strip()

    if not full_text:
        print(
            "\n[WARNING] No extractable text found -- this PDF might be scanned "
            "(image-only). You'll need to type the source content manually below."
        )
    return full_text


def open_for_editing(initial_content, filename_hint="draft.txt"):
    """Writes content to a temp file, opens it in the default editor (Notepad on
    Windows), waits for the user to finish editing, then reads it back."""
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, filename_hint)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(initial_content)

    print(f"\nOpening {tmp_path} for you to review/edit...")
    try:
        if sys.platform.startswith("win"):
            os.startfile(tmp_path)  # noqa: S606 (Windows-only helper, intended use)
        elif sys.platform == "darwin":
            subprocess.run(["open", tmp_path])
        else:
            subprocess.run(["xdg-open", tmp_path])
    except Exception:
        print(f"Could not auto-open the file. Please open it manually: {tmp_path}")

    input("Press Enter here once you're done editing and have saved the file...")

    with open(tmp_path, "r", encoding="utf-8") as f:
        edited_content = f.read().strip()

    return edited_content


def generate_llm_draft(raw_text, theme, level):
    """Uses the local model already loaded in companion.py to draft a first
    version of the story for a given autism level. Lazy-imported so that
    manual mode (--no llm flag) never pays the cost of loading the model."""
    from llm.companion import tokenizer, model, MODEL_AVAILABLE
    import torch

    if not MODEL_AVAILABLE:
        print("[WARNING] Local model not available -- falling back to manual mode for this level.")
        return None

    prompt = f"""You are adapting a social story for a child with autism, theme: "{theme}".

{LEVEL_GUIDANCE[level]}

{CAROL_GRAY_TEMPLATE}

Source material (from an existing PAAutism resource, to be rewritten -- do not
copy verbatim, rewrite in your own words following the structure above):
---
{raw_text[:4000]}
---

Write only the resulting social story text, nothing else (no preamble, no headers).
"""
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to("cuda")

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=600,
            do_sample=True,
            temperature=0.6,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def build_manual_skeleton(theme, level):
    return (
        f"# Theme: {theme}\n"
        f"# Level: {level} -- {LEVEL_GUIDANCE[level]}\n\n"
        f"{CAROL_GRAY_TEMPLATE}\n"
        f"Write the story below this line, delete these instructions when done:\n"
        f"------------------------------------------------------------\n\n"
    )


def get_story_for_level(raw_text, theme, level, use_llm):
    print(f"\n=== Level {level} ===")
    if use_llm:
        draft = generate_llm_draft(raw_text, theme, level)
        if draft is None:
            draft = build_manual_skeleton(theme, level)
    else:
        draft = build_manual_skeleton(theme, level)

    edited = open_for_editing(draft, filename_hint=f"story_level{level}.txt")

    # Strip any leftover instructional header if the skeleton wasn't fully replaced
    edited = re.sub(r"^#.*\n", "", edited, flags=re.MULTILINE)
    edited = edited.replace(
        "Write the story below this line, delete these instructions when done:", ""
    )
    edited = edited.replace("-" * 60, "")
    return edited.strip()


def ask_tag_list(prompt_text):
    raw = input(prompt_text).strip()
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def main():
    parser = argparse.ArgumentParser(description="Transcribe a PAAutism PDF social story into Firestore.")
    parser.add_argument("pdf_path", help="Path to the source PDF")
    parser.add_argument("--llm", action="store_true", help="Use the local model to draft a first version")
    args = parser.parse_args()

    print(f"Reading {args.pdf_path}...")
    raw_text = extract_pdf_text(args.pdf_path)
    if raw_text:
        print("\n--- Extracted text (preview) ---")
        print(raw_text[:800])
        print("--- end preview ---\n")
    else:
        raw_text = open_for_editing(
            "# Paste or type the source content from the PDF here, then save and close.\n\n",
            filename_hint="source_content.txt"
        )

    theme = input("Theme for this story (e.g. 'Waiting in line'): ").strip()

    print(
        "\nSensory and interest tags apply to all 3 levels below (edit per-level "
        "later in Firestore if a specific level needs different tags)."
    )
    sensory_tags = ask_tag_list(
        "Sensory tags, comma-separated (options: auditory, visual, tactile, olfactory, gustatory) or leave empty: "
    )
    interest_tags = ask_tag_list(
        "Interest tags, comma-separated (free text, e.g. 'dinosaurs, trains') or leave empty: "
    )

    stories_by_level = {}
    for level in (1, 2, 3):
        stories_by_level[level] = get_story_for_level(raw_text, theme, level, args.llm)

    print("\n=== Summary before saving to Firestore ===")
    for level, story in stories_by_level.items():
        print(f"\n--- Level {level} ---")
        print(story[:300] + ("..." if len(story) > 300 else ""))

    confirm = input("\nSave these 3 documents to Firestore now? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("Aborted -- nothing was saved.")
        return

    for level, story in stories_by_level.items():
        doc_ref = db.collection("SocialStories").add({
            "theme": theme,
            "levelAutism": level,
            "story": story,
            "sensory_tags": sensory_tags,
            "interest_tags": interest_tags,
        })
        print(f"Saved level {level} -> document id: {doc_ref[1].id}")

    print("\nDone.")


if __name__ == "__main__":
    main()