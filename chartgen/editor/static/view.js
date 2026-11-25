// Pure helpers of the timeline view: no DOM, tested by tests/js/view.test.mjs.

export const ZOOM_MIN = 40; // px per second
export const ZOOM_MAX = 1200;

/** The first index whose tick is >= tick, in notes sorted by tick ([tick, ...] arrays). */
export function lowerBound(notes, tick) {
  let lo = 0;
  let hi = notes.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (notes[mid][0] < tick) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/**
 * The notes to draw between two ticks. A sustain that started before the view still reaches into it, so
 * the slice starts at the first note within reach of the longest sustain.
 */
export function visibleSlice(notes, startTick, endTick, longestSustain = 0) {
  const from = lowerBound(notes, startTick - longestSustain);
  const to = lowerBound(notes, endTick + 1);
  return notes.slice(from, to);
}

export function clampZoom(pxPerSecond) {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, pxPerSecond));
}

/** The scroll position that keeps the time under the pointer in place while zooming. */
export function zoomAround(scrollLeft, pointerX, oldZoom, newZoom) {
  const seconds = (scrollLeft + pointerX) / oldZoom;
  return Math.max(0, seconds * newZoom - pointerX);
}

/** "Bar 23.3": the bar number (from 1) and the beat in it (from 1) of a tick. */
export function barBeat(tempoMap, bars, tick) {
  let bar = 0;
  for (let i = 0; i < bars.length && bars[i] <= tick; i++) bar = i;
  const signature = tempoMap.signatureAt(tick);
  const beat = Math.floor((tick - bars[bar]) / tempoMap.beatTicks(signature)) + 1;
  return { bar: bar + 1, beat };
}

/** m:ss.mmm */
export function clock(seconds) {
  const ms = Math.round(Math.max(0, seconds) * 1000);
  const minutes = Math.floor(ms / 60000);
  const rest = ((ms % 60000) / 1000).toFixed(3).padStart(6, "0");
  return `${minutes}:${rest}`;
}
