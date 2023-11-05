import { getData } from './getData';
import { dataToHeatmapData, getLatestDate } from './dataFormatting';
import { WeekSelect } from './components/WeekSelect';
import { CheckinChart } from './components/Chart';
import { LatestDate } from './components/LatestDate';


export default async function Page() {
  const d = await getData('ROWS');
  const heatmapData = dataToHeatmapData(d);
  const weeks = Object.keys(heatmapData).sort();
  const mostRecentWeek = weeks.length - 1;
  const week = heatmapData[weeks[mostRecentWeek]];
  const fivePluses = week.map(({id, data}) => data.findIndex(({y}) => y === 5) !== -1 ? id : undefined);
 
  return <>
    <WeekSelect weeks={weeks} defaultValue={mostRecentWeek} />
    <LatestDate date={getLatestDate(d)} />
    <CheckinChart
      height={600}
      width={800}
      data={week}
      fivePluses={fivePluses}
    />
  </>
}
