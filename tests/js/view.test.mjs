// The timeline's pure helpers.
import assert from "node:assert/strict";
import { test } from "node:test";

import { TempoMap } from "../../chartgen/editor/static/tempo.js";
import { ZOOM_MAX, ZOOM_MIN, barBeat, clampZoom, clock, lowerBound, visibleSlice, zoomAround } from "../../chartgen/editor/static/view.js";

const notes = [[0, 0, 0, 0], [96, 1, 0, 0], [96, 2, 0, 0], [192, 0, 384, 0], [768, 3, 0, 0], [960, 4, 0, 0]];

test("lowerBound finds the first note at or after a tick", () => {
  assert.equal(lowerBound(notes, 0), 0);
  assert.equal(lowerBound(notes, 96), 1);
  assert.equal(lowerBound(notes, 97), 3);
  assert.equal(lowerBound(notes, 2000), notes.length);
});

test("the visible slice keeps a sustain that started before the view", () => {
  assert.deepEqual(visibleSlice(notes, 400, 800).map((n) => n[0]), [768]);
  // Within reach of the longest sustain the slice may hold more; drawing culls by position.
  const reaching = visibleSlice(notes, 400, 800, 384).filter((n) => n[0] + n[2] >= 400).map((n) => n[0]);
  assert.deepEqual(reaching, [192, 768]);
  assert.deepEqual(visibleSlice(notes, 96, 96).map((n) => n[1]), [1, 2]);
});

test("zoom stays in range and keeps the time under the pointer", () => {
  assert.equal(clampZoom(1), ZOOM_MIN);
  assert.equal(clampZoom(1e6), ZOOM_MAX);
  const before = (300 + 200) / 100; // seconds under the pointer at scroll 300, x 200, 100 px/s
  const scroll = zoomAround(300, 200, 100, 250);
  assert.ok(Math.abs((scroll + 200) / 250 - before) < 1e-12);
  assert.equal(zoomAround(0, 0, 100, 50), 0);
});

test("bar and beat of a tick, through a change of metre", () => {
  const map = new TempoMap(192, [[0, 120]], [[0, 2, 4], [384, 4, 4]]);
  const bars = map.barLines(10);
  assert.deepEqual(bars.slice(0, 3), [0, 384, 1152]);
  assert.deepEqual(barBeat(map, bars, 0), { bar: 1, beat: 1 });
  assert.deepEqual(barBeat(map, bars, 192), { bar: 1, beat: 2 });
  assert.deepEqual(barBeat(map, bars, 384), { bar: 2, beat: 1 });
  assert.deepEqual(barBeat(map, bars, 1151), { bar: 2, beat: 4 });
});

test("the clock never shows 60 seconds", () => {
  assert.equal(clock(0), "0:00.000");
  assert.equal(clock(59.9996), "1:00.000");
  assert.equal(clock(137.546), "2:17.546");
  assert.equal(clock(-1), "0:00.000");
});
