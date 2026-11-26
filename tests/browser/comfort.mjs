// The comfort features of E.4.1 in Chromium, for tests/test_editor_comfort_browser.py: triplet grids, the
// keyboard alone (select, move the playhead, add), sections, star power and the preview, and Keep pitch.
//
//   node tests/browser/comfort.mjs <plan.json>
//
// The checks are in Python; this script only acts and reports. Screenshots go to plan.shots when given.

import { readFileSync } from "node:fs";
import { chromium } from "playwright";

import { toastOf } from "./toasts.mjs";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const browser = await chromium.launch();
const problems = [];
const out = {};
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.on("pageerror", (e) => problems.push(`page: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  await page.goto(`${plan.url}/#/song/${encodeURIComponent(plan.song)}`);
  await page.waitForFunction(() => window.chartgenDebug.state.timeline && window.chartgenDebug.state.edit
    && window.chartgenDebug.state.audio.status === "ready", null, { timeout: 30000 });
  await page.waitForTimeout(300);
  const s = (f) => page.evaluate(f);
  const version = () => s(() => window.chartgenDebug.state.edit.version);
  const notice = () => page.locator(".tool .note").textContent();
  const answered = async (action) => {
    const before = await version();
    await action();
    await page.waitForFunction((v) => window.chartgenDebug.state.edit.version !== v, before, { timeout: 8000 });
    await page.waitForTimeout(250);
  };

  // E.4.0 without a Songs folder: Copy to game looks passive and says why when clicked
  out.copyMissing = await page.locator(".top .copy").evaluate((b) => b.classList.contains("missing") && b.getAttribute("aria-disabled") === "true");
  await page.locator(".top .copy").click({ force: true }); // a real click reaches it; Playwright waits for aria-disabled
  await page.waitForTimeout(250);
  out.copyNotice = await toastOf(page, "copy");

  // c) triplet grids
  out.grids = await page.locator(".tool .grid option").allTextContents();
  await page.selectOption(".tool .grid", "12");

  // b) the keyboard alone: focus the timeline, select with . and ,, move the playhead, add with a number
  await page.locator(".tl").focus();
  await page.keyboard.press(".");
  out.firstNext = await s(() => [...window.chartgenDebug.state.selection]);
  await page.keyboard.press(".");
  out.secondNext = await s(() => [...window.chartgenDebug.state.selection]);
  await page.keyboard.press(",");
  out.back = await s(() => [...window.chartgenDebug.state.selection]);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Control+ArrowRight");
  await page.keyboard.press("Control+ArrowRight");
  out.playheadTick = await s(() => Math.round(window.chartgenDebug.state.tempo.ticksAt(window.chartgenDebug.state.playhead)));
  await answered(() => page.keyboard.press("2"));
  out.added = await s(() => window.chartgenDebug.state.chart.tracks.find((t) => t.instrument === "guitar" && t.difficulty === "expert").notes
    .filter((n) => window.chartgenDebug.state.selection.has(`${n[0]}:${n[1]}`)));
  if (plan.shots) await page.screenshot({ path: `${plan.shots}/e4_02_keyboard_and_triplets.png` });

  // d) a section, star power and the preview, on the bar the playhead is in: bar 3 (bar 1 has the Intro)
  const box = await page.locator(".tl canvas").boundingBox();
  const x3 = await page.evaluate((tick) => { const t = window.chartgenDebug.state.timeline; return t.x(t.tempo.secondsAt(tick)); }, plan.bar3 + 96);
  await page.mouse.click(box.x + x3, box.y + 20); // the ruler: moves the playhead
  await answered(() => page.locator(".right .add-section").click());
  out.focusedName = await s(() => document.activeElement && document.activeElement.classList.contains("sec-name"));
  await page.keyboard.press("Control+a");
  await page.keyboard.type("Verse");
  await answered(() => page.keyboard.press("Enter"));
  out.sections = await s(() => window.chartgenDebug.state.chart.sections);
  await answered(() => page.locator(".right .add-sp").click());
  out.starPower = await s(() => window.chartgenDebug.state.chart.tracks.filter((t) => t.instrument === "guitar").map((t) => [t.difficulty, t.star_power]));
  await answered(() => page.locator(".right .set-preview").click());
  out.preview = await s(() => window.chartgenDebug.state.info.preview_s);
  out.facts = await page.locator(".facts").innerText();
  // select the new section on the ruler and look at the inspector
  const sectionBox = await page.evaluate((tick) => window.chartgenDebug.state.timeline.structureBoxes.find((b) => b.kind === "section" && b.tick === tick), plan.bar3);
  await page.mouse.click(box.x + (sectionBox.x0 + sectionBox.x1) / 2, box.y + (sectionBox.y0 + sectionBox.y1) / 2);
  await page.waitForTimeout(150);
  out.selectedStructure = await s(() => window.chartgenDebug.state.structure);
  out.inspector = await page.locator(".inspector").innerText();
  if (plan.shots) await page.screenshot({ path: `${plan.shots}/e4_03_structure.png` });
  await page.locator(".tl").focus();
  await answered(() => page.keyboard.press("Delete"));
  out.afterDelete = await s(() => window.chartgenDebug.state.chart.sections);

  // a) keep pitch: on, then 0.75x; the stems are stretched on the server and swapped in
  await page.locator(".bot .pitch").click();
  await page.selectOption(".bot .speed", "0.75");
  await page.waitForFunction(() => window.chartgenDebug.player.keepPitch === true, null, { timeout: 60000 });
  await page.waitForTimeout(200);
  out.keepPitch = { on: await s(() => window.chartgenDebug.player.keepPitch), notice: await notice(),
    slow: await s(() => window.chartgenDebug.player.stems.map((st) => st.slow && st.slow.speed)) };
  if (plan.shots) await page.screenshot({ path: `${plan.shots}/e4_04_keep_pitch.png`, clip: { x: 0, y: 860, width: 1600, height: 140 } });
} finally {
  await browser.close();
}
out.problems = problems;
process.stdout.write(JSON.stringify(out));
