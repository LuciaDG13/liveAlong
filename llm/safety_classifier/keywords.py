"""Deterministic high-recall pre-filter for unambiguous crisis language.

Any phrase in CRISIS_KEYWORDS short-circuits classify_message() straight to
"crisis", regardless of what the ML classifier would have said -- this is
the recall safety net for phrasing the (currently tiny, crisis-free)
training set has never seen.

Intentionally empty. Do not add phrases here unilaterally: per
TAXONOMY_DRAFT.md, any crisis-indicating keyword/phrase must be reviewed
with Dr Kanaga first. Until this list is populated, the pre-filter layer
is inert and crisis detection has no real capability yet.
"""

CRISIS_KEYWORDS = []


def matches_crisis_keyword(text):
    lowered = text.lower()
    for phrase in CRISIS_KEYWORDS:
        if phrase.lower() in lowered:
            return phrase
    return None
