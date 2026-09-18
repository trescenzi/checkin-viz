"""Shared persistence and medal feedback for typed and calculator check-ins."""
from dataclasses import dataclass
from collections import defaultdict
import logging

from base_queries import challenger_by_discord_id, get_current_challenge_week, insert_checkin
from helpers import fetchone, with_psycopg
import medals
import medal_log
from medal_roundup import should_suppress_medal_announcements, describe_medal


@dataclass(frozen=True)
class SavedCheckin:
    checkin_id: int
    week: object


def save_checkin(text, tier, discord_id, require_active_member=False):
    challenger = challenger_by_discord_id(str(discord_id))
    if challenger is None:
        raise ValueError("You need to register as a challenger before checking in.")
    week = get_current_challenge_week(challenger.tz)
    if week is None:
        raise ValueError("There is no active challenge week to check into.")
    if require_active_member and not fetchone(
        "select challenger_id from challenger_challenges where challenge_id = %s and challenger_id = %s",
        [week.challenge_id, challenger.id],
    ):
        raise ValueError("You need to join the current challenge before checking in.")
    checkin_id = with_psycopg(insert_checkin(text, tier, challenger, week.id))
    return SavedCheckin(checkin_id, week)


async def send_checkin_feedback(message, tier, saved):
    """Message author is irrelevant: medal ownership comes from the saved record."""
    await message.add_reaction("✅")
    if int(tier[1:]) > 10:
        await message.add_reaction("🔥")
    medals.update_medal_table(saved.week.challenge_id, saved.week.id)
    log = medal_log.get_medal_log(saved.week.id)
    logging.info("DISCORD: medal log %s", log)

    relevant_medals = [medal for medal in log if medal.checkin_id == saved.checkin_id]
    if relevant_medals:
        logging.info("DISCORD: medals for checkin %s", relevant_medals)

        # Add reactions for all medals
        for medal in relevant_medals:
            await message.add_reaction(medal.medal_emoji)

        # Suppress replies until after Opening Medal Roundup on challenge day 2.
        if should_suppress_medal_announcements(saved.week.start):
            logging.info(
                "DISCORD: skipping medal reply before opening roundup window ends"
            )
            return

        # Group medals by user, action type, and (for steals) the person they stole from
        grouped_medals = defaultdict(list)

        for medal in relevant_medals:
            nice_name = describe_medal(medal.medal_name)
            emoji = medal.medal_emoji or ""
            medal_display = f"{emoji} __**{nice_name}**__".strip()

            # Check if this medal was stolen (has a previous holder)
            if medal.stolen_checkin_challenger_name and medal.stolen_discord_id is not None:
                if medal.discord_id == medal.stolen_discord_id:
                    # Special case: still holds and surpassed their own record
                    key = (medal.discord_id, "still_holds", None)
                else:
                    # Stolen from someone else
                    key = (medal.discord_id, "stole", medal.stolen_discord_id)
            else:
                # Earned (no previous holder or invalid steal data)
                key = (medal.discord_id, "earned", None)

            grouped_medals[key].append(medal_display)

        # Format grouped messages
        # Sort so earned messages come before stolen/still_holds messages
        def sort_key(item):
            (discord_id, action_type, stolen_discord_id), medal_list = item
            # Return 0 for "earned", 1 for others to ensure earned comes first
            return (0 if action_type == "earned" else 1, discord_id, action_type, stolen_discord_id or "")

        medal_message = ""
        for (discord_id, action_type, stolen_discord_id), medal_list in sorted(grouped_medals.items(), key=sort_key):
            # Format medal list with commas and "and"
            if len(medal_list) == 1:
                medals_text = medal_list[0]
            elif len(medal_list) == 2:
                medals_text = f"{medal_list[0]} and {medal_list[1]}"
            else:
                medals_text = ", ".join(medal_list[:-1]) + f", and {medal_list[-1]}"

            if action_type == "still_holds":
                pronoun = "them" if len(medal_list) > 1 else "it"
                medal_message += (
                    f"\n\n<@{discord_id}> still holds {medals_text}, and has now surpassed {pronoun}!"
                )
            elif action_type == "stole":
                # Validate stolen_discord_id to prevent invalid mentions
                if stolen_discord_id is not None:
                    medal_message += (
                        f"\n\n<@{discord_id}> stole {medals_text} from <@{stolen_discord_id}>!"
                    )
                else:
                    # Fallback if stolen_discord_id is None (shouldn't happen, but safety check)
                    logging.warning(f"stolen_discord_id is None for steal action by {discord_id}")
                    medal_message += (
                        f"\n\n<@{discord_id}> stole {medals_text}!"
                    )
            else:  # earned
                medal_message += (
                    f"\n\n<@{discord_id}> earned {medals_text}!"
                )

        logging.info("DISCORD: %s", medal_message)
        await message.reply(medal_message)
