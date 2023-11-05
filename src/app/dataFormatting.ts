import { Temporal } from '@js-temporal/polyfill';
import type { CheckinChartData } from './components/Chart';
export type Data = {
  headers: string[];
  rows: string[][];
}

export type CalendarData = {
  from: string;
  to: string;
  data: {
    value: number,
    day: string,
  }[];
}

export const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
export const groupBy = (data: string[][], index: number, fn: (x: string) => string | number) => {
  return data.reduce((acc, row) => {
    const val = fn(row[index]);
    (acc[val] || (acc[val] = [])).push(row)
    return acc;
  }, {} as {[key: string | number]: any});
}

function sortCheckinByWeekday(data: string[], weekdayIndex: number) {
  return data.sort((a, b) => {
    return weekdays.indexOf(a[weekdayIndex]) - weekdays.indexOf(b[weekdayIndex]);
  });
}

function getWeekNumber(isoDate: string): number {
  return Temporal.Instant.from(isoDate+'Z').toZonedDateTimeISO('GMT+0').weekOfYear;
}

export function dataToHeatmapData(data: Data): {
  [key: string]: CheckinChartData,
} {
  const weekdayIndex = data.headers.indexOf('Day of Week');
  const timeIndex = data.headers.indexOf('time');
  const nameIndex = data.headers.indexOf('Name');
  const groupedByWeeks = groupBy(data.rows, timeIndex, getWeekNumber);
  const weeksGroupedByName = Object.keys(groupedByWeeks).reduce((groups, week) => ({
    ...groups,
    [week]: groupBy(
    groupedByWeeks[week],
    nameIndex,
    (t: string) => {
      return t;
    }
  )}), {});
  const heatMapData = Object.keys(weeksGroupedByName).reduce((groups,week) => ({
    ...groups,
    // @ts-ignore TODO
    [week]: Object.keys(weeksGroupedByName[week]).map(name => {
      // @ts-ignore TODO
      const sortedCheckins = sortCheckinByWeekday(weeksGroupedByName[week][name], weekdayIndex);
    return {
      id: name,
      data: weekdays.map((weekday, i) => {
        const checkinIndex = sortedCheckins.findIndex(checkin => checkin[weekdayIndex] === weekday);
        return {
      //@ts-ignore TODO
          x: weekday,//weeksGroupedByName[week][name].find(checkin => checkin[nameIndex] === name) ? 1 : 0,
          y: checkinIndex + 1,
          checkedIn: Boolean(checkinIndex + 1),
        }
      })
    }
  })}), {});
  return heatMapData;
}

export function getLatestDate(data: Data): string {
  const timeIndex = data.headers.indexOf('time');
  const rows = data.rows;
  rows.sort((a, b) => (new Date(a[timeIndex])).getTime() - (new Date(b[timeIndex])).getTime());
  return rows[rows.length - 1][timeIndex]
}
