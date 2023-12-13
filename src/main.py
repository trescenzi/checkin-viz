from typing import List, Dict, NamedTuple
import requests
import os
import itertools
from datetime import datetime
import json
import svgwrite
from flask import Flask, render_template, request

key = os.environ.get("GOOGLE_API_KEY");
id = "1k-tnKWWB3q6XCF2ofav-yT_CGprIFMBTf9OPhvR8hlM";
url = f"https://sheets.googleapis.com/v4/spreadsheets/{id}/values/database!A:E?majorDimension=ROWS&key={key}"
response = requests.get(url)
data = response.json()
headers = data["values"][0]
rows = data["values"][1:]


def getWeekNumber(datestr):
   return int(datetime.fromisoformat(datestr).strftime("%W"))

def sortCheckinByWeekday(data: List[str], weekdayIndex: int) -> List[str]:
    return sorted(data, key=lambda x: weekdays.index(x[weekdayIndex]))

class DataUnit(NamedTuple):
    x: str
    y: int
    checkedIn: bool

class CheckinChartData(NamedTuple):
    id: str
    data: List[DataUnit]

    def tostring(self) -> str:
        return json.dumps({"id": self.id, "data": self.data})

weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
weekday_index = headers.index('Day of Week')
time_index = headers.index('time')
name_index = headers.index('Name')
def data_to_heatmap_data() -> Dict[int, List[CheckinChartData]]:
    rows.sort(key=lambda x: getWeekNumber(x[time_index]))

    grouped_by_weeks = {week: list(value) for week, value in itertools.groupby(rows, key=lambda x: getWeekNumber(x[time_index]))}
    heat_map_data = {}
    for week in grouped_by_weeks:
        weeks_data = grouped_by_weeks[week]
        weeks_data.sort(key=lambda x: x[name_index]) # sort on name
        weeks_grouped_by_name = {name: list(value) for name, value in itertools.groupby(weeks_data, key=lambda x: x[name_index])}
        heat_map_data[week] = []
        for name in weeks_grouped_by_name: 
            sorted_checkins = sortCheckinByWeekday(weeks_grouped_by_name[name], weekday_index)
            data = []
            for i, weekday in enumerate(weekdays):
                checkinIndex = next((index for index, checkin in enumerate(sorted_checkins) if checkin[weekday_index] == weekday), -1)
                data.append(DataUnit(weekday, checkinIndex + 1, bool(checkinIndex + 1)))
            heat_map_data[week].append(CheckinChartData(name, data))
    return heat_map_data


data = {"headers": headers, "rows": rows}

heatmapData = data_to_heatmap_data();
latest = sorted(rows, key=lambda x: x[time_index])[-1][time_index]

def checkin_chart(data: List[CheckinChartData], width: int, height: int, five_pluses: List[str]):
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

    for column, chart in enumerate(data):
        yLabel = chart.id
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


app = Flask(__name__, static_url_path='',)
@app.route("/")
def index():
    weekNum = request.args.get('week') or max(heatmapData, key=int)
    week = heatmapData[int(weekNum)]
    print(heatmapData.keys())
    five_pluses = [week.id for _, week in enumerate(week) if week.data[-1].y >= 5]
    chart = checkin_chart(week, 800, 600, five_pluses);
    return render_template('index.html', svg=chart, latest=latest, keys=heatmapData.keys(), week=int(weekNum))

if __name__ == "__main__":
    app.run(debug=True)

