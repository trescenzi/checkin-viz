from huey import crontab, SqliteHuey
from green import determine_if_green
from mulligan import check_last_week_for_mulligan_necessity, insert_mulligan_for
import logging

# --- Existing tasks config ---
logging.basicConfig(level="DEBUG")
huey = SqliteHuey()

@huey.task()
def example_task(n):
    print("-- RUNNING EXAMPLE TASK: CALLED WITH n=%s --" % n)
    return n

@huey.periodic_task(crontab(hour="8", day="1"))
def is_green_week():
    print("Determining if green")
    determine_if_green()

@huey.periodic_task(crontab(hour="8", day="1"))
def check_mulligans():
    logging.info("checking for mulligans")
    last_week_checkins = check_last_week_for_mulligan_necessity()
    logging.info("last week: %s" % last_week_checkins)

    is_green_week = last_week_checkins[0].green

    needing_of_mulligan = [
        (x.name, x.cwid)
        for x in last_week_checkins
        if x.count < 5 and is_green_week or x.count < 2
    ]
    logging.info("needs a mulligan: %s" % needing_of_mulligan)
    for name, cwid in needing_of_mulligan:
        insert_mulligan_for(name, cwid)

# --- New Discord Results Broadcast Task Begins Here ---

import os
from datetime import datetime, timedelta
import pytz

from base_queries import get_challenges, challenge_data, points_so_far, challenge_weeks
from medals import *
import medal_log
from helpers import fetchone, fetchall

from src.bot import bot

def get_challenge_that_ended_yesterday():
    """
    Returns the challenge (dict-like row) that ended yesterday in America/New_York, or None if none.
    """
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    yesterday = now - timedelta(days=1)
    for challenge in get_challenges():
        end_date = challenge.end if hasattr(challenge, "end") else challenge["end"]
        end_val = end_date.date() if isinstance(end_date, datetime) else end_date
        if end_val == yesterday.date():
            return challenge
    return None

def get_last_challenge_week_id(challenge_id):
    cw = fetchall(
        'SELECT id FROM challenge_weeks WHERE challenge_id = %s ORDER BY "end" DESC LIMIT 1',
        [challenge_id],
    )
    return cw[0].id if cw else None

def format_discord_mention(discord_id):
    return f"<@{discord_id}>"

def get_podium(challenge_id):
    scoring = points_so_far(challenge_id)
    sorted_scores = sorted(scoring, key=lambda s: -s.points)
    return sorted_scores[:3]

def collect_achievement_tags(medal_log_records, kind):
    return list({m.discord_id for m in medal_log_records if m.medal_name == kind})

def collect_achievement_tags_multiple(medal_log_records, kind):
    d = {}
    for m in medal_log_records:
        if m.medal_name == kind:
            d[m.discord_id] = d.get(m.discord_id, 0) + 1
    return d

def render_achievement_line(emote, label, discord_dict):
    if not discord_dict:
        return ""
    tags = []
    for discord_id, count in discord_dict.items():
        tag = format_discord_mention(discord_id)
        if count > 1:
            tag += f" (x{count})"
        tags.append(tag)
    return f"{emote} **{label}:** {', '.join(tags)}"

def compose_results_message(challenge, podium, achievements):
    msg = f"# {challenge.name} Results! 🏁\n\n"
    msg += "### Podium\n"
    places = ["🥇 **1st Place:**", "🥈 **2nd Place:**", "🥉 **3rd Place:**"]
    for idx, person in enumerate(podium):
        if idx >= len(places): break
        msg += f"{places[idx]} {format_discord_mention(person.discord_id)} with {person.points} points\n"
    msg += "\n### Achievements\n"
    for line in achievements:
        if line:
            msg += f"{line}\n"
    msg += "\n@everyone"
    return msg

def gather_achievements(challenge_id, challenge_week_id):
    mlog = medal_log.get_medal_log(challenge_week_id)
    lines = []
    medal_defs = [
        ("🌟", "Club 60", "club_60"),
        ("⭐", "Club 50", "club_50"),
        ("🏋️", "Highest Overall Tier", "highest_tier_challenge"),
        ("💪", "Highest Weekly Tier", "highest_tier_week"),
        ("🏅", "Gold Week", "gold"),
        ("❇", "First to Green", "first_to_green"),
        ("🟩", "Green Week", "green"),
        ("🌞", "Earliest Check-in", "earliest_for_week"),
        ("🌚", "Latest Check-in", "latest_for_week"),
    ]
    for emote, label, db_label in medal_defs:
        if db_label in ("club_60", "club_50"):
            scores = points_so_far(challenge_id)
            point_cut = 60 if db_label == "club_60" else 50
            ids = [s.discord_id for s in scores if s.points >= point_cut]
            if ids:
                lines.append(f"{emote} **{label}:** {', '.join(format_discord_mention(i) for i in ids)}")
            continue
        elif db_label in ("highest_tier_challenge", "highest_tier_week", "gold", "first_to_green", "green"):
            multi = collect_achievement_tags_multiple(mlog, db_label)
            lines.append(render_achievement_line(emote, label, multi))
        elif db_label in ("earliest_for_week", "latest_for_week"):
            multi = collect_achievement_tags_multiple(mlog, db_label)
            lines.append(render_achievement_line(emote, label, multi))
    return lines

@huey.periodic_task(crontab(minute="0", hour="14"))  # 9am ET (14 UTC)
def broadcast_discord_challenge_results():
    chan_id = os.getenv("DISCORD_RESULTS_CHANNEL_ID")
    if not chan_id:
        logging.error("DISCORD_RESULTS_CHANNEL_ID environment variable is required for automated results broadcasts.")
        return
    challenge = get_challenge_that_ended_yesterday()
    if not challenge:
        return
    challenge_week_id = get_last_challenge_week_id(challenge.id)
    if not challenge_week_id:
        logging.error(f"Could not find last week of challenge {challenge.name}")
        return
    podium = get_podium(challenge.id)
    ach_lines = gather_achievements(challenge.id, challenge_week_id)
    msg = compose_results_message(challenge, podium, ach_lines)
    bot.loop.create_task(_post_discord_message(int(chan_id), msg))

async def _post_discord_message(channel_id, msg):
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            logging.error(f"Could not find Discord channel ID {channel_id}")
            return
        await channel.send(msg)
    except Exception as e:
        logging.exception(f"Error sending results message to Discord: {e}")
