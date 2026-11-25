// The editor's editing helpers (E.2): grid, rows, selection, clipboard and the tool row's words.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CYMBAL, DRUM_ROWS, FORCED, cascadeSummary, clipboardOf, flagTarget, gridTicks, laneOfRow, noteKey, notesInBox,
  parseKey, pasteAt, rowOf, selectedNotes, snapTick, stepTick, unsavedLabel,
} from "../../chartgen/editor/static/edit.js";

test("a grid step is a fraction of a whole note", () => {
  assert.equal(gridTicks(192, 4), 192);
  assert.equal(gridTicks(192, 8), 96);
  assert.equal(gridTicks(192, 16), 48);
  assert.equal(gridTicks(480, 16), 120);
});

test("snapping counts the grid from the bar, so an odd bar does not shift the next one", () => {
  // 4/4 from 0 (768 ticks a bar), then 7/8 from 1536 (672 ticks), then 4/4 again from 2208.
  const bars = [0, 768, 1536, 2208, 2976];
  assert.equal(snapTick(bars, 100, 96), 96);
  assert.equal(snapTick(bars, 140, 96), 96);
  assert.equal(snapTick(bars, 150, 96), 192);
  // In the 7/8 bar a 1/4 grid falls on 1536, 1728, 1920, 2112 and the next bar line 2208.
  assert.equal(snapTick(bars, 2150, 192), 2112);
  assert.equal(snapTick(bars, 2170, 192), 2208);
  assert.equal(snapTick(bars, 2210, 192), 2208);
  assert.equal(snapTick(bars, 2208 + 200, 192), 2208 + 192);
  assert.equal(snapTick(bars, 0, 48), 0);
});

test("a step goes to the next grid point that way, also from between two points", () => {
  const bars = [0, 768, 1536];
  assert.equal(stepTick(bars, 96, 96, 1), 192);
  assert.equal(stepTick(bars, 96, 96, -1), 0);
  assert.equal(stepTick(bars, 120, 96, 1), 192);
  assert.equal(stepTick(bars, 120, 96, -1), 96);
  assert.equal(stepTick(bars, 0, 96, -1), 0);
});

test("rows follow the screen: frets top to bottom, drums red to green then the kick", () => {
  assert.deepEqual(DRUM_ROWS, [1, 2, 3, 4, 0]);
  for (let lane = 0; lane < 5; lane++) {
    assert.equal(laneOfRow(false, rowOf(false, lane)), lane);
    assert.equal(laneOfRow(true, rowOf(true, lane)), lane);
  }
  assert.equal(rowOf(true, 0), 4);
  assert.equal(rowOf(false, 5), null);
  assert.equal(laneOfRow(false, 5), null);
  assert.equal(laneOfRow(true, -1), null);
});

test("a box takes the notes inside its ticks and rows, an open note in any row", () => {
  const notes = [[96, 0, 0, 0], [96, 3, 0, 0], [192, 1, 0, 0], [288, 5, 0, 0], [384, 2, 0, 0]];
  assert.deepEqual(notesInBox(notes, 90, 300, 1, 3, false), ["96:3", "192:1", "288:5"]);
  assert.deepEqual(notesInBox([[96, 0, 0, 0], [96, 2, 0, CYMBAL]], 0, 100, 4, 4, true), ["96:0"]);
});

test("keys, selections and flags", () => {
  assert.equal(noteKey([96, 3, 0, 0]), "96:3");
  assert.deepEqual(parseKey("96:3"), [96, 3]);
  const track = { notes: [[96, 0, 0, 0], [96, 1, 0, FORCED], [192, 2, 0, FORCED]] };
  const selection = new Set(["96:1", "192:2"]);
  assert.deepEqual(selectedNotes(track, selection), [[96, 1, 0, FORCED], [192, 2, 0, FORCED]]);
  assert.equal(flagTarget(selectedNotes(track, selection), FORCED), false);
  assert.equal(flagTarget(track.notes, FORCED), true);
});

test("the clipboard keeps notes relative to the first and pastes them anywhere", () => {
  const clip = clipboardOf("guitar", [[960, 1, 96, 0], [1056, 2, 0, FORCED]]);
  assert.deepEqual(clip, { instrument: "guitar", notes: [[0, 1, 96, 0], [96, 2, 0, FORCED]] });
  assert.deepEqual(pasteAt(clip, 3072), [[3072, 1, 96, 0], [3168, 2, 0, FORCED]]);
});

test("the tool row's words", () => {
  assert.equal(unsavedLabel(0), "No unsaved edits");
  assert.equal(unsavedLabel(1), "1 unsaved edit");
  assert.equal(unsavedLabel(4), "4 unsaved edits");
  assert.equal(cascadeSummary([]), "");
  assert.equal(
    cascadeSummary([
      { difficulty: "medium", tick: 0, lane: 1, change: "removed" },
      { difficulty: "hard", tick: 0, lane: 1, change: "removed" },
      { difficulty: "hard", tick: 0, lane: 2, change: "removed" },
    ]),
    "Also changed: Hard 2 notes, Medium 1 note",
  );
});
