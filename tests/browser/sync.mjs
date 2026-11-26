// Measures the editor's playback in Chromium (SPEC 53, 57), driven by tests/test_editor_sync.py.
//
//   node tests/browser/sync.mjs <plan.json>
//
// The plan names the server, the song and what to do; the result is one JSON object on stdout:
//   offline: every render's onsets (seconds of the render) and the player's clock segments. The renders use
//            the editor's own modules (audio.js, tempo.js, transport.js) on an OfflineAudioContext, driven
//            through suspend points as the live page's timer drives them: play, seeks, speed changes.
//   live:    the smoke test (song list, opening the song, playing, seeking, a speed change, pausing) and
//            every drawn frame's playhead with the audio clock it came from.
// Expectations and checks are in Python, from the chart's own tempo map; this script only measures.

import { readFileSync } from "node:fs";
import { chromium } from "playwright";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const LAUNCH_ARGS = ["--autoplay-policy=no-user-gesture-required"];

/** Runs in the page: renders one case of the plan for each source and finds the clicks in each render. */
async function renderOffline({ song, files, cases, threshold, refractory }) {
  const { Player } = await import("/audio.js");
  const { TempoMap } = await import("/tempo.js");
  const { metronomeBeats } = await import("/transport.js");
  const base = `/api/songs/${encodeURIComponent(song)}`;
  const chart = await (await fetch(`${base}/chart`)).json();
  const tempo = new TempoMap(chart.resolution, chart.tempos, chart.time_signatures);
  const bytes = {};
  for (const file of files) bytes[file] = await (await fetch(`${base}/audio/${encodeURIComponent(file)}`)).arrayBuffer();

  const results = [];
  for (const plan of cases) {
    for (const source of plan.sources) {
      const length = Math.ceil(plan.seconds * plan.sampleRate);
      const ctx = new OfflineAudioContext({ numberOfChannels: 2, length, sampleRate: plan.sampleRate });
      const player = new Player(ctx);
      for (const file of files) player.addStem(file, await ctx.decodeAudioData(bytes[file].slice(0)));
      if (plan.keepPitch) {
        // E.4.1 a: the stems stretched to this speed on the server, played at full rate
        for (const [index, file] of files.entries()) {
          const slow = await (await fetch(`${base}/audio/${encodeURIComponent(file)}?keep_pitch=${plan.rate}`)).arrayBuffer();
          player.setSlow(index, plan.rate, await ctx.decodeAudioData(slow));
        }
        player.keepPitch = true;
      }
      player.stems.forEach((stem, i) => { stem.mute = stem.file !== source; });
      player.applyGains(true);
      player.setBeats(metronomeBeats(tempo, player.duration + 30));
      player.setMetronome(source === "metronome");
      player.setRate(plan.rate);

      // The live page pumps every 50 ms; here every 0.1 s of render time, and the plan's actions on top.
      const times = [];
      for (let k = 1; k * 0.1 < plan.seconds - 0.2; k++) times.push(Number((k * 0.1).toFixed(6)));
      for (const action of plan.actions) if (!times.includes(action.at)) times.push(action.at);
      times.sort((a, b) => a - b);
      const done = [];
      for (const time of times) {
        ctx.suspend(time).then(() => {
          for (const action of plan.actions.filter((a) => a.at === time)) {
            const when = action.seek !== undefined ? player.seek(action.seek) : player.setRate(action.rate);
            done.push({ ...action, planned: action.at, at: ctx.currentTime, when });
          }
          player.pump();
          ctx.resume();
        });
      }
      const started = player.play(plan.from);
      const segments = () => player.clock.segments.map((s) => ({ ...s }));
      let snapshot = [];
      // The clock keeps its last four segments; read them right before the render ends.
      ctx.suspend(Number((plan.seconds - 0.1).toFixed(6))).then(() => { snapshot = segments(); ctx.resume(); });
      const rendered = await ctx.startRendering();

      const data = rendered.getChannelData(0);
      const onsets = [];
      let lastLoud = -Infinity;
      const gap = Math.round(refractory * plan.sampleRate);
      for (let i = 0; i < data.length; i++) {
        const loud = Math.abs(data[i]) >= threshold;
        if (loud && i - lastLoud > gap) onsets.push(i / plan.sampleRate);
        if (loud) lastLoud = i;
      }
      results.push({
        name: plan.name, source, sampleRate: rendered.sampleRate, rate: plan.rate, seconds: plan.seconds,
        started, actions: done, segments: snapshot, onsets, durations: Object.fromEntries(player.stems.map((s) => [s.file, s.buffer.duration])),
      });
    }
  }
  return results;
}

async function offline(browser) {
  const page = await browser.newPage();
  const problems = watch(page);
  await page.goto(`${plan.url}/`);
  const results = await page.evaluate(renderOffline, {
    song: plan.song, files: plan.files, cases: plan.cases, threshold: plan.threshold, refractory: plan.refractory,
  });
  return { results, problems };
}

async function live(browser) {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const problems = watch(page);
  const steps = [];
  await page.goto(`${plan.url}/`);
  const row = page.locator("tbody tr", { hasText: plan.title });
  await row.waitFor({ timeout: 10000 });
  steps.push("song list shows the song");
  await row.locator("a.open").click();
  await page.waitForFunction(() => window.chartgenDebug.state.audio && window.chartgenDebug.state.audio.status !== "loading", null, { timeout: 60000 });
  const audio = await page.evaluate(() => ({ ...window.chartgenDebug.state.audio }));
  steps.push(`audio ${audio.status}: ${audio.loaded} of ${audio.total} files`);
  if (audio.status !== "ready") return { problems, steps, audio };

  await page.evaluate(() => { window.chartgenDebug.frames = []; });
  await page.locator(".bot .metro[aria-pressed='false']").click().catch(() => {});
  await page.keyboard.press("Space");
  await page.waitForTimeout(plan.liveSeconds * 1000);
  steps.push(`playing after Space: ${await page.evaluate(() => window.chartgenDebug.player.playing)}`);
  const box = await page.locator(".tl canvas").boundingBox();
  await page.mouse.click(box.x + box.width * 0.7, box.y + 40); // the ruler: seek
  await page.waitForTimeout(plan.liveSeconds * 1000);
  await page.selectOption(".bot .speed", "0.5");
  await page.waitForTimeout(plan.liveSeconds * 1000);
  const measured = await page.evaluate(() => {
    const player = window.chartgenDebug.player;
    return {
      segments: player.clock.segments.map((s) => ({ ...s })),
      frames: window.chartgenDebug.frames,
      sampleRate: player.ctx.sampleRate,
      baseLatency: player.ctx.baseLatency,
      outputLatency: player.ctx.outputLatency,
    };
  });
  await page.locator(".bot .play").click();
  const after = await page.evaluate(() => ({
    playing: window.chartgenDebug.player.playing,
    cursor: window.chartgenDebug.player.cursor,
    clock: document.querySelector(".clock .t").textContent,
  }));
  steps.push(`paused by the play button: ${!after.playing}, clock ${after.clock}`);
  return { problems, steps, audio, ...measured, after };
}

/** Console errors, page errors and failed requests: the smoke test wants none. */
function watch(page) {
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`page: ${e.message}`));
  page.on("requestfailed", (r) => problems.push(`request: ${r.url()} ${r.failure()?.errorText}`));
  return problems;
}

const browser = await chromium.launch({ args: LAUNCH_ARGS });
try {
  const out = { mode: plan.mode, browser: browser.version() };
  Object.assign(out, plan.mode === "offline" ? await offline(browser) : await live(browser));
  process.stdout.write(JSON.stringify(out));
} finally {
  await browser.close();
}
