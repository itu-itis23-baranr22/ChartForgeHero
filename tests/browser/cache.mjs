// The editor after an update, in a browser that kept the old files (the E.2 cache fix), for
// tests/test_editor_cache_browser.py.
//
//   node tests/browser/cache.mjs <plan.json>
//
// The plan names a persistent profile folder (its HTTP cache survives between runs) and one step:
//   warm:   load the page, so that the browser stores its files.
//   fresh:  open a song at the given address, draw a note; report what loaded, from where, and whether the old
//           api.js is still in the cache (proof that there was something old to pick up).
//   reload: load the plain address, then reload it as F5 does; report what loaded.
//   banner: load the page and report the version warning, if any.
//   boot:   load the page and wait; report the "did not start" box, if any.
// The checks are in Python; this script only acts and reports.

import { readFileSync } from "node:fs";
import { chromium } from "playwright";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const context = await chromium.launchPersistentContext(plan.profile, { viewport: { width: 1600, height: 1000 } });
const problems = [];
const out = { step: plan.step };
try {
  const page = context.pages()[0] || await context.newPage();
  page.on("pageerror", (e) => problems.push(`page: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" && plan.step !== "boot") problems.push(`console: ${m.text()}`); });
  const scripts = () => page.evaluate(() => performance.getEntriesByType("resource")
    .filter((e) => /\.js(\?|$)/.test(e.name))
    .map((e) => ({ url: e.name.replace(location.origin, ""), network: e.transferSize > 0 })));

  if (plan.step === "warm") {
    await page.goto(`${plan.url}/`);
    await page.waitForTimeout(1500);
    out.scripts = await scripts();
  } else if (plan.step === "fresh") {
    await page.goto(`${plan.url}${plan.path}#/song/${encodeURIComponent(plan.song)}`);
    await page.waitForFunction(() => window.chartgenDebug && window.chartgenDebug.state.timeline && window.chartgenDebug.state.edit, null, { timeout: 30000 });
    await page.waitForTimeout(500);
    const p = await page.evaluate(([tick, row]) => {
      const t = window.chartgenDebug.state.timeline;
      return { x: t.x(t.tempo.secondsAt(tick)), y: t.rowY(row, t.layout()) };
    }, [plan.tick, 2]);
    const box = await page.locator(".tl canvas").boundingBox();
    await page.keyboard.press("d");
    await page.mouse.click(box.x + p.x, box.y + p.y);
    await page.waitForFunction(() => window.chartgenDebug.state.edit.unsaved === 1, null, { timeout: 5000 }).catch(() => {});
    out.unsaved = await page.locator(".mode").textContent();
    out.notice = await page.locator(".tool .note").textContent();
    out.scripts = await scripts();
    out.cachedApi = await page.evaluate(async () => {
      try {
        const r = await fetch("/api.js", { cache: "only-if-cached", mode: "same-origin" });
        return await r.text();
      } catch {
        return null;
      }
    });
  } else if (plan.step === "reload") {
    await page.goto(`${plan.url}/`);
    await page.reload();
    await page.waitForFunction(() => window.chartgenDebug, null, { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(500);
    out.scripts = await scripts();
    out.started = await page.evaluate(() => Boolean(window.chartgenDebug));
  } else if (plan.step === "banner") {
    await page.goto(`${plan.url}/`);
    await page.locator(".outdated").waitFor({ timeout: 10000 }).catch(() => {});
    out.banner = await page.locator(".outdated p").textContent().catch(() => null);
    out.button = await page.locator(".outdated .reload").textContent().catch(() => null);
  } else {
    await page.goto(`${plan.url}/`);
    await page.locator(".boot-failed").waitFor({ timeout: 10000 }).catch(() => {});
    out.box = await page.locator(".boot-failed").innerText().catch(() => null);
  }
} finally {
  await context.close();
}
out.problems = problems;
process.stdout.write(JSON.stringify(out));
