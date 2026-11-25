// chartgen editor (E.1: read-only, with playback). Two views behind the hash: #/ the song list,
// #/song/<folder> a song.

import { api } from "./api.js";
import { PUMP_MS, Player } from "./audio.js";
import { icon } from "./icons.js";
import { TempoMap } from "./tempo.js";
import { PAD, Timeline } from "./timeline.js";
import { SPEEDS, clampLatency, followScroll, metronomeBeats, peaks, silencedBySolo } from "./transport.js";
import { barBeat, clampZoom, clock, zoomAround } from "./view.js";

const INSTRUMENTS = ["guitar", "bass", "drums", "keys"];
const LEVELS = ["expert", "hard", "medium", "easy"];
const TITLE = { guitar: "Guitar", bass: "Bass", drums: "Drums", keys: "Keys", expert: "Expert", hard: "Hard", medium: "Medium", easy: "Easy" };
const FRETS = ["Green", "Red", "Yellow", "Blue", "Orange"];
const DRUM_LANES = [["Red", 1], ["Yellow", 2], ["Blue", 3], ["Green", 0]]; // name, colour class
const DRUM_NAMES = { 0: "Kick", 1: "Red", 2: "Yellow", 3: "Blue", 4: "Green" };
const root = document.getElementById("app");

const esc = (value) => String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

// ---------------------------------------------------------------- per-viewer conveniences

function stored(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function store(key, value) {
  try { localStorage.setItem(key, String(value)); } catch { /* private window: the choice lasts this page */ }
}

function storedTheme() {
  return stored("chartgen-theme");
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next);
  store("chartgen-theme", next);
  if (state.timeline) {
    state.timeline.readColours();
    state.timeline.draw();
  }
  renderThemeButton();
}

function renderThemeButton() {
  const button = document.querySelector(".theme");
  if (!button) return;
  const light = document.documentElement.dataset.theme === "light";
  button.innerHTML = icon(light ? "moon" : "sun");
  button.title = light ? "Dark theme" : "Light theme";
  button.setAttribute("aria-label", button.title);
}

applyTheme(storedTheme());

// ---------------------------------------------------------------- shell

const state = {};

/** Read by the measurement scripts in tests/browser: the open song's state and its player. */
window.chartgenDebug = {
  get state() { return state; },
  get player() { return state.player || null; },
  frames: null, // an array to record every drawn playhead into, or null
};

function header(inner) {
  return `<header class="top">${inner}<div class="end"><span class="mode"></span><button class="theme"></button></div></header>`;
}

function wireHeader() {
  document.querySelector(".theme").addEventListener("click", toggleTheme);
  renderThemeButton();
}

function route() {
  closeAudio();
  const match = location.hash.match(/^#\/song\/(.+)$/);
  if (match) openSong(decodeURIComponent(match[1]));
  else showList();
}

window.addEventListener("hashchange", route);
route();

// ---------------------------------------------------------------- song list

async function showList() {
  state.timeline = null;
  document.title = "chartgen editor";
  root.className = "app list-view";
  root.innerHTML = header('<div class="brand">chartgen</div><span>Editor</span>') + '<main class="list"><p class="loading">Loading the songs…</p></main>';
  wireHeader();
  const main = root.querySelector(".list");
  let data;
  try {
    data = await api.songs();
  } catch (error) {
    main.innerHTML = `<div class="empty"><h1>The songs could not be listed</h1><p>${esc(error.message)}</p></div>`;
    return;
  }
  if (!data.songs.length) {
    main.innerHTML = `<div class="empty"><h1>No song folders yet</h1>
      <p>The editor opens the folders that <span class="num">chartgen build</span> writes. Build one, then reload this page.</p>
      <ol><li>Build a song from an audio file you own:<br><code>chartgen build song.mp3 --artist "Artist" --title "Title"</code></li>
      <li>It appears here as <span class="num">Artist - Title</span>. Open it to see the chart.</li></ol>
      <p>Looking in <span class="num">${esc(data.root)}</span></p></div>`;
    return;
  }
  const rows = data.songs.map((s) => {
    const badges = INSTRUMENTS.map((i) => `<span class="${s.instruments.includes(i) ? "" : "off"}" title="${TITLE[i]}${s.instruments.includes(i) ? "" : ": no chart"}">${TITLE[i][0]}</span>`).join("");
    const status = s.edited ? '<span class="st ed">Edited</span>' : '<span class="st">Unedited</span>';
    return `<tr><td><div class="t">${esc(s.name)}</div><div class="a">${esc(s.artist)}</div></td>
      <td><div class="inst">${badges}</div></td><td class="num">${s.length_s ? clock(s.length_s).replace(/\.\d+$/, "") : "–"}</td>
      <td>${status}</td><td class="act"><a class="open" href="#/song/${encodeURIComponent(s.id)}">Open</a></td></tr>`;
  }).join("");
  main.innerHTML = `<h1>Songs</h1><p class="sub">Song folders in <span class="num">${esc(data.root)}</span>, built by chartgen.</p>
    <table><thead><tr><th>Song</th><th>Charts</th><th>Length</th><th>State</th><th><span hidden>Open</span></th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ---------------------------------------------------------------- one song

async function openSong(id) {
  root.className = "app";
  root.innerHTML = header(`<div class="brand"><a class="back" href="#/" title="All songs" aria-label="All songs">${icon("back")}</a>chartgen</div>`) +
    '<p class="loading full">Opening the song…</p>';
  wireHeader();
  let chart;
  let info;
  try {
    [chart, info] = await Promise.all([api.chart(id), api.info(id)]);
  } catch (error) {
    root.className = "app list-view";
    root.innerHTML = header(`<div class="brand"><a class="back" href="#/" title="All songs" aria-label="All songs">${icon("back")}</a>chartgen</div>`) +
      `<main class="list"><div class="empty"><h1>This song cannot be opened</h1><p>${esc(error.message)}</p><p><a class="open" href="#/">Back to the songs</a></p></div></main>`;
    wireHeader();
    return;
  }
  const tempo = new TempoMap(chart.resolution, chart.tempos, chart.time_signatures);
  const lastTick = Math.max(0, ...chart.tracks.flatMap((t) => t.notes.map((n) => n[0] + n[2])));
  const lengthS = Math.max(info.length_s || 0, tempo.secondsAt(lastTick) + 1);
  const instruments = INSTRUMENTS.filter((i) => chart.tracks.some((t) => t.instrument === i));
  Object.assign(state, {
    id, chart, info, tempo, lengthS, bars: tempo.barLines(lengthS), instruments,
    instrument: instruments[0], difficulty: null, selected: null, showBelow: true,
    playhead: 0, rate: 1, metronome: stored("chartgen-metronome") === "on",
    latency: clampLatency(stored("chartgen-latency-ms") ?? 0), audio: { status: "loading", loaded: 0, total: info.audio.length },
  });
  state.difficulty = levelsOf(state.instrument)[0];
  document.title = `${chart.name} – chartgen editor`;
  renderSong();
  loadAudio(id);
}

function levelsOf(instrument) {
  return LEVELS.filter((l) => state.chart.tracks.some((t) => t.instrument === instrument && t.difficulty === l));
}

function trackOf(instrument, difficulty) {
  return state.chart.tracks.find((t) => t.instrument === instrument && t.difficulty === difficulty) || null;
}

function belowLevel() {
  const levels = levelsOf(state.instrument);
  const index = levels.indexOf(state.difficulty);
  return index >= 0 && index + 1 < levels.length ? levels[index + 1] : null;
}

function renderSong() {
  const { chart, info } = state;
  const tabs = INSTRUMENTS.map((i) => `<button role="tab" data-instrument="${i}" aria-selected="${i === state.instrument}" ${state.instruments.includes(i) ? "" : `disabled title="No ${TITLE[i].toLowerCase()} chart"`}>${TITLE[i]}</button>`).join("");
  const order = ["song", "guitar", "bass", "drums", "keys", "vocals"];
  const rank = (file) => { const i = order.indexOf(file.replace(/\.ogg$/, "")); return i < 0 ? order.length : i; };
  const audio = [...info.audio].sort((a, b) => rank(a.file) - rank(b.file));
  state.audioFiles = audio.map((a) => a.file);
  const stems = audio.map((a, n) => {
    const name = esc(stemName(a.file));
    const what = `${esc(a.file)}${a.stems.length ? `: ${esc(a.stems.join(", "))}` : ""}`;
    return `<div class="stem" data-stem="${n}"><span class="no">${String(n + 1).padStart(2, "0")}</span><span class="nm" title="${what}">${name}</span>
      <span class="ms"><button class="mute" aria-pressed="false" title="Mute ${name}" aria-label="Mute ${name}" disabled>M</button><button class="solo" aria-pressed="false" title="Solo ${name}" aria-label="Solo ${name}" disabled>S</button></span>
      <input class="vol" type="range" min="0" max="100" step="1" value="100" title="${name} volume" aria-label="${name} volume" disabled></div>`;
  }).join("");
  const speeds = SPEEDS.map((s) => `<option value="${s}"${s === state.rate ? " selected" : ""}>${s.toFixed(2)}×</option>`).join("");
  root.innerHTML = header(`<div class="brand"><a class="back" href="#/" title="All songs" aria-label="All songs">${icon("back")}</a>chartgen</div>
      <div class="song-title"><b>${esc(chart.name)}</b><span>${esc(chart.artist)}</span></div>
      <nav class="tabs" role="tablist" aria-label="Instrument">${tabs}</nav><div class="seg" role="group" aria-label="Level"></div>`) +
    `<div class="tool">
      <button data-zoom="out" title="Zoom out (−)">${icon("zoomOut")}</button><button data-zoom="in" title="Zoom in (+)">${icon("zoomIn")}</button>
      <button data-zoom="fit" title="Whole song">${icon("fit")}Whole song</button><span class="zoom-label"></span><span class="sep"></span>
      <label><input type="checkbox" class="below-toggle" ${state.showBelow ? "checked" : ""}>Show the level below</label>
      <span class="note">Read-only for now: editing comes next.</span></div>
    <aside class="left"></aside>
    <main class="tl" tabindex="0" aria-label="Timeline: arrow keys scroll, plus and minus zoom"><canvas></canvas><div class="spacer"></div></main>
    <aside class="right"></aside>
    <footer class="bot"><button class="play" disabled title="Loading the audio" aria-label="Play">${icon("play")}</button>
      <div class="clock"><b class="t">0:00.000</b><span class="pos"></span></div>
      <label class="ctl" title="Playback speed; slower playback also lowers the pitch">Speed<select class="speed" disabled>${speeds}</select></label>
      <div class="ctl" title="A click on every beat of the chart's tempo map, the downbeat higher"><span id="metro-label">Metronome</span><button class="metro" aria-labelledby="metro-label" aria-pressed="${state.metronome}" disabled>${state.metronome ? "On" : "Off"}</button></div>
      <label class="ctl" title="Draws the playhead this much later than the audio clock. Raise it when the line runs ahead of what you hear (Bluetooth headphones: 150 to 250 ms)">Latency<span class="lat"><input class="latency" type="number" min="-300" max="500" step="5" value="${state.latency}"><span>ms</span></span></label>
      <div class="stems" role="group" aria-label="Stems">${stems}</div></footer>`;
  wireHeader();
  root.querySelector(".mode").textContent = "Read-only";
  root.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => setInstrument(b.dataset.instrument)));
  root.querySelectorAll("[data-zoom]").forEach((b) => b.addEventListener("click", () => zoomBy(b.dataset.zoom)));
  root.querySelector(".below-toggle").addEventListener("change", (e) => {
    state.showBelow = e.target.checked;
    state.timeline.showBelow = state.showBelow;
    layoutLanes();
    state.timeline.draw();
  });

  const scroller = root.querySelector(".tl");
  const canvas = scroller.querySelector("canvas");
  const timeline = new Timeline(canvas, scroller);
  state.timeline = timeline;
  timeline.setSong(state.tempo, state.bars, state.lengthS, state.chart.sections);
  timeline.zoom = startZoom();
  timeline.playhead = state.playhead;
  wireTimeline(scroller, canvas, timeline);
  wireTransport();
  showTrack();
  new ResizeObserver(() => {
    timeline.resize(scroller.clientWidth, scroller.clientHeight);
    layoutLanes();
    timeline.draw();
    updateZoomLabel();
  }).observe(scroller);
}

/** A zoom at which the typical gap between notes of the first chart is about 30 px. */
function startZoom() {
  const track = trackOf(state.instrument, state.difficulty);
  const times = [...new Set(track.notes.map((n) => n[0]))].map((t) => state.tempo.secondsAt(t));
  const gaps = times.slice(1).map((t, i) => t - times[i]).filter((g) => g > 0).sort((x, y) => x - y);
  const median = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0.25;
  return clampZoom(Math.min(320, Math.max(120, 30 / median)));
}

function setInstrument(instrument) {
  if (instrument === state.instrument) return;
  state.instrument = instrument;
  const levels = levelsOf(instrument);
  if (!levels.includes(state.difficulty)) state.difficulty = levels[0];
  state.selected = null;
  showTrack();
}

function setLevel(level) {
  state.difficulty = level;
  state.selected = null;
  showTrack();
}

function showTrack() {
  const levels = levelsOf(state.instrument);
  root.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.instrument === state.instrument)));
  const seg = root.querySelector(".seg");
  seg.innerHTML = LEVELS.map((l) => `<button data-level="${l}" aria-pressed="${l === state.difficulty}" ${levels.includes(l) ? "" : "disabled"}>${TITLE[l]}</button>`).join("");
  seg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => setLevel(b.dataset.level)));
  const below = belowLevel();
  const timeline = state.timeline;
  timeline.setTrack(state.instrument, trackOf(state.instrument, state.difficulty), below ? trackOf(state.instrument, below) : null);
  timeline.selected = state.selected;
  timeline.markers = markers();
  updateWave();
  layoutLanes();
  renderSide();
  timeline.draw();
}

function layoutLanes() {
  const timeline = state.timeline;
  if (!timeline || !timeline.height) return;
  const L = timeline.layout();
  const below = belowLevel();
  const lanes = state.instrument === "drums"
    ? DRUM_LANES.map(([name, colour], i) => [name, `c${colour}`, i])
    : FRETS.map((name, i) => [name, `c${i}`, i]);
  let html = `<div class="lvl" data-top="${L.lanesY - 24}">${TITLE[state.difficulty]}${state.instrument === "drums" ? " · Pro" : ""}</div>`;
  for (const [name, colour, row] of lanes) {
    html += `<div class="lane" data-top="${L.lanesY + row * L.lane}" data-height="${L.lane}"><span class="cell">${String(row + 1).padStart(2, "0")}</span><span class="sw ${colour}"></span>${name}</div>`;
  }
  if (L.kick) html += `<div class="lane" data-top="${L.kickY}" data-height="${L.kick}"><span class="cell">05</span><span class="sw bar c4"></span>Kick</div>`;
  if (L.ghost && below) html += `<div class="lvl" data-top="${L.ghostY - 30}">${TITLE[below]} · below</div>`;
  const wave = waveFile();
  html += `<div class="lvl" data-top="${L.waveY - 30}">${wave ? `Audio · ${esc(wave)}` : "Audio"}</div>`;
  const left = root.querySelector(".left");
  left.innerHTML = html;
  // Positions go through CSSOM: the page's policy allows no inline style attributes.
  left.querySelectorAll("[data-top]").forEach((el) => {
    el.style.top = `${el.dataset.top}px`;
    if (el.dataset.height) el.style.height = `${el.dataset.height}px`;
  });
}

// ---------------------------------------------------------------- side panel

function markers() {
  const below = belowLevel();
  return state.info.validation.errors
    .filter((e) => e.where && e.where.instrument === state.instrument)
    .map((e) => ({
      tick: e.where.tick,
      level: e.where.difficulty === state.difficulty ? "this" : e.where.difficulty === below ? "below" : "other",
    }));
}

function problemItem(entry, kind, index) {
  const where = entry.where;
  const go = where ? `<button class="go" data-${kind}="${index}">Go to ${TITLE[where.instrument]} ${TITLE[where.difficulty]}</button>` : "";
  return `<div class="item"><span class="${kind === "error" ? "ic-err" : "ic-warn"}">${kind === "error" ? icon("alert", "Error") : ""}</span>
    <p>${esc(entry.message)}</p>${go}</div>`;
}

function renderSide() {
  const { info, chart, tempo } = state;
  const errors = info.validation.errors;
  const warnings = info.validation.warnings;
  const count = errors.length + warnings.length;
  let html = `<h2>Problems <span>${count ? `${errors.length} error${errors.length === 1 ? "" : "s"} · ${warnings.length} warning${warnings.length === 1 ? "" : "s"}` : "none"}</span></h2>`;
  if (!count) html += '<p class="quiet">The song folder passes every hard rule of the validator.</p>';
  html += errors.map((e, i) => problemItem(e, "error", i)).join("") + warnings.map((w, i) => problemItem(w, "warning", i)).join("");
  if (info.build_warnings.length) {
    html += `<button class="more" aria-expanded="false">Notes from the build (${info.build_warnings.length})</button><div class="build-notes" hidden>${
      info.build_warnings.map((w) => `<p class="quiet">${esc(w)}</p>`).join("")}</div>`;
  }
  const signatures = tempo.signatures.map((s) => `${s.numerator}/${s.denominator}`).filter((v, i, a) => a.indexOf(v) === i).join(", ");
  html += `<h2>Song</h2><dl class="kv">
    <dt>Tempo</dt><dd>${(info.bpm || tempo.tempos.at(-1).bpm).toFixed(1)} BPM</dd>
    <dt>Tempo events</dt><dd>${tempo.tempos.length}</dd><dt>Time</dt><dd>${signatures}</dd>
    <dt>Sections</dt><dd>${chart.sections.length}</dd><dt>Preview</dt><dd>${clock(info.preview_s)}</dd></dl>`;
  html += '<h2>Selected note</h2><div class="inspector"></div>';
  const side = root.querySelector(".right");
  side.innerHTML = html;
  side.querySelectorAll("[data-error]").forEach((b) => b.addEventListener("click", () => goTo(errors[+b.dataset.error].where)));
  side.querySelectorAll("[data-warning]").forEach((b) => b.addEventListener("click", () => goTo(warnings[+b.dataset.warning].where)));
  const more = side.querySelector(".more");
  if (more) more.addEventListener("click", () => {
    const notes = side.querySelector(".build-notes");
    notes.hidden = !notes.hidden;
    more.setAttribute("aria-expanded", String(!notes.hidden));
  });
  renderInspector();
}

function renderInspector() {
  const box = root.querySelector(".inspector");
  if (!box) return;
  if (state.selected === null) {
    box.innerHTML = '<p class="quiet">Click a note to see where it is.</p>';
    return;
  }
  const { tempo, bars } = state;
  const tick = state.selected;
  const notes = trackOf(state.instrument, state.difficulty).notes.filter((n) => n[0] === tick);
  const drums = state.instrument === "drums";
  const lanes = notes.map((n) => (drums ? `${DRUM_NAMES[n[1]]}${n[1] > 1 ? (n[3] & 4 ? " cymbal" : " tom") : ""}` : n[1] === 5 ? "Open" : FRETS[n[1]])).join(" + ");
  const sustain = Math.max(...notes.map((n) => n[2]));
  const flags = [notes.some((n) => n[3] & 1) && "forced", notes.some((n) => n[3] & 2) && "tap"].filter(Boolean).join(", ") || "none";
  const where = barBeat(tempo, bars, tick);
  box.innerHTML = `<dl class="kv"><dt>Position</dt><dd>Bar ${where.bar}.${where.beat}</dd><dt>Tick</dt><dd>${tick}</dd>
    <dt>Time</dt><dd>${clock(tempo.secondsAt(tick))}</dd><dt>${drums ? "Pads" : "Lanes"}</dt><dd>${esc(lanes)}</dd>
    ${drums ? "" : `<dt>Sustain</dt><dd>${sustain ? `${+(sustain / tempo.resolution).toFixed(3)} beats` : "none"}</dd><dt>Flags</dt><dd>${flags}</dd>`}</dl>`;
}

function goTo(where) {
  if (!where) return;
  if (where.instrument !== state.instrument && state.instruments.includes(where.instrument)) setInstrument(where.instrument);
  if (where.difficulty !== state.difficulty && levelsOf(state.instrument).includes(where.difficulty)) setLevel(where.difficulty);
  scrollToTick(where.tick);
}

// ---------------------------------------------------------------- navigation

function wireTimeline(scroller, canvas, timeline) {
  scroller.querySelector(".spacer").style.width = `${timeline.contentWidth()}px`;
  let frame = 0;
  const redraw = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; timeline.draw(); });
  };
  scroller.addEventListener("scroll", redraw, { passive: true });
  scroller.addEventListener("wheel", (e) => {
    e.preventDefault();
    if (e.ctrlKey) zoomTo(timeline.zoom * Math.exp(-e.deltaY * 0.0015), e.clientX - scroller.getBoundingClientRect().left);
    else scroller.scrollLeft += e.deltaY + e.deltaX;
  }, { passive: false });
  // The ruler and the waveform move the playhead; the lanes pick notes.
  canvas.addEventListener("pointermove", (e) => canvas.classList.toggle("seek", timeline.zoneAt(e.offsetY) !== "lanes"));
  canvas.addEventListener("click", (e) => {
    if (timeline.zoneAt(e.offsetY) !== "lanes") {
      seekTo(timeline.secondsAtX(e.offsetX));
      return;
    }
    state.selected = timeline.hit(e.offsetX, e.offsetY);
    timeline.selected = state.selected;
    timeline.draw();
    renderInspector();
  });
  scroller.addEventListener("keydown", (e) => {
    const bar = state.bars.length > 1 ? (timeline.barSeconds[1] - timeline.barSeconds[0]) * timeline.zoom : 200;
    const actions = {
      ArrowRight: () => { scroller.scrollLeft += bar; },
      ArrowLeft: () => { scroller.scrollLeft -= bar; },
      Home: () => { scroller.scrollLeft = 0; },
      End: () => { scroller.scrollLeft = scroller.scrollWidth; },
      "+": () => zoomBy("in"), "=": () => zoomBy("in"), "-": () => zoomBy("out"),
      Escape: () => { state.selected = null; timeline.selected = null; timeline.draw(); renderInspector(); },
    };
    if (actions[e.key] && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      actions[e.key]();
    }
  });
  showClock(state.playhead);
}

function showClock(seconds) {
  const tick = Math.round(state.tempo.ticksAt(seconds));
  const where = barBeat(state.tempo, state.bars, tick);
  root.querySelector(".clock .t").textContent = clock(seconds);
  root.querySelector(".clock .pos").textContent = `Bar ${where.bar}.${where.beat} · tick ${tick}`;
}

function zoomTo(zoom, pointerX) {
  const timeline = state.timeline;
  const scroller = timeline.scroller;
  const next = clampZoom(zoom);
  const left = zoomAround(Math.max(0, scroller.scrollLeft - PAD), pointerX, timeline.zoom, next) + PAD;
  timeline.zoom = next;
  scroller.querySelector(".spacer").style.width = `${timeline.contentWidth()}px`;
  scroller.scrollLeft = left;
  timeline.draw();
  updateZoomLabel();
}

function zoomBy(how) {
  const timeline = state.timeline;
  const width = timeline.width || 1000;
  if (how === "fit") zoomTo((width - 2 * PAD) / state.lengthS, 0);
  else zoomTo(timeline.zoom * (how === "in" ? 1.4 : 1 / 1.4), width / 2);
}

function updateZoomLabel() {
  const timeline = state.timeline;
  const label = root.querySelector(".zoom-label");
  if (!label || state.bars.length < 2) return;
  label.innerHTML = `<span class="num">${timeline.barsInView()}</span> bars in view`;
}

function scrollToTick(tick) {
  const timeline = state.timeline;
  const x = PAD + state.tempo.secondsAt(tick) * timeline.zoom;
  timeline.scroller.scrollLeft = Math.max(0, x - timeline.width / 3);
  timeline.markers = markers();
  timeline.draw();
  timeline.scroller.focus();
}

// ---------------------------------------------------------------- playback (E.1, SPEC 53)

const STEM_TITLE = { song: "Song", guitar: "Guitar", bass: "Bass", drums: "Drums", keys: "Keys", vocals: "Vocals", crowd: "Crowd" };

function stemName(file) {
  const base = file.replace(/\.ogg$/i, "");
  return STEM_TITLE[base] || base;
}

/** The file whose waveform runs under the lanes: the instrument's own stem, else the backing track. */
function waveFile() {
  const files = state.audioFiles || [];
  return files.find((f) => f === `${state.instrument}.ogg`) || files.find((f) => f === "song.ogg") || files[0] || null;
}

/** Fetches and decodes every audio file of the song, one after the other, showing how far it is. */
async function loadAudio(id) {
  const ctx = new AudioContext({ latencyHint: "interactive" });
  const player = new Player(ctx);
  player.setBeats(metronomeBeats(state.tempo, state.lengthS + 30));
  player.setMetronome(state.metronome);
  player.setRate(state.rate);
  Object.assign(state, { audioCtx: ctx, player, peaks: new Map() });
  renderAudioStatus();
  try {
    if (!state.audioFiles.length) throw new Error("this song folder has no .ogg files.");
    for (const [index, file] of state.audioFiles.entries()) {
      let response;
      try {
        response = await fetch(api.audioUrl(id, file));
      } catch {
        throw new Error("the editor server is not reachable. Is chartgen edit still running?");
      }
      if (!response.ok) throw new Error(`${file}: ${response.status} ${response.statusText}`);
      const bytes = await response.arrayBuffer();
      if (state.player !== player) return; // the song was closed meanwhile
      let buffer;
      try {
        buffer = await ctx.decodeAudioData(bytes);
      } catch {
        throw new Error(`${file} could not be decoded. The editor plays Ogg Vorbis in Chrome and Edge.`);
      }
      if (state.player !== player) return;
      player.addStem(file, buffer);
      state.audio.loaded = index + 1;
      renderAudioStatus();
    }
  } catch (error) {
    if (state.player !== player) return;
    state.audio.status = "error";
    state.audio.message = error.message;
    renderAudioStatus();
    return;
  }
  player.cursor = Math.min(state.playhead, player.duration);
  state.audio.status = "ready";
  renderAudioStatus();
  updateWave();
  layoutLanes();
  drawFrame();
}

/** Stops playback and lets the decoded audio go: on leaving the song. */
function closeAudio() {
  stopLoop();
  const { player, audioCtx } = state;
  state.player = null;
  state.audioCtx = null;
  if (player) player.dispose();
  if (audioCtx) audioCtx.close().catch(() => {});
}

/** The waveform of the stem under the lanes, its peaks computed once per file. */
function updateWave() {
  const timeline = state.timeline;
  const player = state.player;
  if (!timeline || !player || state.audio.status !== "ready") return;
  const file = waveFile();
  const stem = player.stems.find((s) => s.file === file);
  if (!stem) {
    timeline.wave = null;
    timeline.waveNote = "No audio";
    return;
  }
  if (!state.peaks.has(file)) {
    const buffer = stem.buffer;
    const block = 128;
    const channels = Array.from({ length: buffer.numberOfChannels }, (_, c) => buffer.getChannelData(c));
    const values = peaks(channels, block);
    let max = 0;
    for (const v of values) if (v > max) max = v;
    // Quiet stems are drawn larger, up to four times, so that a soft part still shows its shape.
    state.peaks.set(file, { peaks: values, perSecond: buffer.sampleRate / block, scale: max > 0 ? Math.min(4, 0.95 / max) : 1 });
  }
  timeline.wave = state.peaks.get(file);
}

function renderAudioStatus() {
  const audio = state.audio;
  const note = root.querySelector(".tool .note");
  if (!note) return;
  const ready = audio.status === "ready";
  if (audio.status === "loading") note.textContent = `Loading the audio: ${audio.loaded} of ${audio.total} files`;
  else if (audio.status === "error") note.textContent = `The audio could not be loaded: ${audio.message}`;
  else note.textContent = "Read-only for now: editing comes next.";
  note.classList.toggle("bad", audio.status === "error");
  root.querySelectorAll(".bot .play, .bot select, .bot .metro, .stem button, .stem .vol").forEach((el) => { el.disabled = !ready; });
  if (audio.status === "error" && state.timeline) {
    state.timeline.waveNote = "No audio";
    state.timeline.draw();
  }
  renderPlayButton();
}

function renderPlayButton() {
  const play = root.querySelector(".bot .play");
  if (!play) return;
  const playing = Boolean(state.player && state.player.playing);
  play.innerHTML = icon(playing ? "pause" : "play");
  const label = state.audio.status === "ready" ? `${playing ? "Pause" : "Play"} (Space)`
    : state.audio.status === "error" ? "No audio to play" : "Loading the audio";
  play.title = label;
  play.setAttribute("aria-label", label);
}

function renderStems() {
  const stems = state.player ? state.player.stems : [];
  root.querySelectorAll(".stem").forEach((cell) => {
    const index = Number(cell.dataset.stem);
    const stem = stems[index];
    if (!stem) return;
    cell.classList.toggle("muted", stem.mute);
    cell.classList.toggle("solo", stem.solo);
    cell.classList.toggle("silenced", silencedBySolo(stems, index));
    cell.querySelector(".mute").setAttribute("aria-pressed", String(stem.mute));
    cell.querySelector(".solo").setAttribute("aria-pressed", String(stem.solo));
  });
}

function wireTransport() {
  const bot = root.querySelector(".bot");
  bot.querySelector(".play").addEventListener("click", togglePlay);
  bot.querySelector(".speed").addEventListener("change", (e) => {
    state.rate = Number(e.target.value);
    if (state.player) state.player.setRate(state.rate);
  });
  const metro = bot.querySelector(".metro");
  metro.addEventListener("click", () => {
    state.metronome = !state.metronome;
    store("chartgen-metronome", state.metronome ? "on" : "off");
    if (state.player) state.player.setMetronome(state.metronome);
    metro.setAttribute("aria-pressed", String(state.metronome));
    metro.textContent = state.metronome ? "On" : "Off";
  });
  const latency = bot.querySelector(".latency");
  latency.addEventListener("change", () => {
    state.latency = clampLatency(latency.value);
    latency.value = state.latency;
    store("chartgen-latency-ms", state.latency);
    drawFrame();
  });
  bot.querySelectorAll(".stem").forEach((cell) => {
    const index = Number(cell.dataset.stem);
    cell.querySelector(".mute").addEventListener("click", () => toggleStem(index, "mute"));
    cell.querySelector(".solo").addEventListener("click", () => toggleStem(index, "solo"));
    cell.querySelector(".vol").addEventListener("input", (e) => {
      if (state.player && state.player.stems[index]) state.player.setStem(index, { volume: Number(e.target.value) / 100 });
    });
  });
}

function toggleStem(index, key) {
  const player = state.player;
  if (!player || !player.stems[index]) return;
  player.setStem(index, { [key]: !player.stems[index][key] });
  renderStems();
}

async function togglePlay() {
  const player = state.player;
  if (!player || state.audio.status !== "ready") return;
  if (player.playing) {
    const heard = player.playhead(state.latency); // stop where the user is listening, not where the clock is
    player.pause();
    player.cursor = heard;
    stopLoop();
  } else {
    if (player.cursor >= player.duration - 0.05) player.cursor = 0;
    await state.audioCtx.resume();
    if (state.player !== player || player.playing) return;
    player.play();
    startLoop();
  }
  renderPlayButton();
  drawFrame();
}

/** Moves the playhead to a time: playback goes on from there, or starts there. */
function seekTo(seconds) {
  const player = state.player;
  const end = player && player.duration ? player.duration : state.lengthS;
  const target = Math.max(0, Math.min(seconds, end));
  if (player && state.audio.status === "ready") player.seek(target);
  if (!player || !player.playing) state.playhead = target;
  drawFrame();
}

function startLoop() {
  stopLoop();
  state.pump = setInterval(() => { if (state.player) state.player.pump(); }, PUMP_MS);
  const frame = () => {
    state.frame = requestAnimationFrame(frame);
    drawFrame();
  };
  state.frame = requestAnimationFrame(frame);
}

function stopLoop() {
  if (state.frame) cancelAnimationFrame(state.frame);
  if (state.pump) clearInterval(state.pump);
  state.frame = 0;
  state.pump = 0;
}

/** Draws the timeline with the playhead where the audio is heard, turning the page to follow it. */
function drawFrame() {
  const timeline = state.timeline;
  if (!timeline) return;
  const player = state.player;
  const ready = player && state.audio.status === "ready";
  const heard = ready ? player.heardContextTime() : 0;
  const seconds = ready ? player.playhead(state.latency, heard) : state.playhead;
  state.playhead = seconds;
  if (ready && player.playing) {
    const next = followScroll(timeline.x(seconds), timeline.width, timeline.scroller.scrollLeft);
    if (next !== null) timeline.scroller.scrollLeft = next;
    const record = window.chartgenDebug.frames;
    if (record) record.push({ at: performance.now(), playhead: seconds, heard, contextTime: state.audioCtx.currentTime, latency: state.latency });
    if (player.position() >= player.duration) {
      player.pause();
      player.cursor = player.duration;
      stopLoop();
      renderPlayButton();
    }
  }
  timeline.playhead = seconds;
  timeline.draw();
  showClock(seconds);
}

/** Space plays and pauses anywhere but in a text field; a focused button is not pressed by it as well. */
document.addEventListener("keydown", (e) => {
  if (e.code !== "Space" || !state.timeline || e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.target.matches && e.target.matches('input:not([type="range"]), select, textarea')) return;
  e.preventDefault();
  if (!e.repeat) togglePlay();
});
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && state.timeline && e.target.matches && e.target.matches('button, input[type="range"]')) e.preventDefault();
});
