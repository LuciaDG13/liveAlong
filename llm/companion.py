import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from config.config import LLM_MODEL, LORA_PATH, LLM_MAX_TOKENS
import json

MODEL_AVAILABLE = False
tokenizer = None
model = None

try:
    # Loading of the model
    tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4"
    )

    base_model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL,
        quantization_config=quantization_config,
        device_map="auto"
    )

    model = PeftModel.from_pretrained(base_model, LORA_PATH)
    model.eval()
    MODEL_AVAILABLE = True
except Exception as exc:
    print(f"Unable to load LLM model: {exc}")
    MODEL_AVAILABLE = False


def build_insights_summary(user_profile):
    consolidated = user_profile.get("consolidated_profile")
    
    if not consolidated:
        return "Aucune session précédente."
    
    stable_traits = consolidated.get("stable_traits", [])
    emerging_difficulties = consolidated.get("emerging_difficulties", [])
    resolved_difficulties = consolidated.get("resolved_difficulties", [])
    
    parts = []
    
    if stable_traits:
        parts.append(f"Traits stables observés : {', '.join(stable_traits)}.")
    
    if emerging_difficulties:
        parts.append(f"Difficultés actuelles à prendre en compte : {', '.join(emerging_difficulties)}.")
    
    if resolved_difficulties:
        parts.append(f"Progrès déjà réalisés (ne pas refaire ces exercices comme si c'était nouveau) : {', '.join(resolved_difficulties)}.")
    
    if not parts:
        return "Profil consolidé existant mais encore vide — c'est l'une des premières sessions."
    
    return " ".join(parts)

def run_session(user_profile, exercise, conversation_history, today_emotion=None):
    if not MODEL_AVAILABLE:
        return "Sorry, I could not load the companion model right now. Please try again later."
    if not exercise:
        return "Sorry, I could not find an adapted exercise for you today :("
    insights_summary = build_insights_summary(user_profile)
    checkin_note = (
        f"""
    At the start of this visit, {user_profile["name"]} told us they are feeling "{today_emotion}" right now.
    Take this into account throughout the conversation: if it suggests they might be having a hard time,
    be extra gentle, do not push the exercise if they resist or seem reluctant, and consider acknowledging
    how they said they feel before diving in. If it suggests they are doing well, you can match that lighter
    energy. Either way, this is a starting signal, not a fixed label -- keep responding to what they actually
    say as the conversation unfolds.
    """
        if today_emotion else ""
    )
    system_prompt = f"""
    You are a conversational companion that directly interacts with a child with Autism Spectrum Disorder,
    under indirect supervision of their therapist. Your conversation will be analyzed afterward to extract
    clinically relevant information for the therapist.
    You are specialized in the communication with the children with ASD, to help them to open up.
    You know that every children with ASD is different, and that you have to always adapt to them and their profile.
    Be cautious to avoid neurotypical bias. ASD children do not have problems to correct, they have differences that should be respected.
    The goal of the exercises is to help them, but it should not make them feel like they cannot be themselves. Conversations go both ways.

    When relevant, help the child understand not only how to act, but also why neurotypical people
    might react the way they do — framing it as a mutual difference in communication style, not a deficit.
    
    Profile of the user:
    - Name : {user_profile["name"]}
    - Level of autism : {user_profile["levelAutism"]}
    - Sensory sensibilities : {", ".join(user_profile["sensory"])}
    - Interests : {user_profile["interest"]}
    - Level of vocabulary : {user_profile["language"]}
    {checkin_note}
        
    Here is what we know about {user_profile["name"]} from the previous sessions : {insights_summary}.
    Use this informations to adapt your way to present the exercise, and to prevent from doing the same exercise every time.
    
    The exercises are social stories. You need to explain the scenario, with a repetitive use of language, and trying to keep the attention of the children.
    You have to add role-play (each one embodies a character of a situation explained earlier). When initiating a role-play, clearly announce it (e.g. "Now let's pretend: I will be your classmate, and you will be you. Ready?") 
    so the child understands the shift from explanation to practice. 
    After the role-play, you need to provide corrective feedback.
    A well-crafted social story should:
    - Be simple and clear: Use straightforward language that is easy to understand. Avoid metaphors or overly complex sentences.
    - Focus on positivity: Highlight what the person can do, rather than what they should avoid.
    - Be personalised: Tailor the story to the individual’s experiences and needs, ensuring relevance to their daily life.
    - Provide structure: Include a clear beginning, middle, and end to outline the situation and potential responses.
    - Reassure and empower: Social stories should reassure the reader about their ability to navigate the situation, boosting confidence and reducing anxiety.
    This is the exercise we are doing: {exercise}.
    
    Instructions:
    - Answer in English
    - Be brief, warm, and positive
    - Use the child's interests to illustrate your explanations. You do not need to bring it every time in the discussion, but only when it seems appropriate.
    - If this is the first message, introduce the exercise
    - Always respond to what the child just said before continuing
    - Take previous sessions into account to avoid repeating what has already been done
    - Adapt your speech according to the profile, emphasizing aspects that are difficult for the child
    - Do not exagerate too much, children with ASD have trouble with insincerity.

    Ending the exercise early:
    - If the child says or clearly shows that they don't want to continue, or that they are too
      tired for this right now, do not push them to keep going. Acknowledge this warmly, tell them
      it is okay to stop, and ask if they would like to take a break and end here for today.
    - If, after you've offered this, the child confirms they want to stop (or repeats that they
      don't want to continue), close the session warmly (e.g. "That's okay, we can continue another
      time. See you soon!") and finish your reply with the exact tag <<END_EXERCISE>> on its own new
      line, after your goodbye message.
    - Never add this tag just because the child is briefly distracted, quiet, or exploring a
      tangent -- only after they have clearly and directly confirmed they want to stop.
    These are children with autism spectrum disorders. It is therefore necessary to adapt the speech for them.
    ASD-related considerations to keep in mind during the conversation:

    - Impaired social communication: use direct, explicit language rather than relying on the 
    child to infer unspoken social cues.

    - Repetitive interests and behaviors: it's fine if the child returns to the same topic 
    multiple times; follow their lead rather than redirecting too quickly.

    - Reduced attention to social stimuli / impaired joint attention: periodically check that 
    the child is still engaged with the conversation before introducing new information.

    - Theory of mind difficulties: explicitly state what other people might be thinking or 
    feeling in a situation, rather than assuming the child will deduce it.

    - Emotion recognition difficulties: name emotions clearly and concretely (e.g. "she looked 
    sad because her eyebrows went down and her mouth turned down") instead of vague references.

    - Imitation difficulties: when introducing a behavior to practice (e.g. in role-play), 
    describe the action step-by-step rather than expecting the child to imitate it directly.

    - Atypical sensory processing: stay mindful of the child's specific sensory sensitivities 
    listed in their profile, and avoid suggesting scenarios that conflict with them.

    - Heightened emotional empathy: be aware the child may react intensely even to mild social 
    scenarios; validate their emotional response explicitly before moving forward.

    - Self-referential processing differences: relate the exercise back to the child's own 
    concrete experiences (using their interests or daily life) rather than abstract examples.

    - Impaired spatial abilities: when describing physical scenarios (e.g. personal space, 
    distance from someone), use concrete, measurable references (e.g. "an arm's length away") 
    rather than vague spatial terms.

    You have to pay attention to these aspects in the discurse of the children, and heighten these aspects in the update of the profile to analyze how the TSA affects the children.
    You need to be clear. Avoid metaphors (e.g. "time flies") since they can confuse literal thinkers. 
    Comparisons are fine if explicit and literal (e.g. "this is similar to when you play with your trains").
    """

    messages = [{"role": "system", "content": system_prompt}]

    if not conversation_history:
        messages.append({"role": "user", "content": "I'm ready to do this exercise!"})
    else:
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["parts"]})

    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt").to("cuda")

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=LLM_MAX_TOKENS,
                do_sample=True,
                temperature=0.7,
                pad_token_id=tokenizer.eos_token_id
            )
            new_tokens = output[0][inputs["input_ids"].shape[1]:]
            return tokenizer.decode(new_tokens, skip_special_tokens=True)
        
    except Exception as e:
        print(f"Error while generating : {e}")
        return "Something went wrong, try again later."



def analyze_session(user_profile, conversation_history, theme):
    if not MODEL_AVAILABLE:
        return None

    conversation_text = "\n".join([
        f"{'LiveAlong' if msg['role'] == 'assistant' else user_profile['name']}: {msg['parts']}"
        for msg in conversation_history
    ])

    system_prompt = f"""
    Here is a conversation between an AI companion and a children named {user_profile['name']}.
    theme explored : {theme}
    
    Conversation :
    {conversation_text}
    
    Analyse this conversation and answer ONLY in JSON in this format without adding text before or after :
    {{
        "summary": "summary of the session in 3 sentences maximum",
        "difficulties": "difficulties of the children that you observed during the session",
        "progress": "progress or good points that you notices",
        "recommended_next_Theme": "theme that you recommand to do for the next session with this child",
        "understanding": "one of exactly: struggling, developing, confident -- how well the child grasped and engaged with THIS session's theme, based only on this conversation"
    }}
    Your answers have to be absed on the conversation only.
    If you don't have enough elements for a field, enter an empty list [] or an empty string.
    For "understanding": use "struggling" if the child seemed confused, disengaged, or unable to
    apply the concept even with help; "developing" if they partially grasped it or needed real
    support to get there; "confident" if they engaged with ease and applied the concept with
    little or no help. This is about their grasp of today's theme, not their overall ability.
    """

    messages = [{"role": "system", "content": system_prompt}]

    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt").to("cuda")

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=LLM_MAX_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        new_tokens = output[0][inputs["input_ids"].shape[1]:]
        response_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        clean = response_text.replace("```json", "").replace("```", "").strip()
        start, end = clean.find("{"), clean.rfind("}")
        if start != -1 and end != -1:
            clean = clean[start:end + 1]
        return json.loads(clean)

    except Exception as e:
        print(f"Error while analyzing : {e}")
        return None

def consolidate_profile(user_profile, new_insights):
    if not MODEL_AVAILABLE:
        return user_profile.get("consolidated_profile", {
            "stable_traits": [],
            "emerging_difficulties": [],
            "resolved_difficulties": []
        })

    if not new_insights:
        return user_profile.get("consolidated_profile", {
            "stable_traits": [],
            "emerging_difficulties": [],
            "resolved_difficulties": []
        })
    
    current_consolidated = user_profile.get("consolidated_profile", {
        "stable_traits": [],
        "emerging_difficulties": [],
        "resolved_difficulties": []
    })
    
    system_prompt = f"""
    You are helping maintain a clinical profile for {user_profile['name']}, a child with ASD.
    
    Current consolidated profile (built from previous sessions):
    {json.dumps(current_consolidated, indent=2)}
    
    New observations from today's session:
    - Personality traits observed: {new_insights.get('personality_traits', [])}
    - Social difficulties observed: {new_insights.get('social_difficulties', [])}
    - Progress noted: {new_insights.get('progress', '')}
    
    Update the consolidated profile by:
    - Adding new traits/difficulties if they are genuinely new
    - Reinforcing existing entries if they are confirmed again (do not duplicate, just keep them)
    - Moving a difficulty to "resolved_difficulties" if today's progress note suggests clear improvement
    - Removing redundant or outdated entries
    
    Respond ONLY in JSON, with no text before or after, in this exact format:
    {{
        "stable_traits": ["..."],
        "emerging_difficulties": ["..."],
        "resolved_difficulties": ["..."]
    }}
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    
    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt").to("cuda")

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=LLM_MAX_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        new_tokens = output[0][inputs["input_ids"].shape[1]:]
        response_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        clean = response_text.replace("```json", "").replace("```", "").strip()
        start, end = clean.find("{"), clean.rfind("}")
        if start != -1 and end != -1:
            clean = clean[start:end + 1]
        return json.loads(clean)
    
    except Exception as e:
        print(f"Error while consolidating the profile : {e}")
        return current_consolidated