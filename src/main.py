from typing import List, Dict, NamedTuple
import math
import requests
import os
import cairosvg
import itertools
from datetime import datetime, timedelta, date
import json
import svgwrite
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

connection_string = os.environ["DB_CONNECT_STRING"]
LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level="INFO")
pwlogger = logging.getLogger("peewee")
pwlogger.addHandler(logging.StreamHandler())
pwlogger.setLevel(logging.DEBUG)


def get_start_end_dates(year, week_num):
    # Find the first day of the year
    first_day = datetime(year, 1, 1)

    # If the first day of the year is not Monday then find the first
    if first_day.weekday() > 0:
        first_day = first_day + timedelta(7 - first_day.weekday())

    # Find the start and end date of the week
    start_date = first_day + timedelta(days=(week_num - 1) * 7)
    end_date = start_date + timedelta(days=7)

    return start_date, end_date


def getWeekNumber(date):
    return int(date.strftime("%W"))


def sortCheckinByWeekday(data: List[str], weekdayIndex: int) -> List[str]:
    return sorted(data, key=lambda x: weekdays.index(x[weekdayIndex]))


class DataUnit(NamedTuple):
    x: str
    y: int
    checkedIn: bool
    time: datetime
    tier: str


class CheckinChartData(NamedTuple):
    name: str
    data: List[DataUnit]
    totalCheckins: int
    points: float

    def tostring(self) -> str:
        return json.dumps({"name": self.name, "data": self.data})


weekdays = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def checkin_chart(
    data: List[CheckinChartData],
    width: int,
    height: int,
    challenge_id,
    green,
    bye_week,
    austin_points,
    achievements
):
    if len(data) == 0:
        logging.warning("empty week + year selected")
        dwg = svgwrite.Drawing("empty.svg", size=(10, 10))
        return dwg.tostring()

    wGap = 0
    hGap = 20
    gutter = 80
    colors = ["#f7f7f7", "#cccccc", "#969696", "#636363", "#252525"]
    greens = [
        "#edf8e9",
        "#c7e9c0",
        "#a1d99b",
        "#74c476",
        "#41ab5d",
        "#238b45",
        "#005a32",
    ]
    green_mode = greens[4]
    base_color = green_mode if green else "white"

    columns = len(data)
    rows = len(data[0].data)
    rectW = (width - rows * wGap - gutter) / (rows + 1)
    rectH = (height - columns * hGap - gutter) / (columns + 1)

    dwg = svgwrite.Drawing("checkin.svg", size=(width + 1, height), debug=False)
    dwg.add(
        dwg.rect(
            insert=(0, 0),
            size=("100%", "100%"),
            fill="white" if not green else green_mode,
        )
    )
    knocked_out_names = knocked_out(challenge_id)
    logging.info("knocked out: %s", knocked_out_names)
    text_color = "black" if green else ""
    for column, chart in enumerate(data):
        yLabel = chart.name
        is_knocked_out = yLabel in knocked_out_names
        text1 = dwg.text(
            yLabel,
            insert=(0, rectH * column + hGap * column + gutter + rectH / 2),
            font_size=14,
            font_weight="bold" if not is_knocked_out else "normal",
            text_decoration="line-through" if is_knocked_out else "none",
            fill=text_color,
        )
        dwg.add(text1)
        for row, dataUnit in enumerate(chart.data):
            x = dataUnit.x
            checkedIn = dataUnit.checkedIn
            fill_color = colors[2] if checkedIn and not is_knocked_out else base_color
            fill_color = colors[0] if is_knocked_out and checkedIn else fill_color
            stroke_color = colors[3] if not is_knocked_out else colors[1]

            if chart.totalCheckins >= 5 and dataUnit.y != 0:
                fill_color = greens[4] if not green else greens[6]
            if chart.totalCheckins >= 5:
                stroke_color = greens[6]
            # gold for 7!
            if chart.totalCheckins >= 7 and dataUnit.y != 0:
                fill_color = "#D4AF37"

            if column == 0:
                # add day of week
                text = dwg.text(x, fill=text_color)
                text.translate(
                    rectW * row + wGap * row + gutter + rectW / 2, gutter - 10
                )
                text.rotate(-90)
                dwg.add(text)

            rect = dwg.rect(
                insert=(
                    row * rectW + row * wGap + gutter,
                    column * rectH + column * hGap + gutter,
                ),
                size=(rectW, rectH),
                fill=fill_color,
                stroke=stroke_color,
                stroke_width=1,
                rx=2,
                ry=2,
            )
            group = dwg.g()
            text = dwg.text(dataUnit.tier)
            text.translate(
                row * rectW + row * wGap + gutter + rectW / 2 - 5,
                column * rectH + column * hGap + gutter + rectH / 2 + 5,
            )
            group.add(rect)
            if dataUnit.tier:
                group.add(text)
            if dataUnit.time is not None and dataUnit.time.strftime("%H:%M") == achievements[1]:
                text = dwg.text('🌚')
                text.translate(
                    row * rectW + row * wGap + gutter + rectW / 2 + 15,
                    column * rectH + column * hGap + gutter + rectH / 2 + 5,
                )
                group.add(text)
            if dataUnit.time is not None and dataUnit.time.strftime("%H:%M") == achievements[0]:
                text = dwg.text('🌞')
                text.translate(
                    row * rectW + row * wGap + gutter + rectW / 2 + 15,
                    column * rectH + column * hGap + gutter + rectH / 2 + 5,
                )
                group.add(text)


            dwg.add(group)

        if chart.name in austin_points:
            logging.info(
                "adding points for %s total %s week %s",
                chart.name,
                austin_points[chart.name],
                chart.points,
            )
            text = dwg.text(
                "%s (%s)"
                % (round(min(chart.points, 6.0), 4), austin_points[chart.name])
            )
            text.translate(
                rows * rectW + rows * wGap + gutter + rectW / 2 - 30,
                column * rectH + column * hGap + gutter + rectH / 2,
            )
            dwg.add(text)

    # Add Points Label
    text = dwg.text("Points", fill=text_color)
    text.translate(
        rectW * (rows) + wGap * (rows) + gutter + rectW / 2 - 30,
        gutter - 30,
    )
    dwg.add(text)
    text = dwg.text("(Total)", fill=text_color)
    text.translate(
        rectW * (rows) + wGap * (rows) + gutter + rectW / 2 - 30,
        gutter - 10,
    )
    dwg.add(text)

    if bye_week:
        text = dwg.text("BYE")
        text.translate(width / 4, height / 2)
        text["font-size"] = 200
        text.fill = text_color
        dwg.add(text)
        text = dwg.text("WEEK")
        text.translate(width / 4 - 50, height / 2 + 175)
        text["font-size"] = 200
        text.fill = text_color
        dwg.add(text)

    return dwg.tostring()


def write_og_image(svg, week):
    try:
        output = "./static/preview-{week}.png".format(week=week)
        cairosvg.svg2png(bytestring=svg, write_to=output)
    except:
        logging.info("Failed to write og image")


app = Flask(__name__)

logging.info(connection_string)


def fiveCheckinsThisWeek(challengerData):
    return (
        challengerData[6].y >= 5 or challengerData[5].y >= 5 or challengerData[4].y >= 5
    )


def get_names(challenge_id):
    return [
        n.name
        for n in Challengers.select(Challengers.name)
        .join(ChallengerChallenges)
        .where(ChallengerChallenges.challenge == challenge_id)
        .objects()
    ]


def knocked_out(challenge_id):
    return [
        n.name
        for n in Challengers.select(Challengers.name)
        .join(ChallengerChallenges)
        .where(
            (ChallengerChallenges.challenge == challenge_id)
            & (ChallengerChallenges.knocked_out == True)
        )
        .objects()
    ]


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


def points_austin_method(challenge_id):
    nums = [
        {
            "name": n.name,
            "value": 1.2 if n.tier == "T3" else 1,
            "week": n.challenge_week.id,
        }
        for n in Checkins.select(Checkins.tier, Checkins.name, Checkins.challenge_week)
        .join(
            ChallengeWeeks,
            on=((Checkins.challenge_week == ChallengeWeeks.id)),
        )
        .where(ChallengeWeeks.challenge == challenge_id)
        .order_by(Checkins.challenge_week)
        .objects()
    ]
    names = set(n["name"] for n in nums)
    result = {
        n: sum(
            round(min(sum(n2["value"] for n2 in week if n2["name"] == n), 6), 4)
            for w, week in itertools.groupby(nums, key=lambda x: x["week"])
        )
        for n in names
    }
    logging.info("Points Austin Method: %s", result)
    return result


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
    knocked_out = points_knocked_out(challenge_id)
    total_points_t2 = sum(x[0] for x in t2)
    total_points_t3 = sum(x[0] for x in t3)
    ante_t2 = total_ante(challenge_id, "T2")
    ante_t3 = total_ante(challenge_id, "T3")
    dollars_per_point_t2 = ante_t2 / total_points_t2
    dollars_per_point_t3 = ante_t3 / total_points_t3

    points = sorted(points, key=lambda x: -x[0])
    logging.info("points: %s", points)
    challenges = get_challenges()
    return render_template(
        "details.html",
        t2=t2,
        t3=t3,
        total_points_t2=total_points_t2,
        dollars_per_point_t2=dollars_per_point_t2,
        total_ante_t2=int(dollars_per_point_t2 * total_points_t2),
        total_points_t3=total_points_t3,
        dollars_per_point_t3=dollars_per_point_t3,
        total_ante_t3=int(dollars_per_point_t3 * total_points_t3),
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

    current_challenge_week = get_current_challenge_week()

    checkin_predicate = (Checkins.time >= ChallengeWeeks.start) & (
        Checkins.time < fn.date_add(ChallengeWeeks.end, "1 day")
    )
    if week_id is None:
        week_id = current_challenge_week.id

    austin_points = points_austin_method(current_challenge.id)

    selected_challenge_week = ChallengeWeeks.get(id=week_id)

    checkins = (
        Checkins.select()
        .join(ChallengeWeeks, on=(checkin_predicate))
        .where(ChallengeWeeks.id == week_id)
    )

    logging.info("Week checkins: %s", [checkin.name for checkin in checkins.objects()])
    week, latest, achievements = week_heat_map_from_checkins(
        [checkin for checkin in checkins.objects()], current_challenge.id
    )
    week = sorted(week, key=lambda x: -x.points)
    logging.info("WEEK: %s, LATEST: %s", week, latest)
    chart = checkin_chart(
        week,
        800,
        600,
        current_challenge.id,
        selected_challenge_week.green,
        selected_challenge_week.bye_week,
        austin_points,
        achievements
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


def sortCheckinByWeekdayS(data: List[str]) -> List[str]:
    return sorted(data, key=lambda x: weekdays.index(x.day_of_week))


def week_heat_map_from_checkins(checkins, challenge_id):
    heatmap_data = []
    latest_date = None
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select time from checkins order by time desc limit 1")
            latest_date = cur.fetchone()
        conn.commit()
    checkins.sort(key=lambda x: x.name)
    weeks_grouped_by_name = {
        name: list(value)
        for name, value in itertools.groupby(checkins, key=lambda x: x.name)
    }

    names = get_names(challenge_id)
    logging.info("Challengers: %s", names)
    for name in names:
        if name not in weeks_grouped_by_name:
            weeks_grouped_by_name[name] = []

    latest = '00:00:00'
    earliest = '23:59:59'
    for name in weeks_grouped_by_name:
        sorted_checkins = sortCheckinByWeekdayS(weeks_grouped_by_name[name])
        data = []
        total_checkins = 0
        total_points = 0
        for i, weekday in enumerate(weekdays):
            checkinIndex = next(
                (
                    index
                    for index, checkin in enumerate(sorted_checkins)
                    if checkin.day_of_week == weekday
                ),
                -1,
            )
            tier = (
                sorted_checkins[checkinIndex].tier
                if len(sorted_checkins) > checkinIndex and checkinIndex >= 0
                else None
            )
            time = (
                sorted_checkins[checkinIndex].time
                if len(sorted_checkins) > checkinIndex and checkinIndex >= 0
                else None
            )
            time_hour = time.strftime("%H:%M") if time else None
            if time_hour and time_hour > latest:
                latest = time_hour
            if time_hour and time_hour < earliest:
                earliest = time_hour
            total_checkins += 1 if bool(checkinIndex + 1) else 0
            if tier:
                total_points += 1.2 if tier == "T3" else 1
            data.append(
                DataUnit(
                    weekday,
                    checkinIndex + 1,
                    bool(checkinIndex + 1),
                    time,
                    tier
                )
            )
        heatmap_data.append(CheckinChartData(name, data, total_checkins, total_points))
    return heatmap_data, latest_date[0], (earliest, latest)


if __name__ == "__main__":
    app.run(debug=True)
