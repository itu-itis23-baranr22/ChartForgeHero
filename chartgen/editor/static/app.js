// chartgen editor (E.2: playback and editing; saving comes in E.3). Two views behind the hash: #/ the song
// list, #/song/<folder> a song.

import { api } from "./api.js";
import { PUMP_MS, Player } from "./audio.js";
import {
  CYMBAL, FORCED, GRIDS, TAP, cascadeSummary, clipboardOf, flagTarget, gridTicks, keyOf, laneOfRow, noteKey, notesInBox,
  pasteAt, plural, rowOf, selectedNotes, snapTick, stepTick, unsavedLabel,
} from "./edit.js";
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

function header(inner, end = "") {
  return `<header class="top">${inner}<div class="end"><span class="mode"></span>${end}<button class="theme"></button></div></header>`;
}

function wireHeader() {
  document.querySelector(".theme").addEventListener("click", toggleTheme);
  renderThemeButton();
}

/**
 * The page and the server are different versions of the editor (api.js versionProblem): say so above
 * everything and stop editing until the page is reloaded. It stays across views.
 */
function showOutdated(message) {
  state.stale = true;
  let bar = document.getElementById("outdated");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "outdated";
    bar.className = "outdated";
    bar.setAttribute("role", "alert");
    document.body.prepend(bar);
  }
  bar.innerHTML = `<span class="ic-err">${icon("alert", "Error")}</span><p>${esc(message)}</p><button class="reload">Reload the page</button>`;
  bar.querySelector(".reload").addEventListener("click", () => location.reload());
  renderEditState();
}

/** An error from the API: a version mismatch gets the banner, anything else is returned to be shown. */
function outdated(error) {
  if (error && error.outdated) {
    showOutdated(error.message);
    return true;
  }
  return false;
}

function route() {
  closeAudio();
  const drafts = document.getElementById("drafts");
  if (drafts) drafts.remove();
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
    outdated(error);
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
    outdated(error);
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
  const grid = Number(stored("chartgen-grid"));
  Object.assign(state, {
    id, chart, info, tempo, lengthS, bars: tempo.barLines(lengthS), instruments,
    instrument: instruments[0], difficulty: null, showBelow: true,
    playhead: 0, rate: 1, metronome: stored("chartgen-metronome") === "on",
    latency: clampLatency(stored("chartgen-latency-ms") ?? 0), audio: { status: "loading", loaded: 0, total: info.audio.length },
    // editing (E.2): the server holds the chart; the page keeps its version and what is selected
    edit: chart.edit, validation: info.validation, selection: new Set(), tool: stored("chartgen-tool") === "draw" ? "draw" : "select",
    grid: GRIDS.includes(grid) ? grid : 8, linked: true, clipboard: state.clipboard || null, queue: Promise.resolve(),
    stale: false, notice: null, gesture: null, saving: false, dismissed: new Set(),
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
  const tabs = INSTRUMENTS.map((i) => `<button role="tab" data-instrument="${i}" aria-selected="${i === state.instrument}"${state.instruments.includes(i) ? "" : missing(noChart(i))}>${TITLE[i]}</button>`).join("");
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
  const grids = GRIDS.map((g) => `<option value="${g}"${g === state.grid ? " selected" : ""}>1/${g}</option>`).join("");
  root.innerHTML = header(`<div class="brand"><a class="back" href="#/" title="All songs" aria-label="All songs">${icon("back")}</a>chartgen</div>
      <div class="song-title"><b>${esc(chart.name)}</b><span>${esc(chart.artist)}</span></div>
      <nav class="tabs" role="tablist" aria-label="Instrument">${tabs}</nav><div class="seg" role="group" aria-label="Level"></div>`,
    '<button class="save" disabled>Save</button>') +
    `<div class="tool">
      <span class="tools" role="group" aria-label="Tool">
        <button data-tool="select" title="Select (V): click a note, Shift or Ctrl to add, drag a box; drag notes to move them">${icon("select")}Select <kbd>V</kbd></button>
        <button data-tool="draw" title="Draw (D): click a lane to add a note, drag right for a sustain">${icon("draw")}Draw <kbd>D</kbd></button></span>
      <span class="sep"></span>
      <label title="Where notes land when they are drawn, dragged or moved with the arrow keys">Grid<select class="grid">${grids}</select></label>
      <span class="sep"></span>
      <button data-zoom="out" title="Zoom out (−)" aria-label="Zoom out">${icon("zoomOut")}</button><button data-zoom="in" title="Zoom in (+)" aria-label="Zoom in">${icon("zoomIn")}</button>
      <button data-zoom="fit" title="Whole song">${icon("fit")}Whole song</button><span class="zoom-label"></span><span class="sep"></span>
      <button class="undo" disabled>${icon("undo")}Undo</button><button class="redo" disabled>${icon("redo")}Redo</button>
      <span class="sep"></span>
      <button class="linked" aria-pressed="${state.linked}" title="On: a note deleted or moved here goes from the levels below too, and a note added here is added to the levels above that lack it, so every level keeps the notes of the level below it">${icon("levels")}Other levels <b></b></button>
      <label><input type="checkbox" class="below-toggle" ${state.showBelow ? "checked" : ""}>Level below</label>
      <span class="note" role="status" aria-live="polite"></span></div>
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
  root.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
    if (b.classList.contains("missing")) setNotice(noChart(b.dataset.instrument), "info");
    else setInstrument(b.dataset.instrument);
  }));
  root.querySelectorAll("[data-zoom]").forEach((b) => b.addEventListener("click", () => zoomBy(b.dataset.zoom)));
  root.querySelectorAll("[data-tool]").forEach((b) => b.addEventListener("click", () => setTool(b.dataset.tool)));
  root.querySelector(".grid").addEventListener("change", (e) => {
    state.grid = Number(e.target.value);
    store("chartgen-grid", state.grid);
  });
  root.querySelector(".top .save").addEventListener("click", saveChart);
  root.querySelector(".undo").addEventListener("click", () => history("undo"));
  root.querySelector(".redo").addEventListener("click", () => history("redo"));
  root.querySelector(".linked").addEventListener("click", () => {
    state.linked = !state.linked;
    renderEditState();
  });
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
  renderEditState();
  showTrack();
  scheduleValidation();
  renderDraftBox();
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

/** "This song has no Hard guitar chart.": what a missing instrument or level says on hover and on a click. */
function noChart(instrument, level = null) {
  return `This song has no ${level ? `${TITLE[level]} ` : ""}${TITLE[instrument].toLowerCase()} chart.`;
}

/**
 * The attributes of a tab or level the song lacks: shown passive like a disabled control, but it still takes a
 * hover and a click to say why, instead of doing nothing silently (owner, 2026-11-25).
 */
function missing(words) {
  return ` class="missing" aria-disabled="true" title="${esc(words)}"`;
}

function setInstrument(instrument) {
  if (instrument === state.instrument) return;
  state.instrument = instrument;
  const levels = levelsOf(instrument);
  if (!levels.includes(state.difficulty)) state.difficulty = levels[0];
  state.selection = new Set();
  showTrack();
}

function setLevel(level) {
  state.difficulty = level;
  state.selection = new Set();
  showTrack();
}

function showTrack() {
  const levels = levelsOf(state.instrument);
  root.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.instrument === state.instrument)));
  const seg = root.querySelector(".seg");
  seg.innerHTML = LEVELS.map((l) => `<button data-level="${l}" aria-pressed="${l === state.difficulty}"${levels.includes(l) ? "" : missing(noChart(state.instrument, l))}>${TITLE[l]}</button>`).join("");
  seg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    if (b.classList.contains("missing")) setNotice(noChart(state.instrument, b.dataset.level), "info");
    else setLevel(b.dataset.level);
  }));
  const below = belowLevel();
  const timeline = state.timeline;
  timeline.setTrack(state.instrument, trackOf(state.instrument, state.difficulty), below ? trackOf(state.instrument, below) : null);
  timeline.selection = state.selection;
  timeline.flashes = [];
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
  return state.validation.errors
    .filter((e) => e.where && e.where.instrument === state.instrument)
    .map((e) => ({
      tick: e.where.tick,
      level: e.where.difficulty === state.difficulty ? "this" : e.where.difficulty === below ? "below" : "other",
    }));
}

function problemItem(entry, kind, index) {
  const where = entry.where;
  let place = "";
  if (where) {
    const at = barBeat(state.tempo, state.bars, where.tick);
    place = `<span class="where">Bar <span class="num">${at.bar}.${at.beat}</span> · ${TITLE[where.difficulty]} ${TITLE[where.instrument].toLowerCase()}</span>`;
  }
  const go = where ? `<button class="go" data-${kind}="${index}">Go to ${TITLE[where.instrument]} ${TITLE[where.difficulty]}</button>` : "";
  const raw = entry.raw && entry.raw !== entry.message ? ` title="Validator: ${esc(entry.raw)}"` : "";
  return `<div class="item"><span class="${kind === "error" ? "ic-err" : "ic-warn"}">${kind === "error" ? icon("alert", "Error") : ""}</span>
    ${place}<p${raw}>${esc(entry.message)}</p>${go}</div>`;
}

function renderSide() {
  const { info, chart, tempo } = state;
  let html = '<div class="problems"></div>';
  if (info.build_warnings.length) {
    html += `<button class="more" aria-expanded="false">Notes from the build (${info.build_warnings.length})</button><div class="build-notes" hidden>${
      info.build_warnings.map((w) => `<p class="quiet">${esc(w)}</p>`).join("")}</div>`;
  }
  const signatures = tempo.signatures.map((s) => `${s.numerator}/${s.denominator}`).filter((v, i, a) => a.indexOf(v) === i).join(", ");
  html += `<h2>Song</h2><dl class="kv">
    <dt>Tempo</dt><dd>${(info.bpm || tempo.tempos.at(-1).bpm).toFixed(1)} BPM</dd>
    <dt>Tempo events</dt><dd>${tempo.tempos.length}</dd><dt>Time</dt><dd>${signatures}</dd>
    <dt>Sections</dt><dd>${chart.sections.length}</dd><dt>Preview</dt><dd>${clock(info.preview_s)}</dd></dl>`;
  html += '<h2 class="sel-title">Selected</h2><div class="inspector"></div>';
  const side = root.querySelector(".right");
  side.innerHTML = html;
  const more = side.querySelector(".more");
  if (more) more.addEventListener("click", () => {
    const notes = side.querySelector(".build-notes");
    notes.hidden = !notes.hidden;
    more.setAttribute("aria-expanded", String(!notes.hidden));
  });
  renderProblems();
  renderInspector();
}

/** The problem list: the live check of the chart as it would be saved, in plain words. */
function renderProblems() {
  const box = root.querySelector(".problems");
  if (!box) return;
  const { errors, warnings } = state.validation;
  const count = errors.length + warnings.length;
  let html = `<h2>Problems <span>${count ? `${plural(errors.length, "error")} · ${plural(warnings.length, "warning")}` : "none"}</span></h2>`;
  if (!count) html += '<p class="quiet">The chart passes every hard rule of the validator.</p>';
  html += errors.map((e, i) => problemItem(e, "error", i)).join("") + warnings.map((w, i) => problemItem(w, "warning", i)).join("");
  box.innerHTML = html;
  box.querySelectorAll("[data-error]").forEach((b) => b.addEventListener("click", () => goTo(errors[+b.dataset.error].where)));
  box.querySelectorAll("[data-warning]").forEach((b) => b.addEventListener("click", () => goTo(warnings[+b.dataset.warning].where)));
}

function laneName(n) {
  if (state.instrument === "drums") return `${DRUM_NAMES[n[1]]}${n[1] > 1 ? (n[3] & CYMBAL ? " cymbal" : " tom") : ""}`;
  return n[1] === 5 ? "Open" : FRETS[n[1]];
}

const KEYS_HINT = `<dl class="keys">
  <dt><kbd>Del</kbd></dt><dd>Delete</dd>
  <dt><kbd>←</kbd> <kbd>→</kbd></dt><dd>Move one grid step</dd>
  <dt><kbd>↑</kbd> <kbd>↓</kbd></dt><dd>Move to the lane above or below</dd>
  <dt><kbd>Shift</kbd> <kbd>←</kbd> <kbd>→</kbd></dt><dd>Shorten or lengthen the sustain</dd>
  <dt><kbd>F</kbd> <kbd>T</kbd> <kbd>C</kbd></dt><dd>Forced, tap, cymbal</dd>
  <dt><kbd>Ctrl</kbd> <kbd>C</kbd> <kbd>V</kbd></dt><dd>Copy, paste at the playhead</dd>
  <dt><kbd>Ctrl</kbd> <kbd>Z</kbd> <kbd>Y</kbd></dt><dd>Undo, redo</dd></dl>`;

function renderInspector() {
  const box = root.querySelector(".inspector");
  if (!box) return;
  const title = root.querySelector(".sel-title");
  const notes = selectedNotes(trackOf(state.instrument, state.difficulty), state.selection);
  if (title) title.innerHTML = `Selected <span>${notes.length ? plural(notes.length, "note") : ""}</span>`;
  if (!notes.length) {
    box.innerHTML = `<p class="quiet">${state.tool === "draw"
      ? "Click an empty spot of a lane to add a note there; drag right to draw its sustain. Click a note to select it."
      : "Click a note to select it; Shift or Ctrl and click to add more, or drag a box around them."}</p>${KEYS_HINT}`;
    return;
  }
  const { tempo, bars } = state;
  const drums = state.instrument === "drums";
  const first = notes[0][0];
  const last = notes.at(-1)[0];
  const from = barBeat(tempo, bars, first);
  if (first === last) {
    const lanes = notes.map(laneName).join(" + ");
    const sustain = Math.max(...notes.map((n) => n[2]));
    const flags = [notes.some((n) => n[3] & FORCED) && "forced", notes.some((n) => n[3] & TAP) && "tap"].filter(Boolean).join(", ") || "none";
    box.innerHTML = `<dl class="kv"><dt>Position</dt><dd>Bar ${from.bar}.${from.beat}</dd><dt>Tick</dt><dd>${first}</dd>
      <dt>Time</dt><dd>${clock(tempo.secondsAt(first))}</dd><dt>${drums ? "Pads" : "Lanes"}</dt><dd>${esc(lanes)}</dd>
      ${drums ? "" : `<dt>Sustain</dt><dd>${sustain ? `${+(sustain / tempo.resolution).toFixed(3)} beats` : "none"}</dd><dt>Flags</dt><dd>${flags}</dd>`}</dl>${KEYS_HINT}`;
    return;
  }
  const to = barBeat(tempo, bars, last);
  box.innerHTML = `<dl class="kv"><dt>From</dt><dd>Bar ${from.bar}.${from.beat}</dd><dt>To</dt><dd>Bar ${to.bar}.${to.beat}</dd>
    <dt>Time</dt><dd>${clock(tempo.secondsAt(first))} – ${clock(tempo.secondsAt(last))}</dd></dl>${KEYS_HINT}`;
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
  state.redraw = redraw;
  // The ruler and the waveform move the playhead; in the lanes the tools select, move and draw notes.
  canvas.addEventListener("pointerdown", (e) => pointerDown(e, scroller, canvas, timeline));
  canvas.addEventListener("pointermove", (e) => pointerMove(e, canvas, timeline));
  canvas.addEventListener("pointerup", (e) => pointerUp(e, canvas, timeline));
  canvas.addEventListener("pointercancel", () => cancelGesture(timeline));
  canvas.addEventListener("pointerleave", () => {
    if (!state.gesture && timeline.hover) {
      timeline.hover = null;
      redraw();
    }
  });
  scroller.addEventListener("keydown", (e) => {
    // With notes selected the arrow keys move them (the editing keys below); without, they scroll.
    if (state.selection.size && e.key.startsWith("Arrow")) return;
    const bar = state.bars.length > 1 ? (timeline.barSeconds[1] - timeline.barSeconds[0]) * timeline.zoom : 200;
    const actions = {
      ArrowRight: () => { scroller.scrollLeft += bar; },
      ArrowLeft: () => { scroller.scrollLeft -= bar; },
      Home: () => { scroller.scrollLeft = 0; },
      End: () => { scroller.scrollLeft = scroller.scrollWidth; },
      "+": () => zoomBy("in"), "=": () => zoomBy("in"), "-": () => zoomBy("out"),
    };
    if (actions[e.key] && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      actions[e.key]();
    }
  });
  showClock(state.playhead);
}

// ---------------------------------------------------------------- pointer: select, box, move, draw (E.2)

const DRAG_PX = 4; // a press that moves less than this is a click

/** The row under the pointer, clamped to the rows: for a selection box that starts or ends off them. */
function rowClamped(timeline, py) {
  const row = timeline.rowAt(py);
  if (row !== null) return row;
  return py < timeline.layout().lanesY ? 0 : 4;
}

function pointerDown(e, scroller, canvas, timeline) {
  if (e.button !== 0 || state.gesture) return;
  scroller.focus({ preventScroll: true });
  if (timeline.zoneAt(e.offsetY) !== "lanes") {
    seekTo(timeline.secondsAtX(e.offsetX));
    return;
  }
  const note = timeline.noteAt(e.offsetX, e.offsetY);
  const toggle = e.ctrlKey || e.metaKey;
  if (note) {
    const key = noteKey(note);
    const selection = new Set(toggle || e.shiftKey ? state.selection : []);
    if (toggle && state.selection.has(key)) selection.delete(key);
    else selection.add(key);
    // A press on a note of the selection keeps the group, to drag it; a click without a drag picks the one.
    const group = !toggle && !e.shiftKey && state.selection.has(key) && state.selection.size > 1;
    if (group) state.selection.forEach((k) => selection.add(k));
    setSelection(selection);
    if (toggle) return;
    state.gesture = {
      type: "move", anchor: note, x: e.offsetX, y: e.offsetY, started: false, ticks: 0, rows: 0, group, key,
      grab: timeline.tickAtX(e.offsetX) - note[0], downRow: rowOf(drums(), note[1]),
    };
  } else if (state.tool === "draw") {
    const lane = laneOfRow(drums(), timeline.rowAt(e.offsetY));
    if (lane === null) return;
    const tick = snap(timeline.tickAtX(e.offsetX));
    state.gesture = { type: "draw", tick, lane };
    timeline.hover = { tick, lane, length: 0 };
    timeline.draw();
  } else {
    const additive = toggle || e.shiftKey;
    state.gesture = { type: "box", x0: e.offsetX, y0: e.offsetY, started: false, base: new Set(additive ? state.selection : []) };
    if (!additive) setSelection([]);
  }
  canvas.setPointerCapture(e.pointerId);
}

function pointerMove(e, canvas, timeline) {
  const g = state.gesture;
  const zone = timeline.zoneAt(e.offsetY);
  canvas.classList.toggle("seek", !g && zone !== "lanes");
  if (!g) {
    const over = zone === "lanes" ? timeline.noteAt(e.offsetX, e.offsetY) : null;
    canvas.classList.toggle("grab", Boolean(over));
    canvas.classList.toggle("draw", state.tool === "draw" && zone === "lanes" && !over);
    let hover = null;
    if (state.tool === "draw" && zone === "lanes" && !over) {
      const lane = laneOfRow(drums(), timeline.rowAt(e.offsetY));
      if (lane !== null) hover = { tick: snap(timeline.tickAtX(e.offsetX)), lane, length: 0 };
    }
    if (JSON.stringify(hover) !== JSON.stringify(timeline.hover)) {
      timeline.hover = hover;
      state.redraw();
    }
    return;
  }
  if (g.type === "move") {
    if (!g.started && Math.hypot(e.offsetX - g.x, e.offsetY - g.y) < DRAG_PX) return;
    g.started = true;
    canvas.classList.add("dragging");
    g.ticks = snap(Math.max(0, timeline.tickAtX(e.offsetX) - g.grab)) - g.anchor[0];
    const row = timeline.rowAt(e.offsetY);
    if (g.downRow !== null && row !== null) g.rows = row - g.downRow;
    timeline.drag = { ticks: g.ticks, rows: g.rows };
  } else if (g.type === "draw") {
    if (drums()) return; // drum notes have no sustain
    const length = Math.max(0, snap(timeline.tickAtX(e.offsetX)) - g.tick);
    timeline.hover = { tick: g.tick, lane: g.lane, length };
  } else {
    if (!g.started && Math.hypot(e.offsetX - g.x0, e.offsetY - g.y0) < DRAG_PX) return;
    g.started = true;
    timeline.box = { x0: g.x0, y0: g.y0, x1: e.offsetX, y1: e.offsetY };
    const [xa, xb] = [Math.min(g.x0, e.offsetX), Math.max(g.x0, e.offsetX)];
    const [ya, yb] = [Math.min(g.y0, e.offsetY), Math.max(g.y0, e.offsetY)];
    const inside = notesInBox(timeline.track.notes, timeline.tickAtX(xa), timeline.tickAtX(xb), rowClamped(timeline, ya), rowClamped(timeline, yb), drums());
    timeline.selection = new Set([...g.base, ...inside]);
  }
  state.redraw();
}

function pointerUp(e, canvas, timeline) {
  const g = state.gesture;
  if (!g) return;
  state.gesture = null;
  canvas.classList.remove("dragging");
  if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
  if (g.type === "move") {
    timeline.drag = null;
    timeline.draw();
    const { ticks, rows } = g;
    if (g.started && (ticks || rows)) edit(() => ({ kind: "move", notes: selectedPlaces(), ticks, rows }));
    else if (!g.started && g.group) setSelection([g.key]);
  } else if (g.type === "draw") {
    const length = drums() ? 0 : (timeline.hover ? timeline.hover.length : 0);
    timeline.hover = null;
    timeline.draw();
    edit(() => ({ kind: "add", notes: [[g.tick, g.lane, length, 0]] }));
  } else {
    timeline.box = null;
    setSelection(timeline.selection);
  }
}

function cancelGesture(timeline) {
  state.gesture = null;
  Object.assign(timeline, { drag: null, box: null, hover: null, selection: state.selection });
  timeline.draw();
}

// ---------------------------------------------------------------- editing (E.2, SPEC 50)
// The server does every edit and answers with the tracks it changed; the page sends one edit at a time,
// each with the chart version the last answer gave, and builds it when its turn comes (from the selection
// as it is then), so that a held arrow key moves the notes step by step.

const drums = () => state.instrument === "drums";
const currentTrack = () => trackOf(state.instrument, state.difficulty);
const gridStep = () => gridTicks(state.chart.resolution, state.grid);
const snap = (tick) => snapTick(state.bars, tick, gridStep());
const selectedPlaces = () => selectedNotes(currentTrack(), state.selection).map((n) => [n[0], n[1]]);

function setSelection(keys) {
  state.selection = new Set(keys);
  if (state.timeline) {
    state.timeline.selection = state.selection;
    state.timeline.draw();
  }
  renderInspector();
}

function setTool(tool) {
  state.tool = tool;
  store("chartgen-tool", tool);
  if (state.timeline) state.timeline.hover = null;
  renderEditState();
  renderInspector();
  if (state.timeline) state.timeline.draw();
}

function renderEditState() {
  const edit = state.edit;
  const mode = root.querySelector(".mode");
  if (mode && edit) {
    mode.textContent = unsavedLabel(edit.unsaved);
    mode.title = edit.unsaved
      ? "Kept while chartgen edit runs and in a draft beside the songs; Save writes them to the song folder"
      : "The chart is as it is in the song folder";
  }
  const save = root.querySelector(".top .save");
  if (save && edit) {
    save.disabled = !edit.unsaved || state.stale || state.saving;
    save.textContent = state.saving ? "Saving…" : "Save";
    save.title = edit.unsaved ? "Save to the song folder (Ctrl+S); the files before are backed up" : "Nothing to save";
  }
  root.querySelectorAll("[data-tool]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tool === state.tool)));
  const undo = root.querySelector(".tool .undo");
  const redo = root.querySelector(".tool .redo");
  if (undo && edit) {
    undo.disabled = !edit.undo || state.stale;
    undo.title = edit.undo ? `Undo: ${edit.undo} (Ctrl+Z)` : "Nothing to undo";
    redo.disabled = !edit.redo || state.stale;
    redo.title = edit.redo ? `Redo: ${edit.redo} (Ctrl+Y)` : "Nothing to redo";
  }
  const linked = root.querySelector(".tool .linked");
  if (linked) {
    linked.setAttribute("aria-pressed", String(state.linked));
    linked.querySelector("b").textContent = state.linked ? "On" : "Off";
  }
}

/** Queues one edit: `make` returns the operation when its turn comes, or null for nothing to do. */
function edit(make) {
  const id = state.id;
  state.queue = state.queue.then(async () => {
    if (state.id !== id || state.stale) return;
    const op = make();
    if (!op) return;
    const body = { version: state.edit.version, instrument: state.instrument, difficulty: state.difficulty, linked: state.linked, op };
    try {
      const out = await api.op(id, body);
      if (state.id === id) applyAnswer(out, true, "");
    } catch (error) {
      if (state.id === id) failed(error);
    }
  });
}

function history(which) {
  const id = state.id;
  state.queue = state.queue.then(async () => {
    if (state.id !== id || state.stale) return;
    if (!state.edit[which]) return;
    try {
      const out = await api[which](id, state.edit.version);
      if (state.id === id) applyAnswer(out, false, `${which === "undo" ? "Undid" : "Redid"}: ${out.label}`);
    } catch (error) {
      if (state.id === id) failed(error);
    }
  });
}

/** Puts an answer's tracks in place, then redraws, flashes what changed elsewhere and checks again. */
function applyAnswer(out, select, said) {
  state.edit = out.edit;
  for (const track of out.tracks) {
    const index = state.chart.tracks.findIndex((t) => t.instrument === track.instrument && t.difficulty === track.difficulty);
    if (index >= 0) state.chart.tracks[index] = track;
  }
  const notes = currentTrack().notes;
  if (select && out.selection) state.selection = new Set(out.selection.map(([t, l]) => keyOf(t, l)));
  else {
    const present = new Set(notes.map(noteKey));
    state.selection = new Set([...state.selection].filter((k) => present.has(k)));
  }
  const words = [said, cascadeSummary(out.cascaded), ...(out.notices || [])].filter(Boolean);
  setNotice(words.join(" · "), "info");
  const timeline = state.timeline;
  const below = belowLevel();
  timeline.setTrack(state.instrument, currentTrack(), below ? trackOf(state.instrument, below) : null);
  timeline.selection = state.selection;
  timeline.flashes = (out.cascaded || []).filter((c) => c.difficulty === below);
  clearTimeout(state.flashTimer);
  if (timeline.flashes.length) {
    state.flashTimer = setTimeout(() => {
      if (state.timeline !== timeline) return;
      timeline.flashes = [];
      timeline.draw();
    }, 1500);
  }
  timeline.draw();
  renderEditState();
  renderInspector();
  scheduleValidation();
  renderDraftBox();
}

function failed(error) {
  if (outdated(error)) return;
  if (error.stale) state.stale = true;
  setNotice(error.message, "bad");
  renderEditState();
}

function scheduleValidation() {
  clearTimeout(state.validateTimer);
  state.validateTimer = setTimeout(runValidation, 150);
}

/** The live check of the chart as it would be saved; an answer for an older version is dropped. */
async function runValidation() {
  const id = state.id;
  let result;
  try {
    result = await api.validate(id);
  } catch (error) {
    if (state.id === id && (error.stale || error.outdated)) failed(error);
    return;
  }
  if (state.id !== id || !state.edit || result.version !== state.edit.version) return;
  state.validation = { errors: result.errors, warnings: result.warnings };
  if (state.timeline) {
    state.timeline.markers = markers();
    state.timeline.draw();
  }
  renderProblems();
}

/** A line in the tool row: what an edit also did, or why it was refused. It stays until the next one. */
function setNotice(text, tone) {
  state.notice = text ? { text, tone } : null;
  renderNote();
}

function renderNote() {
  const note = root.querySelector(".tool .note");
  if (!note) return;
  const audio = state.audio || {};
  let text = "";
  let bad = false;
  if (state.notice) {
    text = state.notice.text;
    bad = state.notice.tone === "bad";
  } else if (audio.status === "loading") {
    text = `Loading the audio: ${audio.loaded} of ${audio.total} files`;
  } else if (audio.status === "error") {
    text = `The audio could not be loaded: ${audio.message}`;
    bad = true;
  }
  note.textContent = text;
  note.title = text;
  note.classList.toggle("bad", bad);
}

function copySelection() {
  const notes = selectedNotes(currentTrack(), state.selection);
  if (!notes.length) {
    setNotice("Select the notes to copy first.", "info");
    return;
  }
  state.clipboard = clipboardOf(state.instrument, notes);
  setNotice(`Copied ${plural(notes.length, "note")}: Ctrl+V pastes them at the playhead.`, "info");
}

function paste() {
  const clip = state.clipboard;
  if (!clip) {
    setNotice("Nothing is copied yet.", "info");
    return;
  }
  if ((clip.instrument === "drums") !== drums()) {
    setNotice(`Notes copied from ${TITLE[clip.instrument].toLowerCase()} can be pasted on ${clip.instrument === "drums" ? "drums" : "guitar, bass and keys"} only.`, "bad");
    return;
  }
  const tick = snap(state.tempo.ticksAt(state.playhead));
  edit(() => ({ kind: "paste", notes: pasteAt(clip, tick) }));
}

function toggleFlag(flag, bit) {
  edit(() => {
    const notes = selectedNotes(currentTrack(), state.selection);
    if (!notes.length) return null;
    // The cymbal key counts only the pads that can be cymbals: yellow, blue and green.
    const counted = flag === "cymbal" ? notes.filter((n) => n[1] >= 2 && n[1] <= 4) : notes;
    return { kind: "flag", notes: notes.map((n) => [n[0], n[1]]), flag, on: counted.length ? flagTarget(counted, bit) : true };
  });
}

/** The editing keys: anywhere but in a text field, a select or a slider. */
document.addEventListener("keydown", (e) => {
  if (!state.timeline || !state.edit || state.gesture) return;
  if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "s") {
    e.preventDefault(); // never the browser's own "save page"
    saveChart();
    return;
  }
  if (e.target.matches && e.target.matches("input, select, textarea")) return;
  const key = e.key.toLowerCase();
  const ctrl = e.ctrlKey || e.metaKey;
  const any = state.selection.size > 0;
  let action = null;
  if (ctrl && !e.altKey) {
    if (key === "z" && !e.shiftKey) action = () => history("undo");
    else if (key === "y" || (key === "z" && e.shiftKey)) action = () => history("redo");
    else if (key === "c") action = copySelection;
    else if (key === "v") action = paste;
    else if (key === "a") action = () => setSelection(currentTrack().notes.map(noteKey));
  } else if (!e.altKey && !ctrl) {
    if (key === "v" && !e.shiftKey) action = () => setTool("select");
    else if (key === "d" && !e.shiftKey) action = () => setTool("draw");
    else if (key === "escape" && any) action = () => setSelection([]);
    else if ((key === "delete" || key === "backspace") && any) action = () => edit(() => ({ kind: "delete", notes: selectedPlaces() }));
    else if (key === "f" && any) action = () => toggleFlag("forced", FORCED);
    else if (key === "t" && any) action = () => toggleFlag("tap", TAP);
    else if (key === "c" && any) action = () => toggleFlag("cymbal", CYMBAL);
    else if ((key === "arrowleft" || key === "arrowright") && any) {
      const direction = key === "arrowright" ? 1 : -1;
      action = e.shiftKey
        ? () => edit(() => (selectedPlaces().length ? { kind: "sustain", notes: selectedPlaces(), delta: direction * gridStep() } : null))
        : () => edit(() => {
          const notes = selectedNotes(currentTrack(), state.selection);
          if (!notes.length) return null;
          const ticks = stepTick(state.bars, notes[0][0], gridStep(), direction) - notes[0][0];
          return ticks ? { kind: "move", notes: notes.map((n) => [n[0], n[1]]), ticks, rows: 0 } : null;
        });
    } else if ((key === "arrowup" || key === "arrowdown") && any && !e.shiftKey) {
      const rows = key === "arrowdown" ? 1 : -1;
      action = () => edit(() => (selectedPlaces().length ? { kind: "move", notes: selectedPlaces(), ticks: 0, rows } : null));
    }
  }
  if (!action) return;
  e.preventDefault();
  action();
});

// ---------------------------------------------------------------- saving and drafts (E.3)
// Unsaved edits survive closing the page: the server keeps them, and writes a draft beside the songs a second
// after each edit, so the page no longer asks before it is closed.

/** Problems in view, its heading focused: where a refused save sends the user (owner's decision 4). */
function showProblems() {
  const box = root.querySelector(".problems");
  if (!box) return;
  const title = box.querySelector("h2");
  title.tabIndex = -1;
  box.scrollIntoView({ block: "start" });
  title.focus({ preventScroll: true });
}

function saveChart() {
  if (!state.edit || !state.edit.unsaved || state.stale || state.saving) return;
  const errors = state.validation.errors.length;
  if (errors) {
    setNotice(`The chart has ${plural(errors, "error")}: fix ${errors === 1 ? "it" : "them"} before saving (see Problems).`, "bad");
    showProblems();
    return;
  }
  const id = state.id;
  state.saving = true;
  renderEditState();
  state.queue = state.queue.then(async () => {
    try {
      const out = await api.save(id, state.edit.version);
      if (state.id !== id) return;
      state.edit = out.edit;
      setNotice(out.message, "info");
    } catch (error) {
      if (state.id !== id) return;
      if (error.errors) {
        setNotice(error.message, "bad");
        scheduleValidation();
        showProblems();
      } else if (error.diskChanged) {
        setNotice(error.message, "bad");
      } else {
        failed(error);
      }
    } finally {
      if (state.id === id) {
        state.saving = false;
        renderEditState();
        renderDraftBox();
      }
    }
  });
}

function stamp(iso) {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "an earlier session";
  const two = (n) => String(n).padStart(2, "0");
  return `${at.getFullYear()}-${two(at.getMonth() + 1)}-${two(at.getDate())} ${two(at.getHours())}:${two(at.getMinutes())}`;
}

/**
 * The box under the header: a draft from an earlier session to restore or discard, and drafts that were set
 * aside (stale, or not restored before editing), with the path of each (owner's decision 1).
 */
function renderDraftBox() {
  let box = document.getElementById("drafts");
  const edit = state.edit;
  const aside = edit ? (edit.set_aside || []).filter((a) => !state.dismissed.has(a.path)) : [];
  if (!state.timeline || !edit || (!edit.draft && !aside.length)) {
    if (box) box.remove();
    return;
  }
  if (!box) {
    box = document.createElement("div");
    box.id = "drafts";
    box.className = "draft-box";
    box.setAttribute("role", "status");
    document.body.prepend(box);
  }
  let html = "";
  if (edit.draft) {
    html += `<div class="row"><p><b>${plural(edit.draft.unsaved, "unsaved edit")}</b> of this song from ${esc(stamp(edit.draft.saved_at))} ${edit.draft.unsaved === 1 ? "was" : "were"} kept in a draft.</p>
      <span class="acts"><button class="restore">Restore</button><button class="discard">Discard</button></span></div>`;
  }
  for (const a of aside) {
    html += `<div class="row"><p>${esc(a.message)}</p><span class="acts"><button class="dismiss" data-path="${esc(a.path)}">Dismiss</button></span></div>`;
  }
  box.innerHTML = html;
  const restore = box.querySelector(".restore");
  if (restore) restore.addEventListener("click", () => draftAction("restoreDraft"));
  const discard = box.querySelector(".discard");
  if (discard) discard.addEventListener("click", () => draftAction("discardDraft"));
  box.querySelectorAll(".dismiss").forEach((b) => b.addEventListener("click", () => {
    state.dismissed.add(b.dataset.path);
    renderDraftBox();
  }));
}

function draftAction(which) {
  const id = state.id;
  state.queue = state.queue.then(async () => {
    try {
      const out = await api[which](id, state.edit.version);
      if (state.id !== id) return;
      if (which === "restoreDraft") applyAnswer(out, false, `Restored: ${plural(out.edit.unsaved, "unsaved edit")}`);
      else {
        state.edit = out.edit;
        setNotice("The draft was discarded.", "info");
        renderEditState();
      }
    } catch (error) {
      if (state.id === id) failed(error);
    }
    if (state.id === id) renderDraftBox();
  });
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
  if (!root.querySelector(".tool .note")) return;
  const ready = audio.status === "ready";
  renderNote();
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
