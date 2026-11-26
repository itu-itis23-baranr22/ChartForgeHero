// Saving and drafts in Chromium (E.3), for tests/test_editor_save_browser.py, and Copy to game (E.4), for
// tests/test_editor_export_browser.py.
//
//   node tests/browser/save.mjs <plan.json>
//
//   save:    draw a note, Ctrl+S (a "Saved" notification that goes by itself); break a level rule and press Save
//            (an error notification that stays, sends you to Problems, and closes); undo; draw one more note and
//            wait for its draft.
//   copy:    an unsaved edit: Copy to game asks to save first and offers Save; saved, the song is copied (a new
//            song); edited, saved and copied again, the notification names the backup and Copy path copies it.
//   restore: open the song again (the editor was restarted): the draft box offers the draft; Restore.
// Screenshots go to plan.shots when given. The checks are in Python; this script only acts and reports.

import { readFileSync } from "node:fs";
import { chromium } from "playwright";

import { toastGone, toastOf } from "./toasts.mjs";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const browser = await chromium.launch();
const problems = [];
const out = { step: plan.step };
try {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: plan.url });
  const page = await context.newPage();
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
  const savedAll = () => page.waitForFunction(() => window.chartgenDebug.state.edit.unsaved === 0, null, { timeout: 5000 });
  const copied = () => page.waitForFunction(() => !window.chartgenDebug.state.copying, null, { timeout: 10000 });
  const settle = () => page.waitForTimeout(250); // past the 150 ms entrance

  if (plan.step === "save") {
    // A success goes by itself: shortened here so the test does not wait five seconds.
    await page.evaluate(() => { window.chartgenDebug.toasts.durations = { success: 1500, path: 1500 }; });
    out.saveDisabledAtFirst = await page.locator(".top .save").isDisabled();
    await page.keyboard.press("d");
    let p = await at(plan.ticks[0], 2);
    await answered(() => page.mouse.click(p.x, p.y));
    out.beforeSave = await unsaved();
    await page.keyboard.press("Control+s");
    await savedAll();
    const shownAt = Date.now(); // the notification comes with the answer
    await settle();
    out.afterSave = await unsaved();
    out.saved = await toastOf(page, "save");
    out.saveDisabledAfter = await page.locator(".top .save").isDisabled();
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e3_01_saved.png` });
    await page.mouse.move(5, 500); // not on the notification, which would make it wait
    await toastGone(page, "save", 6000);
    out.savedGoneAfterMs = Date.now() - shownAt;

    // A level rule broken on purpose: Save says how many errors, sends you to Problems, and the error stays.
    await page.locator(".tool .linked").click();
    await page.locator('.seg button[data-level="hard"]').click();
    p = await at(plan.ticks[1], 3);
    await answered(() => page.mouse.click(p.x, p.y));
    await page.waitForTimeout(300);
    await page.locator(".top .save").click();
    await settle();
    out.refused = await toastOf(page, "save");
    out.focused = await page.evaluate(() => document.activeElement && document.activeElement.closest(".problems") ? document.activeElement.textContent : null);
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e3_02_save_refused.png` });
    await page.waitForTimeout(2500); // longer than a success stays
    out.refusedStays = (await toastOf(page, "save")) !== null;
    await page.locator(".tl").focus();
    await page.locator('.toasts .toast[data-channel="save"] .acts button', { hasText: "Go to Problems" }).click();
    out.afterGoTo = {
      focused: await page.evaluate(() => document.activeElement && document.activeElement.closest(".problems") ? document.activeElement.textContent : null),
      toast: await toastOf(page, "save"),
    };
    // pressed again it says so again; the close button closes it
    await page.locator(".top .save").click();
    await settle();
    out.again = (await toastOf(page, "save")) !== null;
    await page.locator('.toasts .toast[data-channel="save"] button.close').click();
    await toastGone(page, "save");
    out.closed = (await toastOf(page, "save")) === null;
    await answered(() => page.keyboard.press("Control+z"));
    await page.locator(".tool .linked").click();
    await page.locator('.seg button[data-level="expert"]').click();

    // One more edit, left unsaved: its draft is written by the server.
    p = await at(plan.ticks[2], 2);
    await answered(() => page.mouse.click(p.x, p.y));
    out.leftUnsaved = await unsaved();
  } else if (plan.step === "copy") {
    // Copy to game: with an unsaved edit it asks to save first and offers Save; saved, it copies and says where.
    out.copyEnabledAtFirst = !(await page.locator(".top .copy").isDisabled());
    out.copyTitle = await page.locator(".top .copy").getAttribute("title");
    await page.keyboard.press("d");
    let p = await at(plan.ticks[0], 2);
    await answered(() => page.mouse.click(p.x, p.y));
    await page.locator(".top .copy").click();
    await settle();
    out.saveFirst = await toastOf(page, "copy");
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e4_05_save_first.png` });
    await page.locator('.toasts .toast[data-channel="copy"] .acts button', { hasText: "Save" }).click();
    await savedAll();
    await settle();
    out.afterSaveAction = { copy: await toastOf(page, "copy"), save: await toastOf(page, "save") };

    await page.locator(".top .copy").click();
    await copied();
    await settle();
    out.copiedNew = await toastOf(page, "copy");
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e4_01_copied_to_game.png` });

    // Edited, saved and copied again: the same audio, so only the chart goes, and the game's files are backed up.
    await page.keyboard.press("Escape");
    p = await at(plan.ticks[1], 3);
    await answered(() => page.mouse.click(p.x, p.y));
    await page.keyboard.press("Control+s");
    await savedAll();
    await page.locator(".top .copy").click();
    await copied();
    await settle();
    out.copiedAgain = await toastOf(page, "copy");
    const copyPath = page.locator('.toasts .toast[data-channel="copy"] .copy-path');
    await copyPath.hover();
    await copyPath.click();
    await page.waitForTimeout(150);
    out.copyPathLabel = await copyPath.textContent();
    out.clipboard = await page.evaluate(() => navigator.clipboard.readText());
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e4_06_copied_backup.png` });
    await page.locator(".top .theme").click();
    await page.waitForTimeout(200);
    if (plan.shots) await page.screenshot({ path: `${plan.shots}/e4_07_copied_backup_light.png` });
    out.lightStill = (await toastOf(page, "copy")) !== null; // with a path to copy, a success stays 8 s
    await page.locator(".top .theme").click();
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
