from web.recommendation_service import recommend_exercise, score_story


BASE_PROFILE = {
    "consolidated_profile": {"emerging_difficulties": []},
    "sensory_categories": [],
    "interest": "",
}


def make_story(theme, **overrides):
    story = {"theme": theme, "sensory_tags": [], "interest_tags": []}
    story.update(overrides)
    return story


def make_profile(**overrides):
    profile = {
        "consolidated_profile": {"emerging_difficulties": []},
        "sensory_categories": [],
        "interest": "",
    }
    profile.update(overrides)
    return profile


def test_negative_emotion_penalizes_brand_new_theme():
    story = make_story("New theme")
    score_neutral = score_story(story, BASE_PROFILE, [], set(), theme_counts={}, today_emotion="happy")
    score_sad = score_story(story, BASE_PROFILE, [], set(), theme_counts={}, today_emotion="sad")
    assert score_sad < score_neutral


def test_negative_emotion_favors_familiar_theme():
    story = make_story("Familiar theme")
    score_unfamiliar = score_story(story, BASE_PROFILE, [], set(), theme_counts={"Familiar theme": 1}, today_emotion="sad")
    score_familiar = score_story(story, BASE_PROFILE, [], set(), theme_counts={"Familiar theme": 3}, today_emotion="sad")
    assert score_familiar > score_unfamiliar


def test_positive_emotion_does_not_penalize_new_theme():
    story = make_story("New theme")
    score = score_story(story, BASE_PROFILE, [], set(), theme_counts={}, today_emotion="happy")
    assert score == 0


def test_recommend_exercise_prefers_familiar_theme_on_hard_day():
    stories = [
        make_story("Brand new topic"),
        make_story("Well-practiced topic"),
    ]
    theme_counts = {"Well-practiced topic": 5}

    chosen = recommend_exercise(
        stories, BASE_PROFILE, recent_themes=[], negative_emotion_themes=set(),
        theme_counts=theme_counts, today_emotion="scared"
    )

    assert chosen["theme"] == "Well-practiced topic"


def test_recommend_exercise_returns_none_for_empty_list():
    assert recommend_exercise([], BASE_PROFILE, [], set()) is None


# --- Sensory conflict rule -------------------------------------------------

def test_sensory_conflict_penalizes_proportionally_to_overlap_count():
    story = make_story("Loud environments", sensory_tags=["auditory", "visual"])
    profile_no_conflict = make_profile(sensory_categories=[])
    profile_one_conflict = make_profile(sensory_categories=["auditory"])
    profile_two_conflicts = make_profile(sensory_categories=["auditory", "visual"])

    assert score_story(story, profile_no_conflict, [], set()) == 0
    assert score_story(story, profile_one_conflict, [], set()) == -4
    assert score_story(story, profile_two_conflicts, [], set()) == -8


def test_sensory_conflict_ignores_non_overlapping_tags():
    story = make_story("Textures workshop", sensory_tags=["tactile"])
    profile = make_profile(sensory_categories=["auditory", "visual"])
    assert score_story(story, profile, [], set()) == 0


# --- Interests bonus rule ---------------------------------------------------

def test_interest_bonus_is_case_insensitive_substring_match():
    story = make_story("Trains", interest_tags=["Train", "Dinosaur"])
    profile_matching = make_profile(interest="I love TRAINS and dinosaurs")
    profile_not_matching = make_profile(interest="I love football")

    assert score_story(story, profile_matching, [], set()) == 3
    assert score_story(story, profile_not_matching, [], set()) == 0


def test_interest_bonus_applies_once_even_with_multiple_matching_tags():
    story = make_story("Trains", interest_tags=["train", "railway"])
    profile = make_profile(interest="trains and railway are my favorite")
    assert score_story(story, profile, [], set()) == 3


# --- Rules combined across realistic, varied profiles -----------------------

def test_verbal_and_non_verbal_profiles_score_identically_on_shared_fields():
    # Communication style isn't a scoring input today -- this pins down that
    # both profile shapes flow through score_story without it skewing the
    # result, since only sensory/interest/history fields should matter.
    story = make_story("Sharing feelings", interest_tags=["music"])
    verbal_profile = make_profile(interest="music and singing", **{"communication-type": "verbal"})
    non_verbal_profile = make_profile(interest="music and singing", **{"communication-type": "non-verbal"})

    assert score_story(story, verbal_profile, [], set()) == score_story(story, non_verbal_profile, [], set())


def test_recommend_exercise_across_diverse_profiles_and_shared_story_pool():
    stories = [
        make_story("Loud events", sensory_tags=["auditory"], interest_tags=["music"]),
        make_story("Quiet routines", sensory_tags=[], interest_tags=["trains"]),
        make_story("New friends", sensory_tags=[], interest_tags=[]),
    ]

    # Non-verbal, auditory-sensitive, loves trains, no session history yet.
    profile_a = make_profile(
        sensory_categories=["auditory"], interest="trains, routines",
        **{"communication-type": "non-verbal"},
    )
    chosen_a = recommend_exercise(stories, profile_a, recent_themes=[], negative_emotion_themes=set())
    assert chosen_a["theme"] == "Quiet routines"

    # Verbal, no sensory sensitivities, loves music, already did "New friends" recently.
    profile_b = make_profile(interest="music", **{"communication-type": "verbal"})
    chosen_b = recommend_exercise(
        stories, profile_b, recent_themes=["New friends"], negative_emotion_themes=set()
    )
    assert chosen_b["theme"] == "Loud events"


def test_recent_repetition_and_emerging_difficulty_combine_additively():
    profile = make_profile(consolidated_profile={"emerging_difficulties": ["Sharing"]})
    story = make_story("Sharing")
    score = score_story(story, profile, recent_themes=["Sharing"], negative_emotion_themes=set())
    assert score == -10 + 5


def test_resolved_difficulties_do_not_affect_scoring():
    # Only emerging_difficulties should influence the score -- a theme the
    # child has already resolved shouldn't get the same priority bonus.
    profile_resolved = make_profile(
        consolidated_profile={"emerging_difficulties": [], "resolved_difficulties": ["Sharing"]}
    )
    story = make_story("Sharing")
    assert score_story(story, profile_resolved, [], set()) == 0


# --- Defensive: profiles/stories with missing optional fields ---------------

def test_score_story_handles_profile_missing_all_optional_fields():
    # A brand-new profile before any session/consolidation has ever run.
    bare_profile = {}
    story = make_story("Any theme")
    assert score_story(story, bare_profile, [], set()) == 0


def test_score_story_handles_story_missing_tag_fields():
    profile = make_profile(sensory_categories=["auditory"], interest="trains")
    bare_story = {"theme": "Bare theme"}
    assert score_story(bare_story, profile, [], set()) == 0
