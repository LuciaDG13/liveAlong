# Distress/crisis taxonomy -- DRAFT, NOT APPROVED

**Status: engineering proposal only. Nothing in this document has been
reviewed by Dr Kanaga or any clinician. Do not treat these categories,
examples, or thresholds as final. Nothing derived from this taxonomy
(dataset, classifier, scripted responses) should be used with real children
until this document is reviewed and signed off.**

## Why this exists

LiveAlong is meant to be reachable by a child at any time for support. The
project's own literature review cites ~79% psychiatric comorbidity and ~72%
suicidal ideation in autistic adults. An always-available AI companion for
this population needs a way to notice when a child's message signals
distress or crisis, and to involve a human -- it should never try to handle
a real crisis on its own. This document proposes a starting taxonomy for
that detection layer, to be discussed with Dr Kanaga before any of it is
used to label real training data.

## Proposed categories (ordinal severity)

### `none`
Ordinary conversational content, including normal-range negative emotion
that isn't a distress signal in itself (frustration, mild sadness, sensory
complaints, disliking an activity).

*Illustrative (not exhaustive) examples:*
- "I don't like loud noises."
- "I'm annoyed at my sister."
- "Today was boring."

### `mild_distress`
Signals of sadness, anxiety, overwhelm, or dysregulation that a therapist
would want visibility into, but that are not acutely dangerous on their own.

*Illustrative (not exhaustive) examples:*
- "I feel really bad today."
- "Nobody at school likes me."
- "I don't want to go outside anymore."

### `crisis`
Explicit or strongly implied self-harm, suicidal ideation, or immediate
danger language.

*No illustrative examples are included in this draft document.* Any
example list for this category should be written and reviewed together
with Dr Kanaga directly, not drafted unilaterally and handed over after
the fact.

## Open questions for Dr Kanaga

1. Are three classes enough, or is a fourth needed (e.g. an
   "ambiguous/needs-human-judgment" class distinct from a confident
   `crisis` classification)?
2. Should other-directed aggression/harm (toward another person) be its
   own category, separate from self-harm?
3. Autistic children's communication is often more literal/concrete than
   neurotypical children's (per the project's own literature review). Does
   that change what should count as `crisis` vs `mild_distress` -- e.g.
   could a literal phrase be miscategorized as figurative, or vice versa?
4. What is the intended response for each level -- is `mild_distress`
   meant to be therapist-visible only, or should it ever change what the
   companion says to the child in the moment?
5. Should thresholds/categories differ by the child's ASD support level
   (1/2/3) or age, given very different communication profiles?

## What happens after this is reviewed

Per the approved project plan, only after this taxonomy is signed off does
work begin on: (a) generating and manually reviewing a labeled synthetic
dataset, and (b) writing the scripted response a child would see if
`crisis` is detected. Both of those also require Dr Kanaga's review before
they're used for anything beyond local testing.
