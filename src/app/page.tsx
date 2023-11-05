import { getData } from './getData';
import { dataToHeatmapData } from './dataFormatting';
import { WeekSelect } from './components/WeekSelect';
import { CheckinChart } from './components/Chart';


export default async function Page() {
  const d = await getData('ROWS');
  const heatmapData = dataToHeatmapData(d);
  const weeks = Object.keys(heatmapData).sort();
  const mostRecentWeek = weeks.length - 1;
  // @ts-ignore TODO
  const week = heatmapData[weeks[mostRecentWeek]];
  // @ts-ignore TODO
  const fivePluses = week.map(({id, data}) => data.findIndex(({y}) => y === 5) !== -1 ? id : undefined);
 
  return <>
    <WeekSelect weeks={weeks} defaultValue={mostRecentWeek} />
    <CheckinChart
      height={600}
      width={800}
      data={week}
      fivePluses={fivePluses}
    />
  </>
}
