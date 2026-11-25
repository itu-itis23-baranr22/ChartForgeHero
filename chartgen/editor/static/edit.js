// Pure helpers of editing (E.2): the grid, rows and lanes, selections, the clipboard and the words the tool
// row shows. No DOM; tested by tests/js/edit.test.mjs. The edits themselves happen on the server (SPEC 50).

export const FORCED = 1;
export const TAP = 2;
export const CYMBAL = 4;
export const OPEN_LANE = 5;
export const GRIDS = [4, 8, 16];
export const LEVELS = ["expert", "hard", "medium", "easy"];

/** Drum lanes in the rows on screen, top to bottom: red, yellow, blue, green, then the kick (as ops.DRUM_ROWS). */
export const DRUM_ROWS = [1, 2, 3, 4, 0];

/** Ticks of one grid step: 1/4 is a quarter note, whatever the time signature. */
export function gridTicks(resolution, division) {
  return (resolution * 4) / division;
}

function lastAtOrBefore(values, x) {
  let lo = 0;
  let hi = values.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (values[mid] <= x) lo = mid + 1;
    else hi = mid;
  }
  return lo - 1;
}

/**
 * The grid point nearest to a tick. The grid is counted from the start of the tick's bar, so a bar of 7/8
 * does not shift the grid of the bars after it, and no point passes the next bar line.
 */
export function snapTick(bars, tick, step) {
  const i = Math.max(0, lastAtOrBefore(bars, tick));
  const start = bars.length ? bars[i] : 0;
  const next = i + 1 < bars.length ? bars[i + 1] : Infinity;
  const k = (tick - start) / step;
  const below = start + Math.floor(k) * step;
  const above = Math.min(next, start + Math.ceil(k) * step); // the next bar line is a grid point too
  const snapped = tick - below <= above - tick ? below : above;
  return Math.max(0, Math.round(snapped));
}

/** Where a note goes one grid step earlier (direction -1) or later (+1): the next grid point that way. */
export function stepTick(bars, tick, step, direction) {
  const snapped = snapTick(bars, tick, step);
  if (direction > 0 ? snapped > tick : snapped < tick) return snapped;
  return snapTick(bars, Math.max(0, tick + direction * step), step);
}

/** The row a lane is drawn in (0 at the top), or null for an open note, which spans them all. */
export function rowOf(drums, lane) {
  if (drums) return DRUM_ROWS.indexOf(lane);
  return lane === OPEN_LANE ? null : lane;
}

/** The lane of a row; null outside the rows. */
export function laneOfRow(drums, row) {
  if (row === null || row < 0 || row > 4) return null;
  return drums ? DRUM_ROWS[row] : row;
}

export const keyOf = (tick, lane) => `${tick}:${lane}`;
export const noteKey = (note) => keyOf(note[0], note[1]);

export function parseKey(key) {
  const [tick, lane] = key.split(":").map(Number);
  return [tick, lane];
}

/** The keys of the notes inside a box of ticks and rows; an open note counts in every row. */
export function notesInBox(notes, tickFrom, tickTo, rowFrom, rowTo, drums) {
  const keys = [];
  for (const n of notes) {
    if (n[0] < tickFrom || n[0] > tickTo) continue;
    const row = rowOf(drums, n[1]);
    if (row === null || (row >= rowFrom && row <= rowTo)) keys.push(noteKey(n));
  }
  return keys;
}

/** The selected notes of a track, in its order. */
export function selectedNotes(track, selection) {
  return track ? track.notes.filter((n) => selection.has(noteKey(n))) : [];
}

/** What a flag key does to a selection: turns the flag on unless every note has it already. */
export function flagTarget(notes, bit) {
  return !notes.every((n) => n[3] & bit);
}

/** A copy of notes, kept relative to the first one's tick. */
export function clipboardOf(instrument, notes) {
  const first = Math.min(...notes.map((n) => n[0]));
  return { instrument, notes: notes.map((n) => [n[0] - first, n[1], n[2], n[3]]) };
}

/** The clipboard's notes placed with its first note at a tick. */
export function pasteAt(clipboard, tick) {
  return clipboard.notes.map((n) => [n[0] + tick, n[1], n[2], n[3]]);
}

export function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function unsavedLabel(count) {
  return count ? `${plural(count, "unsaved edit")}` : "No unsaved edits";
}

/** "Also changed: Hard 2 notes, Medium 1 note" for the notes an edit changed on other levels. */
export function cascadeSummary(cascaded) {
  if (!cascaded || !cascaded.length) return "";
  const counts = new Map();
  for (const c of cascaded) counts.set(c.difficulty, (counts.get(c.difficulty) || 0) + 1);
  const parts = LEVELS.filter((l) => counts.has(l)).map((l) => `${l[0].toUpperCase()}${l.slice(1)} ${plural(counts.get(l), "note")}`);
  return `Also changed: ${parts.join(", ")}`;
}
