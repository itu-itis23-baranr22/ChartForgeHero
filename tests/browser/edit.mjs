// Drives the editor's editing in Chromium (E.2), for tests/test_editor_edit_browser.py.
//
//   node tests/browser/edit.mjs <plan.json>
//
//   smoke:  draws, selects, deletes, undoes, drags, draws a sustain, turns a cymbal into a tom, box-selects and
//           breaks a level rule on purpose; reports what the page and the chart show after each step.
//   timing: selects a note and moves it with the arrow keys, waiting for each answer; reports how long each
//           request to the server took as the browser saw it.
// The checks are in Python; this script only acts and reports.

import { readFileSync } from "node:fs";
import { chromium } from "playwright";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));

/** Console errors, page errors, failed requests and dialogs: the smoke test wants none. */
function watch(page) {
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`page: ${e.message}`));
  page.on("requestfailed", (r) => problems.push(`request: ${r.url()} ${r.failure()?.errorText}`));
  page.on("dialog", (d) => { problems.push(`dialog: ${d.message()}`); d.dismiss(); });
  return problems;
}

async function open(page) {
  await page.goto(`${plan.url}/`);
  const row = page.locator("tbody tr", { hasText: plan.title });
  await row.waitFor({ timeout: 10000 });
  await row.locator("a.open").click();
  await page.waitForFunction(() => window.chartgenDebug.state.edit && window.chartgenDebug.state.audio && window.chartgenDebug.state.audio.status !== "loading", null, { timeout: 60000 });
  await page.waitForTimeout(300);
}

const state = (page, f, arg) => page.evaluate(f, arg);

/** Brings a tick to a third of the view at a zoom, and returns the canvas box. */
async function view(page, tick, zoom) {
  await page.evaluate(([tick, zoom]) => {
    const t = window.chartgenDebug.state.timeline;
    t.zoom = zoom;
    t.scroller.querySelector(".spacer").style.width = `${t.contentWidth()}px`;
    t.scroller.scrollLeft = Math.max(0, t.tempo.secondsAt(tick) * zoom - t.width / 3);
    t.draw();
  }, [tick, zoom]);
  await page.waitForTimeout(100);
}

/** The page point of a tick and a row on the timeline. */
async function at(page, tick, row) {
  const box = await page.locator(".tl canvas").boundingBox();
  const p = await page.evaluate(([tick, row]) => {
    const t = window.chartgenDebug.state.timeline;
    return { x: t.x(t.tempo.secondsAt(tick)), y: t.rowY(row, t.layout()) };
  }, [tick, row]);
  return { x: box.x + p.x, y: box.y + p.y };
}

const version = (page) => state(page, () => window.chartgenDebug.state.edit.version);

/** Runs an action and waits for the server's answer to change the chart's version (and the live check). */
async function answered(page, action) {
  const before = await version(page);
  await action();
  await page.waitForFunction((v) => window.chartgenDebug.state.edit.version !== v, before, { timeout: 5000 });
  await page.waitForTimeout(250);
}

const notes = (page, instrument, difficulty) => state(page, ([i, d]) =>
  window.chartgenDebug.state.chart.tracks.find((t) => t.instrument === i && t.difficulty === d).notes, [instrument, difficulty]);
const selection = (page) => state(page, () => [...window.chartgenDebug.state.selection].sort());
const notice = (page) => page.locator(".tool .note").textContent();

async function smoke(page) {
  const out = {};
  const bar = plan.barTicks;
  const beat = bar / 4;
  await open(page);
  await view(page, 2 * bar, 200);

  // Draw a yellow note on bar 3, beat 2.
  await page.keyboard.press("d");
  let p = await at(page, 2 * bar + beat, 2);
  await answered(page, () => page.mouse.click(p.x, p.y));
  out.drawn = { expert: await notes(page, "guitar", "expert"), selection: await selection(page), unsaved: await page.locator(".mode").textContent() };

  // Select it, delete it, undo.
  await page.keyboard.press("v");
  await page.mouse.click(p.x, p.y);
  out.selected = await selection(page);
  await answered(page, () => page.keyboard.press("Delete"));
  out.deleted = await notes(page, "guitar", "expert");
  await answered(page, () => page.keyboard.press("Control+z"));
  out.undone = { expert: await notes(page, "guitar", "expert"), notice: await notice(page) };

  // Drag the note on bar 4, beat 1 one eighth to the right: Hard has it too and follows.
  const target = (await notes(page, "guitar", "expert")).find((n) => n[0] === 3 * bar);
  p = await at(page, target[0], target[1]);
  const q = await at(page, target[0] + beat / 2, target[1]);
  await answered(page, async () => {
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(q.x, q.y, { steps: 6 });
    await page.mouse.up();
  });
  out.dragged = {
    expert: await notes(page, "guitar", "expert"), hard: await notes(page, "guitar", "hard"), notice: await notice(page),
    flashes: await state(page, () => window.chartgenDebug.state.timeline.flashes.length),
  };

  // Draw a red sustain from bar 5, beat 2 over two beats: the note on beat 3 cuts it.
  await view(page, 4 * bar, 200);
  await page.keyboard.press("d");
  p = await at(page, 4 * bar + beat, 1);
  const end = await at(page, 4 * bar + 3 * beat, 1);
  await answered(page, async () => {
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(end.x, end.y, { steps: 6 });
    await page.mouse.up();
  });
  out.sustain = { expert: await notes(page, "guitar", "expert"), notice: await notice(page) };

  // Box-select bars 6 and 7.
  await page.keyboard.press("v");
  await view(page, 5 * bar, 200);
  const from = await at(page, 5 * bar - beat / 2, 0);
  const to = await at(page, 7 * bar - beat / 2, 4);
  await page.mouse.move(from.x, from.y - 20);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y + 20, { steps: 8 });
  await page.mouse.up();
  out.boxed = await selection(page);

  // Drums: turn the yellow cymbal of bar 2 into a tom; Hard follows.
  await page.locator('.tabs button[data-instrument="drums"]').click();
  await view(page, bar, 200);
  p = await at(page, bar, 1);
  await page.mouse.click(p.x, p.y);
  out.drumSelected = await selection(page);
  await answered(page, () => page.keyboard.press("c"));
  out.drums = { expert: await notes(page, "drums", "expert"), hard: await notes(page, "drums", "hard") };

  // A level rule broken on purpose: Other levels off, a Hard note Expert lacks.
  await page.locator('.tabs button[data-instrument="guitar"]').click();
  await page.locator(".tool .linked").click();
  out.linkedOff = await page.locator(".tool .linked").innerText();
  await page.locator('.seg button[data-level="hard"]').click();
  await view(page, 8 * bar, 200);
  await page.keyboard.press("d");
  p = await at(page, 8 * bar + beat, 3);
  await answered(page, () => page.mouse.click(p.x, p.y));
  await page.waitForTimeout(300);
  out.problemList = await page.locator(".problems").innerText();
  await answered(page, () => page.keyboard.press("Control+z"));
  await page.waitForTimeout(300);
  out.problemListAfterUndo = await page.locator(".problems h2").innerText();
  out.unsaved = await page.locator(".mode").textContent();
  out.timings = await page.evaluate(() => performance.getEntriesByType("resource")
    .filter((e) => /\/(ops|undo|redo)$/.test(e.name)).map((e) => e.responseEnd - e.startTime));
  return out;
}

async function timing(page) {
  await open(page);
  const pick = await page.evaluate(() => {
    const s = window.chartgenDebug.state;
    const track = s.chart.tracks.find((t) => t.instrument === "guitar" && t.difficulty === "expert");
    return track.notes[Math.floor(track.notes.length / 2)];
  });
  await view(page, pick[0], 300);
  const p = await at(page, pick[0], pick[1]);
  await page.mouse.click(p.x, p.y);
  for (let k = 0; k < plan.moves; k++) {
    await answered(page, () => page.keyboard.press(k < plan.moves / 2 ? "ArrowRight" : "ArrowLeft"));
  }
  const timings = await page.evaluate(() => performance.getEntriesByType("resource")
    .filter((e) => /\/ops$/.test(e.name)).map((e) => e.responseEnd - e.startTime));
  return { timings, selected: [...await selection(page)], notice: await notice(page) };
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const problems = watch(page);
  const out = plan.mode === "smoke" ? await smoke(page) : await timing(page);
  process.stdout.write(JSON.stringify({ mode: plan.mode, browser: browser.version(), problems, ...out }));
} finally {
  await browser.close();
}
