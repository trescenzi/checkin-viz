from helpers import fetchone, fetchall
from datetime import datetime, timedelta, date
import itertools


def points_so_far(challenge_id):
    return fetchall("select * from get_challenge_score(%s, FALSE)", [challenge_id])


def get_challenges():
    return fetchall("select * from challenges")


def bi_checkins(challenge_id):
    sql = "select sum(bi_checkins) from challenger_challenges where challenge_id = %s"
    return fetchone(sql, [challenge_id]).sum


def points_knocked_out(challenge_id):
    return fetchall("select * from get_challenge_score(%s, TRUE)", [challenge_id])


def challenge_data(challenge_id):
    return fetchone("select * from challenges where id = %s;", [challenge_id])


def total_ante(challenge_id, tier):
    return fetchone(
        "select sum(ante) from challenger_challenges where challenge_id = %s and tier = %s",
        (challenge_id, tier),
    ).sum


def total_possible_checkins_so_far(challenge_id, week_id):
    sql = "select count(*) * 5 as total_possible from challenge_weeks where challenge_id = %s and id < %s;"
    checkins_possible_before_now = fetchone(sql, (challenge_id, week_id))[0]
    now = datetime.now()
    day_of_week = now.weekday()
    return checkins_possible_before_now + min(day_of_week + 1, 5)


def total_possible_checkins(challenge_id):
    sql = "select count(*) * 5 as total_possible from challenge_weeks where challenge_id = %s;"
    return fetchone(sql, [challenge_id])


def challenge_weeks():
    sql = """
        select c.name, cw.id, cw.start from challenge_weeks cw
        join challenges c on cw.challenge_id = c.id
        order by cw.start
        """
    challenges = fetchall(sql, [])
    return [
        list(value) for n, value in itertools.groupby(challenges, key=lambda x: x.name)
    ]


def get_current_challenge_week(tz="America/New_York"):
    sql = """
        select * from challenge_weeks 
        where 
            week_of_year = extract(week from current_timestamp at time zone %s) and
            extract(year from start) = extract(year from current_date)
        """
    return fetchone(sql, [tz])


def get_current_challenge():
    return fetchone(
        'select * from challenges where start <= CURRENT_DATE and "end" >= CURRENT_DATE'
    )


def checkins_this_week(challenge_week_id):
    sql = """
    select
      ch.name, checkins.day_of_week, c.tier, c.time at time zone ch.tz as time, cw.bye_week
    from
      (select day_of_week, max(ltrim(tier, 'T')::INT) as max_tier, challenger
       from checkins
       where challenge_week_id = %s
       group by day_of_week, challenger) as checkins
    join
      checkins c on c.day_of_week = checkins.day_of_week and ltrim(c.tier, 'T')::INT = checkins.max_tier
    join
      challenge_weeks cw on cw.id = c.challenge_week_id
    join
      challengers ch on ch.id = c.challenger
    where cw.id = %s
    group by ch.name, checkins.day_of_week, c.tier, c.time, cw.bye_week, ch.tz
    order by day_of_week, time desc;
    """
    return fetchall(sql, (challenge_week_id, challenge_week_id))
