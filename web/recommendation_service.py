RECENT_THEME_WINDOW = 3
NEGATIVE_EMOTIONS = {"sad", "ashamed", "angry", "scared", "disgusted"}

# On a day the child checks in with a negative emotion, how many past
# sessions on a theme count as "familiar enough" to lean on today, rather
# than introducing something new. A display/product tuning choice.
FAMILIAR_THEME_COUNT = 3


def score_story(story, user_profile, recent_themes, negative_emotion_themes, theme_counts=None, today_emotion=None):
    score = 0
    theme = story.get("theme")
    theme_counts = theme_counts or {}

    # 1. Avoid recent repetition
    if theme in recent_themes:
        score -= 10

    # 2. Prioritize emerging difficulties
    consolidated = user_profile.get("consolidated_profile") or {}
    emerging = consolidated.get("emerging_difficulties", [])
    if theme in emerging:
        score += 5

    # 3. Éviter les conflits avec les sensibilités sensorielles déclarées
    # Avoid conflicts with sensory sensibilities
    story_sensory_tags = set(story.get("sensory_tags", []))
    profile_sensory = set(user_profile.get("sensory_categories", []))
    conflict_count = len(story_sensory_tags & profile_sensory)
    score -= conflict_count * 4

    # 4. Add a bonus if there is a corresponding interest
    interests_text = (user_profile.get("interest") or "").lower()
    interest_tags = story.get("interest_tags", [])
    if any(tag.lower() in interests_text for tag in interest_tags):
        score += 3

    # 5. If associated with a negative emotion, we add a malus
    if theme in negative_emotion_themes:
        score -= 2

    # 6. If the child checked in with a negative emotion today, don't pile a
    # brand-new theme on top of a hard day -- lean towards something familiar.
    if today_emotion in NEGATIVE_EMOTIONS:
        count = theme_counts.get(theme, 0)
        if count == 0:
            score -= 6
        elif count >= FAMILIAR_THEME_COUNT:
            score += 3

    return score


def recommend_exercise(all_stories, user_profile, recent_themes, negative_emotion_themes, theme_counts=None, today_emotion=None):
    if not all_stories:
        return None
    scored = [
        (score_story(s, user_profile, recent_themes, negative_emotion_themes, theme_counts, today_emotion), s)
        for s in all_stories
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]