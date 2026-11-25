// Saving and drafts in Chromium (E.3), for tests/test_editor_save_browser.py.
//
//   node tests/browser/save.mjs <plan.json>
//
//   save:    draw a note, Ctrl+S; break a level rule and press Save (it must send you to Problems), undo; draw
//            one more note and wait for its draft.
//   restore: open the song again (the editor was restarted): the draft box offers the draft; Restore.
// Screenshots go to plan.shots when given. The checks are in Python; this script only acts and reports.

import { readFileSync } from "node:fs";
import { chromium } from "playwright";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const browser = await chromium.launch();
const problems = [];
const out = { step: plan.step };
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.on("pageerror", (e) => problems.push(`page: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  page.on("dialog", (d) => { problems.push(`dialog: ${d.message()}`); d.dismiss(); });
  await page.goto(`${plan.url}/#/song/${encodeURIComponent(plan.song)}`);
  await page.waitForFunction(() => window.chartgenDebug.state.timeline && window.chartgenDebug.state.edit
    && window.chartgenDebug.state.audio.status !== "loading", null, { timeout: 30000 });
  await page.waitForTimeout(400);
  const version = () => page.evaluate(() => window.chartgenDebug.state.edit.version);
  const unsaved = () => page.locator(".mode").textContent();
  const notice = () => page.locator(".tool .note").textContent();
  const at = async (tick, row) => {
    const box = await page.locator(".tl canvas").boundingBox();
    const p = await page.evaluate(([tick, row]) => {
      const t = window.chartgenDebug.state.timeline;
      t.scroller.scrollLeft = Math.max(0, t.tempo.secondsAt(tick) * t.zoom - t.width / 3);
      t.draw();
      return { x: t.x(t.tempo.secondsAt(tick)), y: t.rowY(row, t.layout()) };
    }, [tick, row]);
    return { x: box.x + p.x, y: box.y + p.y };
  };
  const answered = async (action) => {
    const before = await version();
    await action();
    await page.waitForFunction((v) => window.chartgenDebug.state.edit.version !== v, before, { timeout: 5000 });
    await page.waitForTimeout(300);
  };

  if (plan.step === "save") {
    out.saveDisabledAtFirst = await page.locator(".top .save").isDisabled();
    await page.keyboard.press("d");
    let p = await at(plan.ticks[0], 2);
    await answered(() => page.mouse.click(p.x, p.y));
    out.beforeSave = await unsaved();
    await page.keyboard.press("Control+s");
    await page.waitForFunction(() => window.chartgenDebug.state.edit.unsaved === 0, null, { timeout: 5000 });
    out.afterSave = await unsaved();
    out.savedNotice = await notice();
    out.saveDisabledAfter = await page.locator(".top .save").isDisabled();
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e3_01_saved.png` });

    // A level rule broken on purpose: Save says how many errors and sends you to Problems.
    await page.locator(".tool .linked").click();
    await page.locator('.seg button[data-level="hard"]').click();
    p = await at(plan.ticks[1], 3);
    await answered(() => page.mouse.click(p.x, p.y));
    await page.waitForTimeout(300);
    await page.locator(".top .save").click();
    await page.waitForTimeout(200);
    out.refusedNotice = await notice();
    out.focused = await page.evaluate(() => document.activeElement && document.activeElement.closest(".problems") ? document.activeElement.textContent : null);
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e3_02_save_refused.png` });
    await answered(() => page.keyboard.press("Control+z"));
    await page.locator(".tool .linked").click();
    await page.locator('.seg button[data-level="expert"]').click();

    // One more edit, left unsaved: its draft is written by the server.
    p = await at(plan.ticks[2], 2);
    await answered(() => page.mouse.click(p.x, p.y));
    out.leftUnsaved = await unsaved();
  } else {
    await page.locator("#drafts .restore").waitFor({ timeout: 5000 });
    out.offer = await page.locator("#drafts").innerText();
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e3_03_draft_offer.png` });
    await answered(() => page.locator("#drafts .restore").click());
    out.afterRestore = await unsaved();
    out.restoredNotice = await notice();
    out.boxGone = (await page.locator("#drafts").count()) === 0;
    out.notes = await page.evaluate(() => window.chartgenDebug.state.chart.tracks
      .find((t) => t.instrument === "guitar" && t.difficulty === "expert").notes);
  }
} finally {
  await browser.close();
}
out.problems = problems;
process.stdout.write(JSON.stringify(out));
