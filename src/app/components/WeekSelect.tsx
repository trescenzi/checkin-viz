import { selectWeek } from '../selectWeek';

function getWeekStartDate(weekNumber: number): string {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  
  const firstDayOfYear = new Date(currentYear, 0, 1);
  const daysOffset = firstDayOfYear.getDay() > 0 ? (7 - firstDayOfYear.getDay()) : 0;
  
  const startDate = new Date(currentYear, 0, 1 + (7 * (weekNumber - 1)) - daysOffset);
  startDate.setHours(0, 0, 0, 0);
  
  return startDate.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
}
export async function WeekSelect({
  weeks,
  defaultValue
}: {
    weeks: string[],
    defaultValue: number
  }) {
  return <form action={selectWeek}>
    <label htmlFor="weekSelect">
      Week:
    </label>
    <select id="weekSelect" name="weekSelect" defaultValue={defaultValue}>
      {weeks.map((week, i) => <option key={i} value={i}>{getWeekStartDate(parseInt(week))}</option>)}
    </select>
    <button>View</button>
  </form>
}
