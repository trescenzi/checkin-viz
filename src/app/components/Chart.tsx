export type CheckinChartData = {
  id: string,
  data: {
    x: string;
    y: number;
    checkedIn: boolean;
  }[];
}[];
const wGap = 0;
const hGap = 20;
const gutter = 80;
const colors = ["#f7f7f7","#cccccc","#969696","#636363","#252525"];
const greens = ["#edf8e9","#c7e9c0","#a1d99b","#74c476","#41ab5d","#238b45","#005a32"];
export async function CheckinChart({
  data,
  width,
  height,
  fivePluses,
}: {
    data: CheckinChartData;
    width: number;
    height: number;
    fivePluses: Array<string | undefined>;
}) {
  const columns = data.length;
  const rows = data[0].data.length;
  const rectW = (width - rows * wGap - gutter) / rows;
  const rectH = (height - columns * hGap - gutter) / columns;
  return <svg width={width + 1} height={height} xmlns="http://www.w3.org/2000/svg">
    {data.map(({id: yLabel, data}, column) => { 
      return <g key={column}>
        <text
          y={rectH * column + hGap * column + gutter + rectH / 2}
          fontSize={14}
          fontWeight={'bold'}
          key={yLabel}
        >{yLabel}</text>
        {data.map(({x, checkedIn}, row) => {
          return <g key={row}>
            {column === 0 &&
              <text
                fontSize={12}
                key={x}
                transform={`translate(${rectW * row + wGap * row + gutter + rectW / 2}, ${gutter - 10}) rotate(-90)`}
              >{x}</text>
            }
            <rect 
              key={row + x}
              height={rectH}
              width={rectW}
              x={row * rectW + row * wGap + gutter}
              y={column * rectH + column * hGap + gutter}
              fill={checkedIn ? fivePluses.includes(yLabel) ? greens[4] : colors[2] : 'white'}
              rx={2}
              stroke={fivePluses.includes(x) ? greens[6] : colors[3]}
              strokeWidth={1}
            />
          </g>
        })}
      </g>
    })}
  </svg>
}
