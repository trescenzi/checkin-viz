import math
import requests
import os
import itertools
from datetime import datetime, timedelta, date
import json
from flask import Flask, render_template, request, url_for, redirect
import psycopg
from psycopg.rows import namedtuple_row
import logging
import random
from rule_sets import calculate_total_score
from chart import checkin_chart, week_heat_map_from_checkins, write_og_image
import hashlib
from helpers import fetchall, fetchone, with_psycopg
import re
import pytz
from twilio_decorator import twilio_request
from cache_decorator import last_modified

connection_string = os.environ["DB_CONNECT_STRING"]
LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level="DEBUG")

app = Flask(__name__)


def get_challenges():
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            logging.debug("select * from challenges")
            cur.execute("select * from challenges")
            return cur.fetchall()


def points_so_far(challenge_id):
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from get_challenge_score(%s, FALSE)", [challenge_id])
            return cur.fetchall()


def total_ante(challenge_id, tier):
    sql = "select sum(ante) from challenger_challenges where challenge_id = %s and tier = %s"
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (challenge_id, tier))
            return cur.fetchone()[0]


def bi_checkins(challenge_id):
    sql = "select sum(bi_checkins) from challenger_challenges where challenge_id = %s"
    return fetchone(sql, [challenge_id]).sum


def points_knocked_out(challenge_id):
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from get_challenge_score(%s, TRUE)", [challenge_id])
            return cur.fetchall()


def challenge_data(challenge_id):
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from challenges where id = %s;" % challenge_id)
            return cur.fetchone()


def total_possible_checkins(challenge_id):
    sql = "select count(*) * 5 as total_possible from challenge_weeks where challenge_id = %s;"
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(sql % challenge_id)
            return cur.fetchone()

def total_possible_checkins_so_far(challenge_id, week_id):
    sql = "select count(*) * 5 as total_possible from challenge_weeks where challenge_id = %s and id < %s;"
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(sql % (challenge_id, week_id))
            checkins_possible_before_now = cur.fetchone()[0]
            now = datetime.now()
            day_of_week = now.weekday()
            return checkins_possible_before_now + min(day_of_week + 1, 5)



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
    checkins_to_subtract = bi_checkins(challenge_id)
    knocked_out = points_knocked_out(challenge_id)
    total_points_t2 = sum(x[0] for x in t2)
    total_points_t3 = sum(x[0] for x in t3)
    total_points_floating = sum(x[0] for x in floating) - checkins_to_subtract
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
        total_floating=total_points_floating,
        challenges=[c for c in challenges if c[3] not in set([1, challenge_id])],
    )


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


def number_of_non_green_weeks_before_this_one(challenge_id):
    sql = """
    select count(*) from challenge_weeks
      where 
      challenge_id = %s
      and "end" >= (
          select "end" from challenge_weeks where "end" <= current_date - 7 and green = true order by "end" desc limit 1
      )
      and "end" <= current_date - 7;
  """
    return fetchone(sql, [challenge_id]).count


@app.route("/create_challenge", methods=["GET", "POST"])
def create_challenge():
    print(request.method)
    if request.method == "POST":

        def create(conn, curr):
            name = request.form["name"]
            start = request.form["start"]
            end = request.form["end"]
            bi_weeks = request.form["bi_weeks"]
            challengers = request.form.getlist("challengers")
            curr.execute(
                'insert into challenges (name, start, "end", bi_weeks) values (%s, %s, %s, %s) returning id',
                [name, start, end, bi_weeks],
            )
            challenge_id = curr.fetchone()[0]
            for c in challengers:
                curr.execute(
                    "insert into challenger_challenges (challenge_id, challenger_id) values (%s, %s)",
                    [challenge_id, c],
                )
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            diff = end_date - start_date
            weeks = math.ceil(diff.days / 7)
            for w in range(weeks):
                start = start_date + timedelta(days=w * 7)
                end = start_date + timedelta(days=(w * 7) + 6)
                curr.execute(
                    'insert into challenge_weeks (challenge_id, week_of_year, start, "end") values (%s, %s, %s, %s)',
                    [challenge_id, start.isocalendar()[1], start, end],  # week of year
                )

        with_psycopg(create)

    challengers = fetchall(
        "select * from challengers where bmr is not null order by name"
    )
    return render_template("create_challenge.html", challengers=challengers)


@app.route("/")
@last_modified(
    "select time::TIMESTAMP as last_modified from checkins order by time desc limit 1"
)
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
        current_challenge = get_current_challenge()
    else:
        logging.debug("Getting challenge with name: %s", challenge_name)
        current_challenge = fetchone(
            "select * from challenges where name = %s", [challenge_name]
        )

    logging.info("Current challenge: %s", current_challenge)
    current_challenge_week = get_current_challenge_week()
    logging.info("Current challenge week: %s", current_challenge_week)

    if week_id is None:
        week_id = current_challenge_week.id

    total_points = calculate_total_score(current_challenge.id)

    logging.debug("Austin points: %s", total_points)

    selected_challenge_week = fetchone(
        "select * from challenge_weeks where id = %s", [week_id]
    )
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
    total_checkins = {x[1]: x[0] for x in points_so_far(current_challenge.id)}
    logging.info("TOTAL CHECKINS %s", total_checkins)
    logging.debug("WEEK: %s, LATEST: %s", week, latest)
    chart = checkin_chart(
        week,
        1000,
        600,
        current_challenge.id,
        selected_challenge_week.green,
        selected_challenge_week.bye_week,
        total_points,
        achievements,
        total_checkins,
        total_possible_checkins(current_challenge.id)[0],
        total_possible_checkins_so_far(current_challenge.id, 
                                       current_challenge_week.id),
    )
    write_og_image(chart, week_id)
    og_path = url_for("static", filename="preview-" + str(week_id) + ".png")
    logging.debug("Challenge ID: %s", current_challenge.id)
    cws = challenge_weeks()
    logging.debug("Weeks: %s", cws)
    current_challenge_weeks = next(v for v in cws if v[0][0] == current_challenge.name)
    logging.info("Current week index: %s", current_challenge_weeks)
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


def determine_if_green():
    challenge_week = get_current_challenge_week()
    num_non_green = number_of_non_green_weeks_before_this_one(
        challenge_week.challenge_id
    )
    logging.info("there were %s weeks before this one that werent green", num_non_green)
    green = random.randint(0, 100) < 20 * num_non_green
    logging.debug("is is green %s", green)

    def set_green(conn, cur):
        cur.execute(
            "update challenge_weeks set green = %s where id = %s",
            [green, challenge_week.id],
        )

    if challenge_week.green is None:
        with_psycopg(set_green)
    return green


@app.route("/make-it-green")
def make_it_green():
    green = determine_if_green()
    return render_template("green.html", green=green)


@app.route("/magic")
def magic():
    return render_template("magic.html")


@app.route("/challenger/<challenger>", methods=["GET", "POST"])
def challenger(challenger):
    if "timezone" in request.form:
        timezone = request.form["timezone"]

        def fn(conn, cur):
            cur.execute(
                "update challengers set tz = %s where name = %s", [timezone, challenger]
            )

        with_psycopg(fn)
    c = fetchone("select * from challengers where name = %s", [challenger])
    m = fetchone(
        'select cc.mulligan from challenger_challenges cc join challenges c on c.id = cc.challenge_id and c.start <= CURRENT_DATE and c."end" >= CURRENT_DATE where cc.challenger_id = %s',
        [c.id],
    )
    logging.info("Challenger: %s, mulligan: %s", c.name, m)
    return render_template(
        "challenger.html",
        name=challenger,
        bmr=c.bmr,
        timezone=c.tz,
        mulliganed=(m.mulligan != None),
    )


@app.route("/calc")
def calc():
    name = request.args.get("name")
    challengers = fetchall(
        "select * from challengers where bmr is not null order by name"
    )
    return render_template("calc.html", challengers=challengers, name=name)


@app.route("/add-checkin", methods=["GET", "POST"])
def add_checkin():
    logging.debug("Add checkin")
    name = request.form["name"]
    tier = request.form["tier"]
    time = datetime.fromisoformat(request.form["time"])
    day_of_week = time.strftime("%A")
    challenger = fetchone("select * from challengers where name = %s", [name])
    challenge_week_during_sql = """
        select * from challenge_weeks 
        where 
            week_of_year = extract(week from %s at time zone 'America/New_York') and
            extract(year from start) = extract(year from current_date)
        """
    challenge_week = fetchone(challenge_week_during_sql, [time])
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
    with_psycopg(
        insert_checkin(
            message=("%s checkin via magic" % tier),
            tier=("T%s" % tier),
            challenger=challenger,
            week_id=challenge_week.id,
            day_of_week=day_of_week,
            time=time,
        )
    )
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


def insert_checkin(message, tier, challenger, week_id, day_of_week=None, time=None):
    tz = pytz.timezone(challenger.tz)
    now = datetime.now(tz=tz)
    logging.info("now %s", now)

    def fn(conn, cur):
        cur.execute(
            "INSERT INTO checkins (name, time, tier, day_of_week, text, challenge_week_id, challenger, tz) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING returning id",
            (
                challenger.name,
                time or now,
                tier,
                day_of_week or now.strftime("%A"),
                message,
                week_id,
                challenger.id,
                challenger.tz,
            ),
        )
        return cur.fetchone().id

    return fn


@app.route("/mail", methods=["POST"])
def mail():
    fromaddress = request.json["from"]["text"]
    logging.info("MAIL: weve got mail from %s", fromaddress)

    sessionmta = request.json["session"]["mta"]
    if sessionmta != "mx1.forwardemail.net" and sessionmta != "mx2.forwardemail.net":
        logging.error("MAIL: not from mx1/2, %s", sessionmta)
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
        logging.error("MAIL: non buffer data %s", content["type"])
        return "2", 200

    bdata = bytearray(content["data"])
    md5 = hashlib.md5()
    md5.update(bdata)
    buffer_checksum = md5.hexdigest()

    if checksum != buffer_checksum:
        logging.error("MAIL: checksum mismatch %s %s", buffer_checksum, checksum)
        return "3", 200

    number, domain = fromaddress.split("@")
    message = bdata.decode("utf-8")

    logging.info("MAIL: content %s", message)

    if not is_checkin(message):
        logging.debug("MAIL: not checkin")
        return "4", 200

    tier = get_tier(message)

    logging.info("MAIL: tier %s", tier)

    if tier == "unknown":
        logging.info("MAIL: unknown tier")
        return "5", 200

    challenger = fetchone(
        "select * from challengers where phone_number = %s and email_domain = %s",
        (number, domain),
    )
    challenge_week = get_current_challenge_week(challenger.tz)

    logging.info("MAIL: challenger %s", challenger)
    logging.info("MAIL: challenge week %s", challenge_week.id)

    with_psycopg(insert_checkin(message, tier, challenger, challenge_week.id))

    return "success", 200


@app.route("/sms", methods=["POST"])
@twilio_request
def sms():
    body = request.form
    phone_number = body.get("From")
    message = body.get("Body")
    logging.info("SMS: %s %s", phone_number, message)

    if not is_checkin(message):
        logging.debug("SMS: not checkin")
        return "4", 200

    tier = get_tier(message)

    logging.info("SMS: tier %s", tier)

    if tier == "unknown":
        logging.info("SMS: unknown tier")
        return "5", 200

    challenger = fetchone(
        "select * from challengers where phone_number = %s or phone_number = %s",
        # check vs +1 and no +1
        (phone_number, phone_number[2:]),
    )
    challenge_week = get_current_challenge_week()

    logging.info("SMS: challenger %s", challenger)
    logging.info("SMS: challenge week %s", challenge_week.id)

    with_psycopg(insert_checkin(message, tier, challenger, challenge_week.id))

    return "success", 200


@app.route("/mulligan/<challenger>", methods=["GET", "POST"])
def mulligan(challenger):
    challenge_week = get_current_challenge_week()
    c = fetchone("select * from challengers where name = %s", [challenger])

    def insert_checkin_and_associate_mulligan(conn, cur):
        m = insert_checkin("MULLIGAN T1 checkin", "T1", c, challenge_week.id)(conn, cur)
        logging.debug("mulligan: %s, challenger: %s", m, c.id)
        cur.execute(
            "update challenger_challenges set mulligan = %s where challenger_id = %s and challenge_id = %s",
            [m, c.id, challenge_week.challenge_id],
        )

    with_psycopg(insert_checkin_and_associate_mulligan)
    return render_template("mulligan.html", challenger=c)


if __name__ == "__main__":
    app.run(debug=True)
