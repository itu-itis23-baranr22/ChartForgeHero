// How much memory Chromium needs for a song's audio (E.1 report, Windows): run against `chartgen edit`.
//
//   node tests/browser/memory.mjs http://127.0.0.1:8765 "Davul Testi - LastResort"
//
// Sums the private bytes of the browser's processes (Win32_Process) before the song opens, once its audio is
// decoded, and while it plays; also the decoded audio's own size (frames x channels x 4 bytes).

import { execFileSync } from "node:child_process";
import { chromium } from "playwright";

const [, , url, song] = process.argv;
if (!url || !song) {
  console.error('usage: node tests/browser/memory.mjs <editor url> "<song folder>"');
  process.exit(2);
}

function processTree(rootPid) {
  const json = execFileSync("powershell.exe", [
    "-NoProfile", "-Command",
    "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,PrivatePageCount,WorkingSetSize | ConvertTo-Json -Compress",
  ], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const all = JSON.parse(json);
  const children = new Map();
  for (const p of all) {
    if (!children.has(p.ParentProcessId)) children.set(p.ParentProcessId, []);
    children.get(p.ParentProcessId).push(p);
  }
  const tree = [];
  const walk = (pid) => {
    const self = all.find((p) => p.ProcessId === pid);
    if (self) tree.push(self);
    for (const child of children.get(pid) || []) walk(child.ProcessId);
  };
  walk(rootPid);
  return tree;
}

const mb = (bytes) => Math.round(bytes / 1048576);

function measure(rootPid, label) {
  const tree = processTree(rootPid);
  const privateBytes = tree.reduce((sum, p) => sum + Number(p.PrivatePageCount), 0);
  const largest = tree.reduce((a, b) => (Number(b.PrivatePageCount) > Number(a.PrivatePageCount) ? b : a));
  return { label, processes: tree.length, private_mb: mb(privateBytes), largest_process_private_mb: mb(Number(largest.PrivatePageCount)) };
}

// launchServer, not launch: only a server hands out the browser's process, the root of the tree to measure.
const server = await chromium.launchServer({ args: ["--autoplay-policy=no-user-gesture-required"] });
const pid = server.process().pid;
const browser = await chromium.connect(server.wsEndpoint());
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(`${url}/`);
  await page.waitForSelector("tbody tr");
  const rows = [measure(pid, "song list")];
  const started = Date.now();
  await page.goto(`${url}/#/song/${encodeURIComponent(song)}`);
  await page.waitForFunction(() => window.chartgenDebug.state.audio && window.chartgenDebug.state.audio.status !== "loading", null, { timeout: 180000 });
  const loadMs = Date.now() - started;
  const audio = await page.evaluate(() => {
    const player = window.chartgenDebug.player;
    return {
      status: window.chartgenDebug.state.audio.status,
      sampleRate: player.ctx.sampleRate,
      stems: player.stems.map((s) => ({ file: s.file, seconds: Math.round(s.buffer.duration * 10) / 10, channels: s.buffer.numberOfChannels, mb: Math.round((s.buffer.length * s.buffer.numberOfChannels * 4) / 1048576) })),
    };
  });
  rows.push(measure(pid, "audio decoded"));
  await page.keyboard.press("Space");
  await page.waitForTimeout(5000);
  rows.push(measure(pid, "after 5 s of playback"));
  await page.keyboard.press("Space");
  console.log(JSON.stringify({ song, load_ms: loadMs, audio, decoded_mb: audio.stems.reduce((s, x) => s + x.mb, 0), rows }, null, 1));
} finally {
  await browser.close();
  await server.close();
}
