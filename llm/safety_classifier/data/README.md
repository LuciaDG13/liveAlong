# Dataset status -- DRAFT, UNREVIEWED

`train.csv` / `eval.csv` currently contain only `none` and `mild_distress`
examples. **There are intentionally zero `crisis`-labeled examples.**

This is not an oversight. Per `TAXONOMY_DRAFT.md`, any `crisis`-labeled
example needs to be written and reviewed together with Dr Kanaga, not
drafted unilaterally. Until that happens, the classifier trained on this
data cannot detect a real crisis at all -- it only distinguishes ordinary
content from mild distress signals. Real crisis detection currently depends
entirely on the keyword pre-filter in `keywords.py`, which is also
intentionally empty for the same reason.

Every row here is marked `source=draft-unreviewed`: none of it has been
checked by a clinician. It exists to let the training/evaluation pipeline
be built and tested end-to-end, not to represent a validated dataset.

Before this dataset is extended or used for anything beyond local pipeline
testing:
1. Get the taxonomy in `TAXONOMY_DRAFT.md` reviewed and approved.
2. Write `crisis` examples together with Dr Kanaga (not solo).
3. Have every example -- especially every `crisis` one -- manually reviewed
   before it's added here.
