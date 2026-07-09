import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# 1. Modèle de base officiel (téléchargé automatiquement)
LLM_MODEL = "Qwen/Qwen2.5-7B-Instruct"

# 2. Le chemin vers TON dossier local où se trouvent adapter_config.json et adapter_model.safetensors
path_to_lora = "C:/Users/ISK26RA1001/Documents/Internship-LiveAlong-Lucia/liveAlong/ASD-iLLM/lora-weight"

print("Chargement du tokenizer officiel Qwen2.5...")
tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)

print("Configuration de la compression 4-bits pour la RTX 4070...")
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_quant_type="nf4"
)

print("Chargement du modèle de base Qwen compressé (Léger : ~5 Go)...")
base_model = AutoModelForCausalLM.from_pretrained(
    LLM_MODEL,
    quantization_config=quantization_config,
    device_map="auto"
)

print("Application de l'adaptateur ASD-iLLM depuis ton dossier local...")
model = PeftModel.from_pretrained(base_model, path_to_lora)
model.eval()

# Préparation du test
messages = [
    {"role": "system", "content": "You are a helpful assistant for children with ASD."},
    {"role": "user", "content": "Hello, how are you? Are you an assistant? Are you my friend ?"}
]

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

print("\nGénération de la réponse...")
with torch.no_grad():
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=100
    )

generated_ids = [
    output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
]
response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

print("\n--- Réponse du modèle ---")
print(response)