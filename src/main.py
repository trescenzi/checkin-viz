import math
import requests
import os
import itertools
from datetime import datetime, timedelta, date
import json
from flask import Flask, render_template, request, url_for
import psycopg
from psycopg.rows import namedtuple_row
import logging
from models import (
    Checkins,
    Challenges,
    ChallengeWeeks,
    Challengers,
    ChallengerChallenges,
)
from peewee import *
import random
from rule_sets import calculate_total_score
from chart import checkin_chart, week_heat_map_from_checkins, write_og_image
import hashlib
from helpers import fetchall, fetchone, with_psycopg
import re
import pytz

connection_string = os.environ["DB_CONNECT_STRING"]
LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level=LOGLEVEL)
pwlogger = logging.getLogger("peewee")
pwlogger.addHandler(logging.StreamHandler())
pwlogger.setLevel(logging.DEBUG)


app = Flask(__name__)

logging.info(connection_string)


def get_challenges():
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            logging.debug("select * from challenges")
            cur.execute("select * from challenges")
            return cur.fetchall()


def points_so_far(challenge_id):
    sql = """
    SELECT SUM(count), name, tier 
    FROM (SELECT week, name, tier, LEAST(count, 5) as count FROM
      (SELECT 
        date_part('week', time) as week, name, cc.tier as tier,
        COUNT(distinct date_part('day', time)) as count
        FROM
        checkins c
        join challenger_challenges cc on 
            cc.challenger_id = c.challenger
        WHERE
        time >= (SELECT start FROM challenges WHERE id = %s)
        AND time <= (SELECT "end" FROM challenges WHERE id = %s)
        and cc.challenge_id = %s
        and (cc.knocked_out = FALSE AND cc.ante > 0)
        GROUP BY
        week, name, cc.tier
        ORDER BY
        week DESC, name, cc.tier
    ) as sub_query) group by name, tier order by tier;
    """
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (challenge_id, challenge_id, challenge_id))
            return cur.fetchall()


def total_ante(challenge_id, tier):
    sql = "select sum(ante) from challenger_challenges where challenge_id = %s and tier = %s"
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (challenge_id, tier))
            return cur.fetchone()[0]


def points_knocked_out(challenge_id):
    sql = """
    SELECT SUM(count), name, tier 
    FROM (SELECT week, name, tier, LEAST(count, 5) as count FROM
      (SELECT 
        date_part('week', time) as week, name, cc.tier as tier,
        COUNT(distinct date_part('day', time)) as count
        FROM
        checkins c
        join challenger_challenges cc on 
            cc.challenger_id = c.challenger
        WHERE
        time >= (SELECT start FROM challenges WHERE id = %s)
        AND time <= (SELECT "end" FROM challenges WHERE id = %s)
        and cc.challenge_id = %s
        and (cc.knocked_out = TRUE or cc.ante = 0)
        GROUP BY
        week, name, cc.tier
        ORDER BY
        week DESC, name, cc.tier
    ) as sub_query) group by name, tier;
    """
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (challenge_id, challenge_id, challenge_id))
            return cur.fetchall()


def challenge_data(challenge_id):
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from challenges where id = %s;" % challenge_id)
            return cur.fetchone()


@app.route("/details")
def details():
    challenge_id = request.args.get("challenge_id")
    challenge = challenge_data(challenge_id)
    logging.debug("Challenge ID: %s %s", challenge_id, challenge)
    weeksSinceStart = (
        min(
            math.ceil((date.today() - challenge[1]).days / 7),
            math.floor((challenge[2] - challenge[1]).days / 7),
        )
        - challenge[4]
    )
    logging.debug("Weeks since start: %s", weeksSinceStart)
    points = points_so_far(challenge_id)
    t3 = [x for x in points if x[2] == "T3"]
    t3 = sorted(t3, key=lambda x: -x[0])
    t2 = [x for x in points if x[2] == "T2"]
    t2 = sorted(t2, key=lambda x: -x[0])
    floating = [x for x in points if x[2] == "floating"]
    floating = sorted(floating, key=lambda x: -x[0])
    knocked_out = points_knocked_out(challenge_id)
    total_points_t2 = sum(x[0] for x in t2)
    total_points_t3 = sum(x[0] for x in t3)
    total_points_floating = sum(x[0] for x in floating)
    ante_floating = total_ante(challenge_id, "floating")
    ante_t2 = total_ante(challenge_id, "T2")
    ante_t3 = total_ante(challenge_id, "T3")
    dollars_per_point_floating = (
        ante_floating / total_points_floating if total_points_floating > 0 else 0
    )
    dollars_per_point_t2 = ante_t2 / total_points_t2 if total_points_t2 > 0 else 0
    dollars_per_point_t3 = ante_t3 / total_points_t3 if total_points_t3 > 0 else 0

    points = sorted(points, key=lambda x: -x[0])
    logging.debug("points: %s", points)
    challenges = get_challenges()
    return render_template(
        "details.html",
        t2=t2,
        t3=t3,
        floating=floating,
        total_points_t2=total_points_t2,
        dollars_per_point_t2=dollars_per_point_t2,
        total_ante_t2=int(dollars_per_point_t2 * total_points_t2),
        total_points_t3=total_points_t3,
        dollars_per_point_t3=dollars_per_point_t3,
        total_ante_t3=int(dollars_per_point_t3 * total_points_t3),
        total_points_floating=total_points_floating,
        dollars_per_point_floating=dollars_per_point_floating,
        total_ante_floating=int(dollars_per_point_floating * total_points_floating),
        challenge=challenge,
        knocked_out=knocked_out,
        weeks=weeksSinceStart,
        challenges=[c for c in challenges if c[3] not in set([1, challenge_id])],
    )


def challenge_weeks():
    challenges = (
        Challenges.select(Challenges.name, ChallengeWeeks.id, ChallengeWeeks.start)
        .join(ChallengeWeeks)
        .order_by(ChallengeWeeks.start)
    )
    return [
        list(value)
        for n, value in itertools.groupby(challenges.tuples(), key=lambda x: x[0])
    ]


def get_current_challenge_week():
    now = datetime.now()
    current_year = int(now.strftime("%Y"))
    current_week = int(now.strftime("%W"))
    challenge_week_predicate = (ChallengeWeeks.start.year == current_year) & (
        ChallengeWeeks.week_of_year == current_week
    )
    current_challenge_week = (
        ChallengeWeeks.select().where(challenge_week_predicate).get()
    )
    return current_challenge_week


def checkins_this_week(challenge_week_id):
    sql = """
    select name, day_of_week, tier, time at time zone 'America/New_York' as time from checkins c
    join challenge_weeks cw on cw.id = c.challenge_week_id
    where cw.id = %s
    """
    return fetchall(sql, [challenge_week_id])


@app.route("/")
def index():
    challenge_name = request.args.get("challenge")
    logging.debug("Challenge requested: %s", challenge_name)
    week_id = request.args.get("challenge_week_%s" % challenge_name)
    logging.debug("Week requested: %s", week_id)
    now = datetime.now()
    current_year = int(now.strftime("%Y"))
    current_week = int(now.strftime("%W"))
    current_date = date.today().isoformat()

    current_challenge = None
    if challenge_name is None:
        logging.debug(
            "Getting challenge for current week dates: %s %s %s",
            current_year,
            current_week,
            current_date,
        )
        current_challenge = (
            Challenges.select()
            .where(
                (Challenges.start <= current_date) & (Challenges.end >= current_date)
            )
            .get()
        )
    else:
        logging.debug("Getting challenge with name: %s", challenge_name)
        current_challenge = (
            Challenges.select().where(Challenges.name == challenge_name).get()
        )

    logging.debug("Current challenge: %s", current_challenge)
    current_challenge_week = get_current_challenge_week()
    logging.debug("Current challenge week: %s", current_challenge_week)

    checkin_predicate = (Checkins.time >= ChallengeWeeks.start) & (
        Checkins.time < fn.date_add(ChallengeWeeks.end, "1 day")
    )
    if week_id is None:
        week_id = current_challenge_week.id

    total_points = calculate_total_score(current_challenge.id)

    logging.debug("Austin points: %s", total_points)

    selected_challenge_week = ChallengeWeeks.get(id=week_id)
    logging.debug(
        "Selected challenge week: %s is green: %s",
        selected_challenge_week,
        selected_challenge_week.green,
    )

    checkins = checkins_this_week(week_id)
    logging.debug("Week checkins: %s", [checkin.name for checkin in checkins])
    week, latest, achievements = week_heat_map_from_checkins(
        checkins,
        current_challenge.id,
        current_challenge.rule_set,
    )
    week = sorted(
        week, key=lambda x: -total_points[x.name] if x.name in total_points else 0
    )
    logging.debug("WEEK: %s, LATEST: %s", week, latest)
    chart = checkin_chart(
        week,
        800,
        600,
        current_challenge.id,
        selected_challenge_week.green,
        selected_challenge_week.bye_week,
        total_points,
        achievements,
    )
    write_og_image(chart, week_id)
    og_path = url_for("static", filename="preview-" + str(week_id) + ".png")
    logging.debug("Challenge ID: %s", current_challenge.id)
    cws = challenge_weeks()
    logging.debug("Weeks: %s", cws)
    current_challenge_weeks = next(v for v in cws if v[0][0] == current_challenge.name)
    logging.debug("Current week index: %s", current_challenge_weeks)
    week_index = (
        next(i for i, v in enumerate(current_challenge_weeks) if v[1] == int(week_id))
        + 1
    )
    logging.debug("Week Index: %s, Week ID: %s", week_index, week_id)
    return render_template(
        "index.html",
        svg=chart,
        latest=latest,
        week=int(current_week),
        year=current_year,
        challenge_id=current_challenge.id,
        og_path=og_path,
        challenge_weeks=cws,
        current_challenge=current_challenge.name,
        current_week_index=week_index,
        current_week_start=current_challenge_weeks[week_index - 1][2].strftime("%m/%d"),
        current_week=current_week,
        viewing_this_week=challenge_name == request.args.get("challenge") == None,
        green=selected_challenge_week.green,
    )


@app.route("/make-it-green")
def make_it_green():
    green = random.randint(1, 100) < 21
    logging.debug("is is green %s", green)
    challenge_week = get_current_challenge_week()
    if challenge_week.green is None:
        challenge_week.green = green
        challenge_week.save()
    return render_template("green.html", green=green)


@app.route("/magic")
def magic():
    return render_template("magic.html")


@app.route("/challenger/<challenger>")
def challenger(challenger):
    c = Challengers.get(Challengers.name == challenger)
    logging.debug("Challenger: %s", c.name)
    return render_template("challenger.html", name=challenger, bmr=c.bmr)


@app.route("/calc")
def calc():
    name = request.args.get("name")
    challengers = Challengers.select().where(Challengers.bmr != None).objects()
    return render_template("calc.html", challengers=challengers, name=name)


@app.route("/add-checkin", methods=["GET", "POST"])
def add_checkin():
    logging.debug("Add checkin")
    name = request.form["name"]
    tier = request.form["tier"]
    time = datetime.fromisoformat(request.form["time"])
    day_of_week = time.strftime("%A")
    challenger = Challengers.select().where(Challengers.name == name).get()
    challenge_week = ChallengeWeeks.challenge_week_during(time)
    logging.debug(
        "Add checkin: %s",
        {
            "name": name,
            "tier": tier,
            "time": time,
            "day_of_week": day_of_week,
            "challenger": challenger.id,
            "challenge_week": challenge_week.id,
        },
    )
    checkin = Checkins.create(
        name=name,
        time=time,
        day_of_week=day_of_week,
        challenger=challenger,
        tier=("T%s" % tier),
        text=("%s checkin via magic" % tier),
        challenge_week=challenge_week,
    )
    logging.debug("Addind checkin: %s", checkin)
    return render_template("magic.html")


def is_checkin(message):
    body = message.lower()
    matches = (
        re.match(".*((t\\d+)?.?(check.?in.?|✅)|(check.?in.?|✅)(t\\d+)?).*", body)
        is not None
    )
    return (
        matches
        and "liked" not in body
        and "emphasized" not in body
        and "loved" not in body
        and "laughed" not in body
        and 'to "' not in body
        and "to “" not in body
    )


def get_tier(message):
    match = re.match(".*(t\\d+).*", message.lower())
    if match is not None:
        return match.group(1).upper()
    return "unknown"


def insert_checkin(message, tier, challenger, week_id):
    tz = pytz.timezone(challenger.tz)
    now = datetime.now(tz=tz)
    logging.info("now %s", now)

    def fn(conn, cur):
        cur.execute(
            "INSERT INTO checkins (name, time, tier, day_of_week, text, challenge_week_id, challenger) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (
                challenger.name,
                now,
                tier,
                now.strftime("%A"),
                message,
                week_id,
                challenger.id,
            ),
        )

    return fn


@app.route("/mail", methods=["POST"])
def mail():
    fromaddress = request.json["from"]["text"]
    logging.debug("weve got mail from %s", fromaddress)

    sessionmta = request.json["session"]["mta"]
    if sessionmta != "mx1.forwardemail.net" and sessionmta != "mx2.forwardemail.net":
        logging.error("not from mx1/2, %s", sessionmta)
        return "1", 200

    attachments = request.json["attachments"]
    first_text_plain = next(
        (
            attachment
            for attachment in attachments
            if attachment["contentType"] == "text/plain"
        ),
        None,
    )
    if first_text_plain is None:
        return "not_text", 200

    content = first_text_plain["content"]
    checksum = first_text_plain["checksum"]

    if content["type"] != "Buffer":
        logging.error("non buffer data %s", content["type"])
        return "2", 200

    bdata = bytearray(content["data"])
    md5 = hashlib.md5()
    md5.update(bdata)
    buffer_checksum = md5.hexdigest()

    if checksum != buffer_checksum:
        logging.error("checksum mismatch %s %s", buffer_checksum, checksum)
        return "3", 200

    number, domain = fromaddress.split("@")
    challenger = fetchone(
        "select * from challengers where phone_number = %s and email_domain = %s",
        (number, domain),
    )
    challenge_week_id = fetchone(
        "select id from challenge_weeks where start <= CURRENT_DATE at time zone 'America/New_York' and \"end\" >= CURRENT_DATE at time zone 'America/New_York';",
        (),
    ).id

    logging.info("challenger %s", challenger)
    logging.info("challenge week %s", challenge_week_id)
    message = bdata.decode("utf-8")

    logging.info("content %s", message)

    if not is_checkin(message):
        logging.info("not checkin")
        return "4", 200

    tier = get_tier(message)

    logging.info("tier %s", tier)

    if tier == "unknown":
        logging.info("unknown tier")
        return "5", 200

    with_psycopg(insert_checkin(message, tier, challenger, challenge_week_id))

    return "success", 200


if __name__ == "__main__":
    app.run(debug=True)
