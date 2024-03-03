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
from models import Checkins, Challenges, ChallengeWeeks, Challengers, ChallengerChallenges
from peewee import *
import random

connection_string = os.environ["DB_CONNECT_STRING"]
LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level="INFO")
pwlogger = logging.getLogger('peewee')
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


class CheckinChartData(NamedTuple):
    name: str
    data: List[DataUnit]

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
    data: List[CheckinChartData], width: int, height: int, five_pluses: List[str],
    challenge_id
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

    columns = len(data)
    rows = len(data[0].data)
    rectW = (width - rows * wGap - gutter) / rows
    rectH = (height - columns * hGap - gutter) / columns

    dwg = svgwrite.Drawing("checkin.svg", size=(width + 1, height), debug=False)
    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))
    knocked_out_names = knocked_out(challenge_id)
    logging.info("knocked out: %s", knocked_out_names)
    for column, chart in enumerate(data):
        yLabel = chart.name
        is_knocked_out = yLabel in knocked_out_names
        text1 = dwg.text(
            yLabel,
            insert=(0, rectH * column + hGap * column + gutter + rectH / 2),
            font_size=14,
            font_weight="bold" if not is_knocked_out else "normal",
            text_decoration="line-through" if is_knocked_out else "none",
        )
        dwg.add(text1)
        for row, dataUnit in enumerate(chart.data):
            x = dataUnit.x
            checkedIn = dataUnit.checkedIn
            fill_color = colors[2] if checkedIn and not is_knocked_out else "white"
            fill_color = colors[0] if is_knocked_out and checkedIn else fill_color
            stroke_color = colors[3] if not is_knocked_out else colors[1]

            if five_pluses and yLabel in five_pluses and dataUnit.y != 0:
                fill_color = greens[4]
            if five_pluses and x in five_pluses:
                stroke_color = greens[6]

            if column == 0:
                text = dwg.text(x)
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
            if dataUnit.time:
                rect.update(
                    {
                        "hx-get": "/view-checkin?date="
                        + dataUnit.time.isoformat()
                        + "&challenger_id="
                        + yLabel
                    }
                )
            dwg.add(rect)

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
    return [n.name for n in Challengers.select(Challengers.name).join(ChallengerChallenges).where(ChallengerChallenges.challenge == challenge_id).objects()]


def knocked_out(challenge_id):
    return [n.name for n in Challengers.select(Challengers.name).join(ChallengerChallenges).where((ChallengerChallenges.challenge == challenge_id) & (ChallengerChallenges.knocked_out == True)).objects()]


def get_challenges():
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            logging.info("select * from challenges")
            cur.execute("select * from challenges")
            return cur.fetchall()

def points_so_far(challenge_id):
    sql = """
    SELECT SUM(count), name 
    FROM (SELECT week, name, LEAST(count, 5) as count FROM
      (SELECT 
        date_part('week', time) as week, name,
        COUNT(distinct date_part('day', time)) as count
        FROM
        checkins
        WHERE
        time >= (SELECT start FROM challenges WHERE id = %s)
        AND time <= (SELECT "end" FROM challenges WHERE id = %s)
        GROUP BY
        week, name
        ORDER BY
        week DESC, name
    ) as sub_query) group by name;
    """
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (challenge_id, challenge_id))
            return cur.fetchall()


def challenge_data(challenge_id):
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from challenges where id = %s;", (challenge_id,))
            return cur.fetchone()


@app.route("/details")
def details():
    challenge_id = request.args.get("challenge_id")
    challenge = challenge_data(challenge_id)
    logging.info("Challenge ID: %s %s", challenge_id, challenge)
    weeksSinceStart = min(
        math.ceil((date.today() - challenge[1]).days / 7),
        math.floor((challenge[2] - challenge[1]).days / 7)
    ) - challenge[4]
    logging.info("Weeks since start: %s", weeksSinceStart)
    points = points_so_far(challenge_id)
    points = sorted(points, key=lambda x: -x[0])
    logging.info("points: %s", points)
    challenges = get_challenges()
    return render_template(
        "details.html",
        points=points,
        challenge=challenge,
        weeks=weeksSinceStart,
        challenges=[c for c in challenges if c[3] not in set([1, challenge_id])],
    )

def challenge_weeks():
    challenges = Challenges.select(Challenges.name, ChallengeWeeks.id, ChallengeWeeks.start).join(ChallengeWeeks).order_by(ChallengeWeeks.start)
    return [list(value) for n, value in itertools.groupby(challenges.tuples(), key=lambda x: x[0])]

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

    current_challenge = None;
    if challenge_name is None:
        logging.info("Getting challenge for current week dates: %s %s %s", current_year, current_week, current_date)
        current_challenge = Challenges.select().where((Challenges.start <= current_date) & (Challenges.end >= current_date)).get()
    else:
        logging.info("Getting challenge with name: %s", challenge_name)
        current_challenge = Challenges.select().where(Challenges.name == challenge_name).get()

    challenge_week_predicate = (ChallengeWeeks.start.year ==  current_year) & (ChallengeWeeks.week_of_year == current_week);
    current_challenge_week = ChallengeWeeks.select().where(challenge_week_predicate).get()


    checkin_predicate = ((Checkins.time >= ChallengeWeeks.start) & (Checkins.time < ChallengeWeeks.end))
    checkins = None
    if (week_id is None):
        week_id = current_challenge_week.id
    checkins = Checkins.select().join(ChallengeWeeks, on=(checkin_predicate)).where(ChallengeWeeks.id == week_id)

    logging.info("Week checkins: %s", [checkin.name for checkin in checkins.objects()])
    week, latest = week_heat_map_from_checkins([checkin for checkin in checkins.objects()], current_challenge.id)
    five_pluses = [
        challenger.name
        for _, challenger in enumerate(week)
        if fiveCheckinsThisWeek(challenger.data)
    ]
    logging.info("WEEK: %s, LATEST: %s", week, latest)
    chart = checkin_chart(week, 800, 600, five_pluses, current_challenge.id)
    write_og_image(chart, week_id)
    og_path = url_for(
        "static", filename="preview-" + str(week_id) + ".png"
    )
    logging.info("Challenge ID: %s", current_challenge.id)
    cws = challenge_weeks()
    logging.info("Weeks: %s", cws)
    current_challenge_weeks = next(v for v in cws if v[0][0] == current_challenge.name)
    logging.info("Current week index: %s", current_challenge_weeks)
    week_index = next(i for i, v in enumerate(current_challenge_weeks) if v[1] == int(week_id)) + 1
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
        current_week_start=current_challenge_weeks[week_index-1][2].strftime("%m/%d"),
        current_week=current_week
    )

@app.route("/make-it-green")
def make_it_green():
    green = random.randint(1,100) < 21
    logging.info("is is green %s", green)
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

    for name in weeks_grouped_by_name:
        sorted_checkins = sortCheckinByWeekdayS(weeks_grouped_by_name[name])
        data = []
        for i, weekday in enumerate(weekdays):
            checkinIndex = next(
                (
                    index
                    for index, checkin in enumerate(sorted_checkins)
                    if checkin.day_of_week == weekday
                ),
                -1,
            )
            data.append(
                DataUnit(
                    weekday,
                    checkinIndex + 1,
                    bool(checkinIndex + 1),
                    (
                        sorted_checkins[checkinIndex].time
                        if len(sorted_checkins) > checkinIndex
                        and checkinIndex >= 0
                        else None
                    ),
                )
            )
        heatmap_data.append(CheckinChartData(name, data))
    return heatmap_data, latest_date[0]


if __name__ == "__main__":
    app.run(debug=True)
