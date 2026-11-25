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

/** A level and an instrument the song lacks: passive, with words on hover and on a click (owner, 2026-11-25). */
async function levels(page) {
  await open(page);
  const out = {};
  const describe = (locator) => locator.evaluate((b) => ({
    ariaDisabled: b.getAttribute("aria-disabled"), title: b.getAttribute("title"), disabled: b.disabled,
    opacity: getComputedStyle(b).opacity, cursor: getComputedStyle(b).cursor,
  }));
  const where = () => page.evaluate(() => ({ instrument: window.chartgenDebug.state.instrument, level: window.chartgenDebug.state.difficulty }));
  const medium = page.locator('.seg button[data-level="medium"]');
  out.medium = await describe(medium);
  out.hard = await describe(page.locator('.seg button[data-level="hard"]'));
  await medium.click({ force: true }); // a real click reaches it; Playwright waits for aria-disabled
  out.afterMedium = { notice: await notice(page), ...(await where()) };
  const keys = page.locator('.tabs button[data-instrument="keys"]');
  out.keys = await describe(keys);
  await keys.click({ force: true });
  out.afterKeys = { notice: await notice(page), ...(await where()) };
  await page.locator('.seg button[data-level="hard"]').click();
  out.afterHard = await where();
  return out;
}

async function timing(page) {
  await open(page);
  // From the middle on: a single note on the 1/8 grid (the default) whose next eighth on its lane is free. It
  // then goes right and back left in turn: the way back is the place it left, so no chart can block a move,
  // whatever edits the folder holds.
  const pick = await page.evaluate(() => {
    const s = window.chartgenDebug.state;
    const notes = s.chart.tracks.find((t) => t.instrument === "guitar" && t.difficulty === "expert").notes;
    const step = s.chart.resolution / 2;
    const taken = new Set(notes.map((n) => `${n[0]}:${n[1]}`));
    const chord = (tick) => notes.filter((n) => n[0] === tick).length > 1;
    const barStart = (tick) => s.bars.filter((b) => b <= tick).at(-1) ?? 0;
    for (let i = Math.floor(notes.length / 2); i < notes.length; i++) {
      const n = notes[i];
      if (n[1] < 5 && (n[0] - barStart(n[0])) % step === 0 && !taken.has(`${n[0] + step}:${n[1]}`) && !chord(n[0])) return n;
    }
    return null;
  });
  if (!pick) throw new Error("no note to move in Expert guitar");
  await view(page, pick[0], 300);
  const p = await at(page, pick[0], pick[1]);
  await page.mouse.click(p.x, p.y);
  for (let k = 0; k < plan.moves; k++) {
    await answered(page, () => page.keyboard.press(k % 2 === 0 ? "ArrowRight" : "ArrowLeft"));
  }
  const timings = await page.evaluate(() => performance.getEntriesByType("resource")
    .filter((e) => /\/ops$/.test(e.name)).map((e) => e.responseEnd - e.startTime));
  return { timings, selected: [...await selection(page)], notice: await notice(page) };
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const problems = watch(page);
  const out = plan.mode === "smoke" ? await smoke(page) : plan.mode === "levels" ? await levels(page) : await timing(page);
  process.stdout.write(JSON.stringify({ mode: plan.mode, browser: browser.version(), problems, ...out }));
} finally {
  await browser.close();
}
