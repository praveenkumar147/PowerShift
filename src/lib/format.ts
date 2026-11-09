/** Number formatting with units. kW = power (rate); kWh = energy (amount). */

const twoDecimals = new Intl.NumberFormat('en', { maximumFractionDigits: 2 });
const wholeNumber = new Intl.NumberFormat('en', { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 1 });

export function formatWatts(watts: number): string {
  return `${wholeNumber.format(watts)} W`;
}

export function formatKw(kw: number): string {
  return `${twoDecimals.format(kw)} kW`;
}

export function formatKwh(kwh: number): string {
  return `${twoDecimals.format(kwh)} kWh`;
}

export function formatShare(fraction: number): string {
  return percent.format(fraction);
}

/**
 * Amount in the household's currency. An unknown or missing code falls back to a
 * plain number with the code as a suffix, rather than guessing a symbol.
 */
function currencyAmount(amount: number, currency: string | null | undefined, digits: number): string {
  if (!currency) return amount.toFixed(digits);
  try {
    return new Intl.NumberFormat('en', {
      style: 'currency',
      currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(amount);
  } catch {
    return `${amount.toFixed(digits)} ${currency}`;
  }
}

export function formatMoney(amount: number, currency: string | null | undefined): string {
  return currencyAmount(amount, currency, 2);
}

/** A price per kWh, e.g. "₹6.50/kWh". Shows up to 4 decimals because tariffs use them. */
export function formatRate(rate: number, currency: string | null | undefined): string {
  const decimals = (String(rate).split('.')[1] ?? '').length;
  return `${currencyAmount(rate, currency, Math.min(4, Math.max(2, decimals)))}/kWh`;
}
