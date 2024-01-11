from typing import List, Dict, NamedTuple
import requests
import os
import cairosvg
import itertools
from datetime import datetime, timedelta
import json
import svgwrite
from flask import Flask, render_template, request, url_for
import psycopg
import logging

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(level=LOGLEVEL)

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


class CheckinChartData(NamedTuple):
    name: str
    data: List[DataUnit]

    def tostring(self) -> str:
        return json.dumps({"name": self.name, "data": self.data})

weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def checkin_chart(data: List[CheckinChartData], width: int, height: int, five_pluses: List[str]):
    if len(data) == 0:
        logging.warning('empty week + year selected')
        dwg = svgwrite.Drawing('empty.svg', size=(10, 10))
        return dwg.tostring()

    wGap = 0
    hGap = 20
    gutter = 80
    colors = ["#f7f7f7","#cccccc","#969696","#636363","#252525"]
    greens = ["#edf8e9","#c7e9c0","#a1d99b","#74c476","#41ab5d","#238b45","#005a32"]

    columns = len(data)
    rows = len(data[0].data)
    rectW = (width - rows * wGap - gutter) / rows
    rectH = (height - columns * hGap - gutter) / columns

    dwg = svgwrite.Drawing('checkin.svg', size=(width + 1, height))
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='white'))
    for column, chart in enumerate(data):
        yLabel = chart.name
        text1 = dwg.text(yLabel, insert=(0, rectH * column + hGap * column + gutter + rectH / 2), font_size=14, font_weight="bold")
        dwg.add(text1)
        for row, dataUnit in enumerate(chart.data):
            x = dataUnit.x
            checkedIn = dataUnit.checkedIn
            fill_color = colors[2] if checkedIn else 'white'
            stroke_color = colors[3]

            if five_pluses and yLabel in five_pluses and dataUnit.y != 0:
                fill_color = greens[4]
            if five_pluses and x in five_pluses:
                stroke_color = greens[6]

            if column == 0:
                text = dwg.text(x)
                text.translate(rectW * row + wGap * row + gutter + rectW / 2, gutter - 10)
                text.rotate(-90)
                dwg.add(text)

            rect = dwg.rect(insert=(row * rectW + row * wGap + gutter, column * rectH + column * hGap + gutter), size=(rectW, rectH), fill=fill_color, stroke=stroke_color, stroke_width=1, rx=2,ry=2)
            dwg.add(rect)

    return dwg.tostring()


def write_og_image(svg, weekNum, year):
    output = './static/preview-{week}-{year}.png'.format(week=weekNum,year=year)
    cairosvg.svg2png(bytestring=svg, write_to=output)


app = Flask(__name__)

connection_string = os.environ['DB_CONNECT_STRING']
def week_heat_map_from_db(weekNum, year):
    name_index = 0
    time_index = 1
    weekday_index = 3
    heatmap_data = []
    latest_date = None
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select time from checkins order by time desc limit 1")
            latest_date = cur.fetchone()
            start, end = get_start_end_dates(year, weekNum)
            logging.info("Week bounds: %s, %s", start, end)
            logging.info("Query: select distinct on (DATE(time), name) name, time, tier, day_of_week, text from checkins where time >= %s and time < %s", start, end)
            cur.execute("select distinct on (DATE(time), name) name, time, tier, day_of_week, text from checkins where time >= %s and time < %s",
                        (start, end))
            rows = cur.fetchall()
            rows.sort(key=lambda x: getWeekNumber(x[time_index]))
            grouped_by_weeks = {week: list(value) for week, value in itertools.groupby(rows, key=lambda x: getWeekNumber(x[time_index]))}
            rows.sort(key=lambda x: x[name_index]) # sort on name
            weeks_grouped_by_name = {name: list(value) for name, value in itertools.groupby(rows, key=lambda x: x[name_index])}

            names = get_names();
            logging.info("Challengers: %s", names)
            for name in names:
                if name not in weeks_grouped_by_name:
                    weeks_grouped_by_name[name] = []

            for name in weeks_grouped_by_name: 
                sorted_checkins = sortCheckinByWeekday(weeks_grouped_by_name[name], weekday_index)
                data = []
                for i, weekday in enumerate(weekdays):
                    checkinIndex = next((index for index, checkin in enumerate(sorted_checkins) if checkin[weekday_index] == weekday), -1)
                    data.append(DataUnit(weekday, checkinIndex + 1, bool(checkinIndex + 1)))
                heatmap_data.append(CheckinChartData(name, data))
        conn.commit()
    return heatmap_data, latest_date[0]

def fiveCheckinsThisWeek(challengerData):
    return challengerData[6].y >= 5 or challengerData[5].y >= 5 or challengerData[4].y >= 5

def get_names():
    with psycopg.connect(conninfo=connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from challengers where id in (select challenger_id from challenger_challenges where challenge_id = (select id from challenges where start <= NOW() and \"end\" > NOW())) order by name;")
            names = cur.fetchall()

            return [n for n, i in names]

@app.route("/")
def index():
    currentWeekNum = int(datetime.now().strftime("%W"))
    weekNum = int(request.args.get('week') or currentWeekNum)
    year = int(request.args.get('year') or 2024)
    week, latest = week_heat_map_from_db(weekNum, year);
    five_pluses = [challenger.name for _, challenger in enumerate(week) if fiveCheckinsThisWeek(challenger.data)]
    logging.info("WEEK: %s, LATEST: %s", week, latest)
    chart = checkin_chart(week, 800, 600, five_pluses)
    write_og_image(chart, weekNum, year)
    og_path = url_for('static', filename='preview-' + str(weekNum) + '-' + str(year) + '.png')
    print(og_path)
    return render_template('index.html',
                           svg=chart,
                           latest=latest,
                           keys=[i + 1 for i in range(52)],
                           week=int(weekNum),
                           year=year,
                           og_path=og_path)

if __name__ == "__main__":
    app.run(debug=True)
