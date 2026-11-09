/** Number formatting with units. kW = power (rate); kWh = energy (amount). */

const twoDecimals = new Intl.NumberFormat('en', { maximumFractionDigits: 2 });
const wholeNumber = new Intl.NumberFormat('en', { maximumFractionDigits: 0 });

export function formatWatts(watts: number): string {
  return `${wholeNumber.format(watts)} W`;
}

export function formatKw(kw: number): string {
  return `${twoDecimals.format(kw)} kW`;
}

export function formatKwh(kwh: number): string {
  return `${twoDecimals.format(kwh)} kWh`;
}
