from helpers import fetchall, with_psycopg
from base_queries import insert_checkin
import datetime
import logging
import pytz
from typing import List, Dict, NamedTuple


class Challenger(NamedTuple):
    id: int
    name: str
    tz: str


class ChallengeWeek(NamedTuple):
    id: int
    challenge_id: str
    week_of_year: str


def find_date(week, day):
    current_year = datetime.datetime.now().year
    days = {
        "Sunday": 0,
        "Monday": 1,
        "Tuesday": 2,
        "Wednesday": 3,
        "Thursday": 4,
        "Friday": 5,
        "Saturday": 6,
    }
    day = days[day]
    date = datetime.datetime.strptime(f"{current_year} {week} {day}", "%Y %W %w").date()
    return datetime.datetime(date.year, date.month, date.day, 12)


def last_week_mulligan_table():
    last_week_id_sql = """
    select id from challenge_weeks 
    where 
        week_of_year = extract(week from current_timestamp - INTERVAL '1 day') and
        extract(year from start) = extract(year from current_date)
    """
    sql = (
        """
    select 
        c.name,
        count(*),
        cw.green,
        cw.id as cwid
    from checkins c 
    join challenge_weeks cw ON cw.id = c.challenge_week_id
    where 
        c.challenge_week_id = (%s) 
        and tier != 'T0'
    group by c.name, cw.green, cwid;
    """
        % last_week_id_sql
    )

    return fetchall(sql)


def check_last_week_for_mulligan_necessity():
    last_week_checkins = last_week_mulligan_table()

    return last_week_checkins


days_of_week = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def insert_mulligan_for(name, challenge_week_id):
    checkin_sql = """
        select 
            distinct day_of_week,
            challenger,
            tz,
            challenge_weeks.week_of_year,
            challenge_weeks.id,
            challenge_weeks.challenge_id,
            time
        from checkins
        join challenge_weeks ON challenge_weeks.id = checkins.challenge_week_id 
        where name = %s and challenge_week_id = %s
    """

    checkins = fetchall(checkin_sql, (name, challenge_week_id))

    challenger = Challenger(checkins[0].challenger, name, checkins[0].tz)
    challenge_week = ChallengeWeek(
        checkins[0].id, checkins[0].challenge_id, checkins[0].week_of_year
    )
    logging.info("challenger %s", challenger)
    logging.info("challenge_week %s", challenge_week)

    checkedin_days = [checkin.day_of_week for checkin in checkins]
    logging.info("days checked in %s", checkedin_days)

    days_not_checked_in = [
        day_of_week for day_of_week in days_of_week if day_of_week not in checkedin_days
    ]
    logging.info("days not checked in %s", days_not_checked_in)

    day_to_insert = days_not_checked_in[0]
    week_of_year = checkins[0].week_of_year
    logging.info("inserting checkin for %s", find_date(week_of_year, day_to_insert))
    time = find_date(week_of_year, day_to_insert)

    def insert_checkin_and_associate_mulligan(conn, cur):
        m = insert_checkin(
            "MULLIGAN T1 checkin",
            "T1",
            challenger,
            checkins[0].id,
            day_to_insert,
            time,
        )(conn, cur)
        logging.debug("mulligan: %s, challenger: %s", m, challenger.id)
        cur.execute(
            "update challenger_challenges set mulligan = %s where challenger_id = %s and challenge_id = %s",
            [m, challenger.id, challenge_week.challenge_id],
        )

    with_psycopg(insert_checkin_and_associate_mulligan)
