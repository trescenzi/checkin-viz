import { getData } from '../getData';
import { dataToHeatmapData } from '../dataFormatting';
import { CheckinChart } from '../components/Chart';
import { WeekSelect } from '../components/WeekSelect';

// @ts-ignore TODO
export default async function Page({params: {weekNum}}) {
  const d = await getData('ROWS');
  const heatmapData = dataToHeatmapData(d);
  const weeks = Object.keys(heatmapData).sort();
  // @ts-ignore TODO
  const week = heatmapData[weeks[weekNum]];
  // @ts-ignore TODO
  const fivePluses = week.map(({id, data}) => data.findIndex(({y}) => y === 5) !== -1 ? id : undefined);
 
  return <>
    <WeekSelect weeks={weeks} defaultValue={weekNum} />
    <CheckinChart
      height={600}
      width={800}
      data={week}
      fivePluses={fivePluses}
    />
  </>
}
