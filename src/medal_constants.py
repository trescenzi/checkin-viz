# Shared medal display/constants with no DB dependencies.

NON_STEALABLE_MEDALS = frozenset(
    {"green", "red", "diamond", "gold", "first_to_green", "all_gold", "all_green"}
)

CHALLENGE_SCOPED_MEDALS = frozenset(
    {
        "highest_tier_challenge",
        "earliest_for_challenge",
        "latest_for_challenge",
        "all_gold",
        "all_green",
    }
)

nice_medal_names = {
    "highest_tier_challenge": "Highest Overall Tier",
    "highest_tier_week": "Highest Weekly Tier",
    "gold": "Gold Week",
    "all_gold": "All Gold",
    "first_to_green": "First to Green",
    "green": "Green Week",
    "red": "Red Week",
    "diamond": "Diamond Week",
    "all_green": "All Green",
    "earliest_for_week": "Earliest Weekly Check-in",
    "latest_for_week": "Latest Weekly Check-in",
    "earliest_for_challenge": "Earliest Overall Check-in",
    "latest_for_challenge": "Latest Overall Check-in",
}
