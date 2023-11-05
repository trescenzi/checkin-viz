export async function LatestDate({date}: {date: string}) {
  const d = new Date(date);
  const displayDate = new Intl.DateTimeFormat('en-US', 
    {month: "2-digit", day: "2-digit", hour: "numeric", minute: "numeric"}
  ).format(d)
  return <span id="latestDate">Updated Last: {displayDate}</span>
}
