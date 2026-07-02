# Points d'amélioration futurs

## Child.html
- Remplacer le système d'apparition/disparition des éléments par un système de grisage (disabled) pour plus de prévisibilité
- Les boutons et zones doivent toujours être visibles
- Revoir le système de navigation des flèches

## À discuter avec la maître de stage
- Rule-based recommendation system
- Emotion tracking
- Intégration nouveau LLM (modèle open source sur GPU)

## Implémentation d'un autre modèle
- Lire cet article sur LoRA: [Article IBM](https://www.ibm.com/fr-fr/think/topics/lora)

### Migration LLM — ASD-iLLM (Qwen2.5-7B + LoRA)
- [BLOQUÉ] Installation PyTorch sur GPU entreprise (RTX 5070, sm_120/Blackwell)
- Cause : Python 3.14 système entre en conflit avec environnements conda dans PowerShell/VSCode
- Solution trouvée : utiliser Anaconda Prompt directement (pas PowerShell ni VSCode terminal)
- Version PyTorch nécessaire confirmée : torch==2.9.1+cu128 (spécifique RTX 5070/sm_120)
- Commande de référence :
  pip install torch==2.9.1+cu128 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
- Environnement conda "livealong" créé (python=3.11)
- À faire ensuite : installer ms-swift, transformers, peft, accelerate
- Réfléchir si ASD-iLLM (LoRA) doit aussi servir pour analyze_session/consolidate_profile, 
  ou si on garde Qwen2.5-7B sans LoRA pour ces deux fonctions (génération JSON structuré)

## Création des profils
- Suggestion pur compléter le profil