import { getData } from '../getData';
import { dataToHeatmapData, getLatestDate } from '../dataFormatting';
import { CheckinChart } from '../components/Chart';
import { WeekSelect } from '../components/WeekSelect';
import { LatestDate } from '../components/LatestDate';

export default async function Page({params: {weekNum}}: {params: {weekNum: string}}) {
  const d = await getData('ROWS');
  const heatmapData = dataToHeatmapData(d);
  const weeks = Object.keys(heatmapData).sort();
  const weekNumNumber = parseInt(weekNum);
  if (!weekNumNumber) {
    return <></>;
  }
  const week = heatmapData[weeks[weekNumNumber]];
  const fivePluses = week.map(({id, data}) => data.findIndex(({y}) => y === 5) !== -1 ? id : undefined);
 
  return <>
    <WeekSelect weeks={weeks} defaultValue={weekNumNumber} />
    <LatestDate date={getLatestDate(d)} />
    <CheckinChart
      height={600}
      width={800}
      data={week}
      fivePluses={fivePluses}
    />
  </>
}
