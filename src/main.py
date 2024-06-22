import math
import requests
import os
import itertools
from datetime import datetime, timedelta, date
import json
from flask import Flask, render_template, request, url_for
import psycopg
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

connection_string = os.environ["DB_CONNECT_STRING"]
LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level="INFO")
pwlogger = logging.getLogger("peewee")
pwlogger.addHandler(logging.StreamHandler())
pwlogger.setLevel(logging.DEBUG)


app = Flask(__name__)

logging.info(connection_string)


def get_challenges():
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            logging.info("select * from challenges")
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
    logging.info("Challenge ID: %s %s", challenge_id, challenge)
    weeksSinceStart = (
        min(
            math.ceil((date.today() - challenge[1]).days / 7),
            math.floor((challenge[2] - challenge[1]).days / 7),
        )
        - challenge[4]
    )
    logging.info("Weeks since start: %s", weeksSinceStart)
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
    logging.info("points: %s", points)
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


@app.route("/")
def index():
    challenge_name = request.args.get("challenge")
    logging.info("Challenge requested: %s", challenge_name)
    week_id = request.args.get("challenge_week_%s" % challenge_name)
    logging.info("Week requested: %s", week_id)
    now = datetime.now()
    current_year = int(now.strftime("%Y"))
    current_week = int(now.strftime("%W"))
    current_date = date.today().isoformat()

    current_challenge = None
    if challenge_name is None:
        logging.info(
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
        logging.info("Getting challenge with name: %s", challenge_name)
        current_challenge = (
            Challenges.select().where(Challenges.name == challenge_name).get()
        )

    logging.info("Current challenge: %s", current_challenge)
    current_challenge_week = get_current_challenge_week()
    logging.info("Current challenge week: %s", current_challenge_week)

    checkin_predicate = (Checkins.time >= ChallengeWeeks.start) & (
        Checkins.time < fn.date_add(ChallengeWeeks.end, "1 day")
    )
    if week_id is None:
        week_id = current_challenge_week.id

    total_points = calculate_total_score(current_challenge.id)

    logging.info("Austin points: %s", total_points)

    selected_challenge_week = ChallengeWeeks.get(id=week_id)
    logging.info(
        "Selected challenge week: %s is green: %s",
        selected_challenge_week,
        selected_challenge_week.green,
    )

    checkins = (
        Checkins.select()
        .join(ChallengeWeeks, on=(checkin_predicate))
        .where(ChallengeWeeks.id == week_id)
    )

    logging.info("Week checkins: %s", [checkin.name for checkin in checkins.objects()])
    week, latest, achievements = week_heat_map_from_checkins(
        [checkin for checkin in checkins.objects()],
        current_challenge.id,
        current_challenge.rule_set,
    )
    week = sorted(
        week, key=lambda x: -total_points[x.name] if x.name in total_points else 0
    )
    logging.info("WEEK: %s, LATEST: %s", week, latest)
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
    logging.info("Challenge ID: %s", current_challenge.id)
    cws = challenge_weeks()
    logging.info("Weeks: %s", cws)
    current_challenge_weeks = next(v for v in cws if v[0][0] == current_challenge.name)
    logging.info("Current week index: %s", current_challenge_weeks)
    week_index = (
        next(i for i, v in enumerate(current_challenge_weeks) if v[1] == int(week_id))
        + 1
    )
    logging.info("Week Index: %s, Week ID: %s", week_index, week_id)
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
    logging.info("is is green %s", green)
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
    logging.info("Challenger: %s", c.name)
    return render_template("challenger.html", name=challenger, bmr=c.bmr)


@app.route("/calc")
def calc():
    name = request.args.get("name")
    challengers = Challengers.select().where(Challengers.bmr != None).objects()
    return render_template("calc.html", challengers=challengers, name=name)


@app.route("/add-checkin", methods=["GET", "POST"])
def add_checkin():
    logging.info("Add checkin")
    name = request.form["name"]
    tier = request.form["tier"]
    time = datetime.fromisoformat(request.form["time"])
    day_of_week = time.strftime("%A")
    challenger = Challengers.select().where(Challengers.name == name).get()
    challenge_week = ChallengeWeeks.challenge_week_during(time)
    logging.info(
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
    logging.info("Addind checkin: %s", checkin)
    return render_template("magic.html")


if __name__ == "__main__":
    app.run(debug=True)
