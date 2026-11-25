// chartgen editor (E.0: read-only). Two views behind the hash: #/ the song list, #/song/<folder> a song.

import { api } from "./api.js";
import { icon } from "./icons.js";
import { TempoMap } from "./tempo.js";
import { PAD, Timeline } from "./timeline.js";
import { barBeat, clampZoom, clock, zoomAround } from "./view.js";

const INSTRUMENTS = ["guitar", "bass", "drums", "keys"];
const LEVELS = ["expert", "hard", "medium", "easy"];
const TITLE = { guitar: "Guitar", bass: "Bass", drums: "Drums", keys: "Keys", expert: "Expert", hard: "Hard", medium: "Medium", easy: "Easy" };
const FRETS = ["Green", "Red", "Yellow", "Blue", "Orange"];
const DRUM_LANES = [["Red", 1], ["Yellow", 2], ["Blue", 3], ["Green", 0]]; // name, colour class
const DRUM_NAMES = { 0: "Kick", 1: "Red", 2: "Yellow", 3: "Blue", 4: "Green" };
const root = document.getElementById("app");

const esc = (value) => String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

// ---------------------------------------------------------------- theme (a per-viewer convenience)

function storedTheme() {
  try { return localStorage.getItem("chartgen-theme"); } catch { return null; }
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next);
  try { localStorage.setItem("chartgen-theme", next); } catch { /* private window: the choice lasts this page */ }
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

function header(inner) {
  return `<header class="top">${inner}<div class="end"><span class="mode"></span><button class="theme"></button></div></header>`;
}

function wireHeader() {
  document.querySelector(".theme").addEventListener("click", toggleTheme);
  renderThemeButton();
}

function route() {
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
  });
  state.difficulty = levelsOf(state.instrument)[0];
  document.title = `${chart.name} – chartgen editor`;
  renderSong();
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
  const stems = audio.map((a, n) => `<div class="stem" title="${esc(a.file)}${a.stems.length ? `: ${esc(a.stems.join(", "))}` : ""}"><span class="no">${String(n + 1).padStart(2, "0")}</span><span class="nm">${esc(a.file.replace(/\.ogg$/, ""))}</span></div>`).join("");
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
    <footer class="bot"><button class="play" disabled title="Playback comes next">${icon("play")}</button>
      <div class="clock"><b class="t">0:00.000</b><span class="pos"></span></div>
      <div class="ctl">Tempo<b class="bpm">–</b></div><div class="ctl">Length<b>${clock(state.lengthS).replace(/\.\d+$/, "")}</b></div>
      <div class="stems" role="group" aria-label="Audio files">${stems}</div></footer>`;
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
  wireTimeline(scroller, canvas, timeline);
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
  root.querySelector(".bpm").textContent = (info.bpm || tempo.tempos.at(-1).bpm).toFixed(1);
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
  canvas.addEventListener("pointermove", (e) => showClock(timeline.secondsAtX(e.offsetX)));
  canvas.addEventListener("pointerleave", () => showClock(timeline.secondsAtX(0)));
  canvas.addEventListener("click", (e) => {
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
  showClock(0);
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
