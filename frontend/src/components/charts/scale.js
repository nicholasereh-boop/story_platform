// Small pure helpers for the SVG line chart.

// Round a maximum UP to a "nice" number (1, 2, 5 times a power of ten) so the axis labels are tidy.
export function niceMax(value) {
  if (!(value > 0)) return 1;
  const exp = 10 ** Math.floor(Math.log10(value));
  const f = value / exp;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * exp;
}

// Evenly spaced y-axis values from 0 to max, e.g. [0, 25, 50, 75, 100].
export const yTicks = (max, count = 4) => Array.from({ length: count + 1 }, (_, i) => (max * i) / count);

// x position of each of n points between left and right (a single point sits in the middle).
export function xPositions(n, left, right) {
  if (n <= 1) return n === 1 ? [(left + right) / 2] : [];
  return Array.from({ length: n }, (_, i) => left + ((right - left) * i) / (n - 1));
}

// Which points get a text label on the x axis: first and last always, the rest evenly spread. At most `max` labels.
export function labelIndexes(n, max = 6) {
  if (n <= max) return Array.from({ length: n }, (_, i) => i);
  const picked = new Set([0, n - 1]);
  for (let i = 1; i < max - 1; i += 1) picked.add(Math.round((i * (n - 1)) / (max - 1)));
  return [...picked].sort((a, b) => a - b);
}
