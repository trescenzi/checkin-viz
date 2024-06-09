from models import (
    Checkins,
    Challenges,
    ChallengeWeeks,
    Challengers,
    ChallengerChallenges,
)
from peewee import *
import itertools
import os
import logging
LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level="INFO")
pwlogger = logging.getLogger("peewee")
pwlogger.addHandler(logging.StreamHandler())
pwlogger.setLevel(logging.DEBUG)

def score(tier, rule_set):
    if rule_set == 1:
        return version_1_score(tier)
    return version_2_score(tier)

def version_1_score(tier):
    match tier:
        case "T0":
            return 0
        case "T1":
            return 0
        case "T2":
            return 1
        case "T3":
            return 1.2
        case "T4":
            return 1.5
    return 1

def version_2_score(tier):
    if tier == "T0":
        return 0
    number = int(tier.lstrip("T"))
    points = 0.9+0.1*number
    logging.info("Tier: %s Number: %s Points: %s", tier, number, points)
    return points

def calculate_total_score(challenge_id):
    checkins_this_challenge = (
        Checkins.select(fn.Max(Checkins.tier), Checkins.name, Checkins.challenge_week, Challenges.rule_set)
        .join(ChallengeWeeks, on=((Checkins.challenge_week == ChallengeWeeks.id)))
        .where(ChallengeWeeks.challenge == challenge_id)
        .join(Challenges, on=((Challenges.id == ChallengeWeeks.challenge)))
        .where(Challenges.id == challenge_id)
        .group_by(fn.date(Checkins.time), Checkins.name, Checkins.challenge_week, Challenges.rule_set)
        .order_by(Checkins.challenge_week)
        .objects()
    )
    version = checkins_this_challenge[0].rule_set
    logging.info("Version: %s", version)
    nums = [
        {
            "name": n.name,
            "value": score(n.max, version),
            "week": n.challenge_week.id,
            "tier": n.max,
        }
        for n in checkins_this_challenge
    ]
    names = set(n["name"] for n in nums)
    weeks = [list(week) for w, week in itertools.groupby(nums, key=lambda x: x["week"])]
    num_weeks = len(list(weeks))
    result = {
        n: sum(
            round(
                sum(
                    sorted(
                        (name["value"] for name in week if name["name"] == n),
                        reverse=True,
                    )[:5]
                ),
                4,
            ) for week in weeks
        ) for n in names
    }
    logging.info("Total Points: %s", result)
    return result
