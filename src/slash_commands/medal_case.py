"""Private view of the invoking participant's current medals and personal best."""
import logging

from base_queries import challenger_by_discord_id, get_current_challenge_week
from medal_constants import NON_STEALABLE_MEDALS
from medal_roundup import describe_medal
import medals


def build_medal_case(held_medals, record, active_week=True):
    lines = ["## Your Medal Case", "", "**Currently held stealable medals**"]
    if not active_week:
        lines.append("There is no active challenge week right now.")
    elif held_medals:
        for medal in sorted(held_medals, key=lambda row: describe_medal(row.medal_name)):
            lines.append(f"- {medal.medal_emoji or ''} **{describe_medal(medal.medal_name)}**")
    else:
        lines.append("You aren't currently holding any stealable medals.")

    lines.extend(["", "**All-time personal record**"])
    if record is None:
        lines.append("No personal tier record yet. Submit your first check-in to set one!")
    else:
        day = record.record_date
        date_text = f"{day:%B} {day.day}, {day:%Y}"
        lines.append(f"🏆 **Highest Ever Personal Tier: {record.tier}** — {date_text}")
    return "\n".join(lines)


async def send_medal_case(ctx):
    await ctx.defer(ephemeral=True)
    try:
        challenger = challenger_by_discord_id(str(ctx.author.id))
        if challenger is None:
            await ctx.followup.send(
                "You aren't registered as a challenger yet, so you don't have a medal case.",
                ephemeral=True,
            )
            return

        week = get_current_challenge_week(challenger.tz)
        held = []
        if week is not None:
            # Determine the current holders before filtering to this user;
            # otherwise an old award stolen by someone else would still appear.
            standings = medals.get_current_week_medal_standings(week.challenge_id, week.id)
            held = [
                row for row in standings
                if row.medal_name not in NON_STEALABLE_MEDALS
                and str(row.discord_id) == str(ctx.author.id)
            ]
        record = medals.get_personal_tier_record(challenger.id)
        await ctx.followup.send(
            build_medal_case(held, record, active_week=week is not None),
            ephemeral=True,
        )
    except Exception:
        logging.exception("Failed to load medal case")
        await ctx.followup.send(
            "I couldn't load your medal case. Please try /medal-case again in a moment.",
            ephemeral=True,
        )
