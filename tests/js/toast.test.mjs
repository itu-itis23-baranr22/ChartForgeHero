// The notifications without the page (toast.js, E.4): one per subject, a success goes by itself unless the
// pointer or the focus is on it, a warning or an error stays until it is closed.

import assert from "node:assert/strict";
import { test } from "node:test";

import { TONES, Toasts } from "../../chartgen/editor/static/toast.js";

/** A clock the test moves by hand. */
function clock() {
  let time = 0;
  let next = 1;
  const timers = new Map();
  return {
    setTimer: (run, ms) => { const id = next++; timers.set(id, { at: time + ms, run }); return id; },
    clearTimer: (id) => { timers.delete(id); },
    now: () => time,
    advance(ms) {
      time += ms;
      for (const [id, timer] of [...timers].sort((a, b) => a[1].at - b[1].at)) {
        if (timer.at > time || !timers.has(id)) continue;
        timers.delete(id);
        timer.run();
      }
    },
    pending: () => timers.size,
  };
}

const titles = (toasts) => toasts.items.map((t) => t.title);

test("three tones; a title is needed", () => {
  assert.deepEqual(TONES, ["success", "warning", "error"]);
  const toasts = new Toasts(clock());
  assert.throws(() => toasts.show({ tone: "info", title: "x" }), /unknown tone/);
  assert.throws(() => toasts.show({ tone: "error" }), /needs a title/);
});

test("a success goes by itself; one with a path to copy stays longer", () => {
  const c = clock();
  const toasts = new Toasts(c);
  toasts.show({ channel: "save", tone: "success", title: "Saved" });
  toasts.show({ channel: "copy", tone: "success", title: "Copied to game", path: "C:\\outputs\\_songs_backup\\x", pathShown: "outputs\\_songs_backup\\x" });
  c.advance(4999);
  assert.deepEqual(titles(toasts), ["Saved", "Copied to game"]);
  c.advance(1);
  assert.deepEqual(titles(toasts), ["Copied to game"]);
  c.advance(3000);
  assert.deepEqual(titles(toasts), []);
  assert.equal(c.pending(), 0);
});

test("a warning and an error stay until they are closed", () => {
  const c = clock();
  const toasts = new Toasts(c);
  const warning = toasts.show({ channel: "copy", tone: "warning", title: "Save first", actions: [{ label: "Save", run() {} }] });
  const error = toasts.show({ channel: "save", tone: "error", title: "Not saved: 1 error" });
  c.advance(60 * 60 * 1000);
  assert.deepEqual(titles(toasts), ["Save first", "Not saved: 1 error"]);
  assert.equal(c.pending(), 0);
  toasts.dismiss(warning.id);
  assert.deepEqual(titles(toasts), ["Not saved: 1 error"]);
  toasts.dismiss(error.id);
  toasts.dismiss(error.id); // twice is nothing
  assert.deepEqual(titles(toasts), []);
});

test("a new message on the same subject takes the old one's place", () => {
  const c = clock();
  const toasts = new Toasts(c);
  const refused = toasts.show({ channel: "save", tone: "error", title: "Not saved: 2 errors" });
  toasts.show({ channel: "copy", tone: "warning", title: "Save first" });
  const saved = toasts.show({ channel: "save", tone: "success", title: "Saved" });
  assert.deepEqual(titles(toasts), ["Saved", "Save first"]); // in place: nothing below it moved
  assert.equal(saved.replaces, refused.id);
  assert.equal(toasts.find(refused.id), null);
  c.advance(5000);
  assert.deepEqual(titles(toasts), ["Save first"]);
  // a success replaced before its time leaves no timer behind
  toasts.show({ channel: "save", tone: "success", title: "Saved" });
  toasts.show({ channel: "save", tone: "error", title: "Not saved: notes.chart changed on disk" });
  assert.equal(c.pending(), 0);
});

test("the pointer or the focus on a success makes it wait, then it goes after what was left", () => {
  const c = clock();
  const toasts = new Toasts(c);
  const saved = toasts.show({ channel: "save", tone: "success", title: "Saved" });
  c.advance(3000);
  toasts.pause(saved.id);
  c.advance(60 * 1000);
  assert.deepEqual(titles(toasts), ["Saved"]);
  toasts.resume(saved.id);
  c.advance(1999);
  assert.deepEqual(titles(toasts), ["Saved"]);
  c.advance(1);
  assert.deepEqual(titles(toasts), []);
});

test("at least a second is left after the pointer leaves", () => {
  const c = clock();
  const toasts = new Toasts(c);
  const saved = toasts.show({ channel: "save", tone: "success", title: "Saved" });
  c.advance(4900);
  toasts.pause(saved.id);
  toasts.resume(saved.id);
  c.advance(999);
  assert.deepEqual(titles(toasts), ["Saved"]);
  c.advance(1);
  assert.deepEqual(titles(toasts), []);
});

test("shorter times for tests apply to the next notification", () => {
  const c = clock();
  const toasts = new Toasts(c);
  toasts.durations = { success: 300, path: 600 };
  toasts.show({ channel: "save", tone: "success", title: "Saved", path: "C:\\x" });
  c.advance(599);
  assert.equal(toasts.items.length, 1);
  c.advance(1);
  assert.equal(toasts.items.length, 0);
});

test("clear closes everything and tells the page once", () => {
  const c = clock();
  const toasts = new Toasts(c);
  const seen = [];
  const stop = toasts.onChange((items) => seen.push(items.length));
  toasts.show({ channel: "save", tone: "success", title: "Saved" });
  toasts.show({ channel: "edit", tone: "warning", title: "Not changed", text: "Easy has single notes only." });
  toasts.clear();
  toasts.clear(); // nothing left: no news
  stop();
  toasts.show({ channel: "save", tone: "success", title: "Saved" });
  assert.deepEqual(seen, [1, 2, 0]);
  toasts.clear();
  assert.equal(c.pending(), 0);
});

test("pausing a warning changes nothing", () => {
  const c = clock();
  const toasts = new Toasts(c);
  const warning = toasts.show({ channel: "copy", tone: "warning", title: "Clone Hero is running" });
  toasts.pause(warning.id);
  toasts.resume(warning.id);
  toasts.pause(12345); // gone or never there
  c.advance(60 * 1000);
  assert.deepEqual(titles(toasts), ["Clone Hero is running"]);
  assert.equal(c.pending(), 0);
});

test("the shown path defaults to the path itself", () => {
  const toasts = new Toasts(clock());
  const item = toasts.show({ channel: "copy", tone: "success", title: "Copied to game", pathLabel: "In the game", path: "D:\\Songs\\A - B" });
  assert.equal(item.pathShown, "D:\\Songs\\A - B");
  assert.equal(toasts.show({ channel: "save", tone: "success", title: "Saved" }).path, null);
});
