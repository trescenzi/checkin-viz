import type { Data } from './dataFormatting.ts';

type GoogleSheetResponse<T> = {
  range: string;
  majorDimension: "COLUMNS" | "ROWS";
  values: Array<T[]>;
};

const id = "1k-tnKWWB3q6XCF2ofav-yT_CGprIFMBTf9OPhvR8hlM";
export async function getData(
  dimension: "COLUMNS" | "ROWS"
): Promise<Data> {
  const url = `https://sheets.googleapis.com/v4/spreadsheets/${id}/values/database!A:E?majorDimension=${dimension}&key=${process.env.GOOGLE_API_KEY}`;
  return fetch(url)
    .then((res) => res.json() as Promise<GoogleSheetResponse<string>>)
    .then(gdata => ({
      headers: gdata.values[0],
      rows: gdata.values.slice(1),
    }))
}
