// The timeline: time runs left to right in seconds (as the audio does), lanes are rows. Drawn on a canvas
// that stays in place while a wide spacer scrolls under it, so the browser's own scrollbar moves the view.

import { laneOfRow, noteKey, rowOf } from "./edit.js";
import { peakBetween } from "./transport.js";
import { visibleSlice } from "./view.js";

export const PAD = 24; // px before the song's start and after its end
const RULER = 92;
const GHOST_ROW = 13;
const KICK_ROW = 44;
const WAVE_ROW = 56;
const WAVE_GAP = 40; // room for the waveform's label above it
const FORCED = 1;
const TAP = 2;
const CYMBAL = 4;
const OPEN_LANE = 5;

/** Drums: pad lane -> row (red, yellow, blue, green) and -> fret colour; the kick (lane 0) has its own row. */
const DRUM_ROW = { 1: 0, 2: 1, 3: 2, 4: 3 };
const DRUM_COLOUR = { 0: 4, 1: 1, 2: 2, 3: 3, 4: 0 };

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export class Timeline {
  constructor(canvas, scroller) {
    this.canvas = canvas;
    this.scroller = scroller;
    this.ctx = canvas.getContext("2d");
    this.zoom = 160; // px per second
    this.selection = new Set(); // keys "tick:lane" of the selected notes
    this.drag = null; // {ticks, rows}: the selected notes drawn where a drag would put them
    this.hover = null; // {tick, lane, length}: the note the Draw tool would add
    this.box = null; // {x0, y0, x1, y1}: a selection box being drawn
    this.flashes = []; // {tick, lane}: notes an edit changed on the level below, ringed for a moment
    this.markers = [];
    this.showBelow = true;
    this.playhead = 0; // seconds: where playback is, or starts
    this.wave = null; // {peaks, perSecond, scale} of the stem under the lanes, null while loading
    this.waveNote = "Loading the audio…";
    this.width = 0;
    this.height = 0;
  }

  setSong(tempoMap, bars, lengthS, sections) {
    this.tempo = tempoMap;
    this.bars = bars;
    this.lengthS = lengthS;
    this.sections = sections;
    this.barSeconds = bars.map((t) => tempoMap.secondsAt(t));
  }

  setTrack(instrument, track, below) {
    this.instrument = instrument;
    this.track = track;
    this.below = below;
    this.longest = Math.max(0, ...track.notes.map((n) => n[2]));
    this.longestBelow = below ? Math.max(0, ...below.notes.map((n) => n[2])) : 0;
  }

  get drums() {
    return this.instrument === "drums";
  }

  /** Rows and their heights for the current size: also used to place the lane labels beside the canvas. */
  layout() {
    const rows = this.drums ? 4 : 5;
    const kick = this.drums ? KICK_ROW : 0;
    const ghost = this.showBelow && this.below ? 40 + 5 * GHOST_ROW + 16 : 0;
    const free = this.height - RULER - kick - ghost - WAVE_GAP - WAVE_ROW - 24;
    const lane = Math.max(44, Math.min(76, Math.floor(free / rows)));
    const lanesY = RULER;
    const kickY = lanesY + rows * lane;
    const ghostY = kickY + kick + 40;
    const waveY = (ghost ? ghostY + 5 * GHOST_ROW + 6 : kickY + kick) + WAVE_GAP;
    return { rows, lane, lanesY, kick, kickY, ghostY, ghost: ghost > 0, waveY, wave: WAVE_ROW };
  }

  resize(width, height) {
    const dpr = window.devicePixelRatio || 1;
    this.width = width;
    this.height = height;
    this.canvas.width = Math.round(width * dpr);
    this.canvas.height = Math.round(height * dpr);
    this.canvas.style.width = `${width}px`;
    this.canvas.style.height = `${height}px`;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  contentWidth() {
    return Math.ceil(this.lengthS * this.zoom) + 2 * PAD;
  }

  x(seconds) {
    return Math.round(PAD + seconds * this.zoom - this.scroller.scrollLeft);
  }

  secondsAtX(x) {
    return Math.max(0, Math.min(this.lengthS, (x + this.scroller.scrollLeft - PAD) / this.zoom));
  }

  visibleTicks() {
    const s0 = this.secondsAtX(0);
    const s1 = this.secondsAtX(this.width);
    return [this.tempo.ticksAt(s0), this.tempo.ticksAt(s1)];
  }

  rowOf(lane) {
    return this.drums ? DRUM_ROW[lane] : lane;
  }

  colourOf(lane) {
    return this.colours.fret[this.drums ? DRUM_COLOUR[lane] : lane];
  }

  readColours() {
    this.colours = {
      bg: css("--bg"), panel: css("--panel"), rule: css("--rule"), rule2: css("--rule-2"), ink: css("--ink"),
      ink2: css("--ink-2"), ink3: css("--ink-3"), mark: css("--mark"), sp: css("--sp"), err: css("--err"),
      rim: css("--rim"), open: css("--open"), ghost: parseFloat(css("--ghost")) || 0.45, wave: css("--wave"),
      fret: [0, 1, 2, 3, 4].map((i) => css(`--fret-${i}`)),
      ui: css("--ui"), mono: css("--mono"),
    };
  }

  draw() {
    if (!this.track || !this.width) return;
    if (!this.colours) this.readColours();
    const c = this.colours;
    const ctx = this.ctx;
    const L = this.layout();
    ctx.clearRect(0, 0, this.width, this.height);
    ctx.fillStyle = c.bg;
    ctx.fillRect(0, 0, this.width, this.height);
    const [t0, t1] = this.visibleTicks();
    const lanesBottom = L.lanesY + L.rows * L.lane + L.kick;

    // lanes
    for (let r = 0; r < L.rows; r++) {
      const y = L.lanesY + r * L.lane + L.lane / 2;
      this.hline(y, c.rule2);
      this.hline(L.lanesY + (r + 1) * L.lane - 0.5, c.rule, 0.5);
    }
    if (L.kick) this.hline(L.kickY + L.kick / 2, c.rule2);

    this.drawBars(L, lanesBottom);
    this.drawRuler(L);
    this.drawMarkers(L);

    // notes of the edited level; while notes are dragged, the selected ones are drawn where they would go
    let notes = visibleSlice(this.track.notes, t0, t1, this.longest);
    if (this.drag) {
      notes = notes.filter((n) => !this.selection.has(noteKey(n)));
      for (const n of this.track.notes) {
        if (!this.selection.has(noteKey(n))) continue;
        const moved = this.dragged(n);
        if (moved[0] + moved[2] >= t0 - 1 && moved[0] <= t1 + 1) notes.push(moved);
      }
      notes.sort((a, b) => a[0] - b[0]);
    }
    const byTick = new Map();
    for (const n of notes) {
      if (!byTick.has(n[0])) byTick.set(n[0], []);
      byTick.get(n[0]).push(n);
    }
    for (const n of notes) if (n[2] > 0 && n[1] !== OPEN_LANE) this.drawSustain(n, L);
    for (const [tick, group] of byTick) this.drawGroup(tick, group, L);
    for (const n of notes) if (this.drag ? n[4] === true : this.selection.has(noteKey(n))) this.drawSelected(n, L);
    if (this.hover) this.drawHover(L);

    if (L.ghost) this.drawBelow(L, t0, t1);
    this.drawWave(L);
    if (this.box) this.drawBox();
    this.drawPlayhead();
  }

  /** A selected note where the current drag would put it, marked as selected (fifth element). */
  dragged(n) {
    const row = rowOf(this.drums, n[1]);
    const lane = row === null ? n[1] : laneOfRow(this.drums, row + this.drag.rows);
    return [Math.max(0, n[0] + this.drag.ticks), lane === null ? n[1] : lane, n[2], n[3], true];
  }

  /** The tick under an x position of the canvas (fractional). */
  tickAtX(x) {
    return this.tempo.ticksAt(this.secondsAtX(x));
  }

  /** The row under a y position: 0-4 from the top, the kick's row being 4 on drums; null elsewhere. */
  rowAt(py) {
    const L = this.layout();
    if (py >= L.lanesY && py < L.lanesY + L.rows * L.lane) return Math.floor((py - L.lanesY) / L.lane);
    if (L.kick && py >= L.kickY && py < L.kickY + L.kick) return 4;
    return null;
  }

  /** The y of a row's centre. */
  rowY(row, L) {
    return this.drums && row === 4 ? L.kickY + L.kick / 2 : L.lanesY + row * L.lane + L.lane / 2;
  }

  /** What a click at height `py` does: "ruler" and "wave" move the playhead, "lanes" picks notes. */
  zoneAt(py) {
    const L = this.layout();
    if (py < L.lanesY) return "ruler";
    if (py >= L.waveY - 6 && py <= L.waveY + L.wave + 6) return "wave";
    return "lanes";
  }

  drawWave(L) {
    const ctx = this.ctx;
    const c = this.colours;
    const mid = L.waveY + L.wave / 2;
    ctx.globalAlpha = 0.55;
    ctx.fillStyle = c.panel;
    ctx.fillRect(0, L.waveY - 6, this.width, L.wave + 12);
    ctx.globalAlpha = 1;
    this.hline(mid, c.rule2);
    if (!this.wave) {
      ctx.font = `14px ${c.ui}`;
      ctx.fillStyle = c.ink3;
      ctx.textAlign = "left";
      ctx.fillText(this.waveNote, 16, mid + 5);
      return;
    }
    const { peaks, perSecond, scale } = this.wave;
    const half = L.wave / 2;
    ctx.fillStyle = c.wave;
    const first = Math.max(0, this.x(0));
    const last = Math.min(this.width, this.x(this.lengthS));
    for (let x = first; x < last; x++) {
      const s0 = (x + this.scroller.scrollLeft - PAD) / this.zoom;
      const peak = peakBetween(peaks, perSecond, s0, s0 + 1 / this.zoom);
      const h = Math.min(half, Math.round(peak * scale * half));
      if (h > 0) ctx.fillRect(x, mid - h, 1, 2 * h);
    }
  }

  /** The playhead: where the audio is while playing, where it starts while stopped. */
  drawPlayhead() {
    const x = this.x(this.playhead);
    if (x < -8 || x > this.width + 8) return;
    const ctx = this.ctx;
    ctx.fillStyle = this.colours.mark;
    ctx.fillRect(x - 1, 8, 2, this.height - 8);
    ctx.beginPath();
    ctx.moveTo(x - 7, 0);
    ctx.lineTo(x + 7, 0);
    ctx.lineTo(x, 9);
    ctx.closePath();
    ctx.fill();
  }

  hline(y, colour, alpha = 1) {
    const ctx = this.ctx;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = colour;
    ctx.fillRect(0, Math.round(y), this.width, 1);
    ctx.globalAlpha = 1;
  }

  drawBars(L, lanesBottom) {
    const ctx = this.ctx;
    const c = this.colours;
    const tempo = this.tempo;
    for (let i = 0; i < this.bars.length; i++) {
      const x = this.x(this.barSeconds[i]);
      const next = i + 1 < this.bars.length ? this.x(this.barSeconds[i + 1]) : this.x(this.lengthS);
      if (next < 0 || x > this.width) continue;
      ctx.fillStyle = c.rule;
      ctx.fillRect(x, 10, 1, this.height - 10);
      const signature = tempo.signatureAt(this.bars[i]);
      const beat = tempo.beatTicks(signature);
      const end = i + 1 < this.bars.length ? this.bars[i + 1] : tempo.ticksAt(this.lengthS);
      const spacing = (next - x) / Math.max(1, (end - this.bars[i]) / beat);
      if (spacing >= 12) {
        ctx.fillStyle = c.rule2;
        for (let t = this.bars[i] + beat; t < end - 1e-6; t += beat) {
          ctx.fillRect(this.x(tempo.secondsAt(t)), L.lanesY, 1, lanesBottom - L.lanesY);
        }
      }
    }
  }

  drawRuler(L) {
    const ctx = this.ctx;
    const c = this.colours;
    const every = this.labelStep();
    ctx.textBaseline = "alphabetic";
    for (let i = 0; i < this.bars.length; i += every) {
      const x = this.x(this.barSeconds[i]);
      if (x < -60 || x > this.width) continue;
      const label = String(i + 1);
      ctx.font = `13px ${c.mono}`;
      const w = Math.max(30, Math.ceil(ctx.measureText(label).width) + 14);
      ctx.fillStyle = c.panel;
      ctx.fillRect(x, 10, w, 22);
      ctx.strokeStyle = c.rule;
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 0.5, 10.5, w - 1, 21);
      ctx.fillStyle = c.ink;
      ctx.textAlign = "center";
      ctx.fillText(label, x + w / 2, 26);
    }
    // tempo and time signature changes, after the bar box they fall on
    ctx.textAlign = "left";
    ctx.font = `12px ${c.mono}`;
    ctx.fillStyle = c.ink3;
    const signatures = new Map(this.tempo.signatures.map((s) => [s.tick, s]));
    const marks = new Map();
    for (const t of this.tempo.tempos) marks.set(t.tick, `${t.bpm.toFixed(1)} BPM`);
    for (const [tick, s] of signatures) marks.set(tick, `${marks.get(tick) ? `${marks.get(tick)} · ` : ""}${s.numerator}/${s.denominator}`);
    // Each change gets a short mark; its label is left out where it would run into the one before.
    let freeFrom = -Infinity;
    for (const [tick, text] of [...marks].sort((a, b) => a[0] - b[0])) {
      const x = this.x(this.tempo.secondsAt(tick));
      if (x < -200 || x > this.width) continue;
      ctx.fillRect(x, 36, 1, 8);
      if (x + 4 >= freeFrom) {
        ctx.fillText(text, x + 4, 46);
        freeFrom = x + 4 + ctx.measureText(text).width + 12;
      }
    }
    // sections, written in
    ctx.font = `700 17px ${c.ui}`;
    for (const [tick, name] of this.sections) {
      const x = this.x(this.tempo.secondsAt(tick));
      if (x < -200 || x > this.width) continue;
      ctx.fillStyle = c.ink;
      ctx.fillText(name, x + 6, 70);
      const w = ctx.measureText(name).width;
      ctx.fillRect(x + 5, 74, Math.ceil(w) + 2, 2);
    }
    // star power phrases of this track
    ctx.fillStyle = c.sp;
    for (const [tick, length] of this.track.star_power) {
      const x0 = this.x(this.tempo.secondsAt(tick));
      const x1 = this.x(this.tempo.secondsAt(tick + length));
      if (x1 < 0 || x0 > this.width) continue;
      ctx.fillRect(x0, 80, Math.max(2, x1 - x0), 7);
    }
  }

  labelStep() {
    if (this.bars.length < 2) return 1;
    const barPx = (this.barSeconds[1] - this.barSeconds[0]) * this.zoom;
    return barPx >= 48 ? 1 : barPx >= 24 ? 2 : barPx >= 12 ? 4 : 8;
  }

  drawMarkers(L) {
    const ctx = this.ctx;
    const c = this.colours;
    for (const m of this.markers) {
      const x = this.x(this.tempo.secondsAt(m.tick));
      if (x < -20 || x > this.width + 20) continue;
      if (m.level === "this") {
        ctx.strokeStyle = c.err;
        ctx.lineWidth = 2;
        ctx.strokeRect(x - 16, L.lanesY + 3, 32, L.rows * L.lane + L.kick - 6);
      } else if (m.level === "below" && L.ghost) {
        ctx.strokeStyle = c.err;
        ctx.lineWidth = 2;
        ctx.strokeRect(x - 10, L.ghostY - 5, 20, 5 * GHOST_ROW + 10);
      }
      ctx.fillStyle = c.err;
      ctx.beginPath();
      ctx.arc(x, 56, 8, 0, Math.PI * 2);
      ctx.fill();
      // the exclamation mark drawn, not typed: a bar and a dot
      ctx.fillStyle = c.bg;
      ctx.fillRect(x - 1.2, 51, 2.4, 6);
      ctx.beginPath();
      ctx.arc(x, 60, 1.3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  laneY(lane, L) {
    return this.drums && lane === 0 ? L.kickY + L.kick / 2 : L.lanesY + this.rowOf(lane) * L.lane + L.lane / 2;
  }

  /** Gems grow with the zoom up to what the lane holds, so that dense passages do not pile up. */
  radius(L) {
    const lane = Math.max(8, Math.min(12, Math.round(L.lane * 0.19)));
    return Math.max(5, Math.min(lane, Math.round(this.zoom * 0.06)));
  }

  /** The bar lines between the view's edges. */
  barsInView() {
    const s0 = this.secondsAtX(0);
    const s1 = this.secondsAtX(this.width);
    return this.barSeconds.filter((s) => s >= s0 && s <= s1).length;
  }

  drawSustain(n, L, alpha = 0.9) {
    const ctx = this.ctx;
    const x0 = this.x(this.tempo.secondsAt(n[0]));
    const x1 = this.x(this.tempo.secondsAt(n[0] + n[2]));
    if (x1 < 0 || x0 > this.width) return;
    const y = this.laneY(n[1], L);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = this.colourOf(n[1]);
    this.roundRect(x0, y - 4.5, x1 - x0, 9, 4.5);
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  drawGroup(tick, group, L) {
    const x = this.x(this.tempo.secondsAt(tick));
    if (x < -30 || x > this.width + 30) return;
    for (const n of group) {
      const lane = n[1];
      if (lane === OPEN_LANE) this.drawOpen(x, n, L);
      else if (this.drums && lane === 0) this.drawKick(x, L);
      else if (n[3] & CYMBAL) this.drawCymbal(x, this.laneY(lane, L), this.colourOf(lane), L);
      else this.drawGem(x, this.laneY(lane, L), this.colourOf(lane), n[3], L);
    }
  }

  drawGem(x, y, colour, flags, L) {
    const ctx = this.ctx;
    const c = this.colours;
    const r = this.radius(L);
    ctx.fillStyle = c.bg;
    ctx.beginPath();
    ctx.arc(x, y, r + 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = colour;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = c.rim;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    if (flags & (FORCED | TAP)) {
      ctx.fillStyle = flags & TAP ? c.bg : "#ffffff";
      ctx.beginPath();
      ctx.arc(x, y, r * 0.42, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  drawCymbal(x, y, colour, L) {
    const ctx = this.ctx;
    const c = this.colours;
    const w = this.radius(L) + 3;
    const h = Math.round(w * 0.72);
    const plate = () => {
      ctx.beginPath();
      ctx.moveTo(x - w, y);
      ctx.lineTo(x - w + 5, y - h);
      ctx.lineTo(x + w - 5, y - h);
      ctx.lineTo(x + w, y);
      ctx.lineTo(x + w - 5, y + h);
      ctx.lineTo(x - w + 5, y + h);
      ctx.closePath();
    };
    ctx.lineJoin = "round";
    plate();
    ctx.strokeStyle = c.bg;
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.fillStyle = colour;
    ctx.fill();
    ctx.strokeStyle = c.rim;
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.fillStyle = c.rim;
    ctx.fillRect(x - w + 6, y - 0.8, 2 * w - 12, 1.6);
  }

  drawKick(x, L) {
    const ctx = this.ctx;
    const y = L.kickY + L.kick / 2;
    ctx.fillStyle = this.colours.bg;
    this.roundRect(x - 17, y - 7, 34, 14, 7);
    ctx.fill();
    ctx.fillStyle = this.colours.fret[4];
    this.roundRect(x - 15, y - 5, 30, 10, 5);
    ctx.fill();
  }

  drawOpen(x, n, L) {
    const ctx = this.ctx;
    const top = L.lanesY + 6;
    const height = L.rows * L.lane - 12;
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = this.colours.open;
    this.roundRect(x - 6, top, 12, height, 6);
    ctx.fill();
    if (n[2] > 0) {
      const x1 = this.x(this.tempo.secondsAt(n[0] + n[2]));
      ctx.globalAlpha = 0.35;
      ctx.fillRect(x, top + height / 2 - 4, x1 - x, 8);
    }
    ctx.globalAlpha = 1;
  }

  /** A marker-white outline around one selected note, shaped as the note is. */
  drawSelected(n, L) {
    const ctx = this.ctx;
    const x = this.x(this.tempo.secondsAt(n[0]));
    if (x < -30 || x > this.width + 30) return;
    ctx.strokeStyle = this.colours.mark;
    ctx.lineWidth = 2;
    if (n[1] === OPEN_LANE) {
      this.roundRect(x - 10, L.lanesY + 2, 20, L.rows * L.lane - 4, 8);
    } else if (this.drums && n[1] === 0) {
      const y = L.kickY + L.kick / 2;
      this.roundRect(x - 21, y - 11, 42, 22, 9);
    } else {
      ctx.beginPath();
      ctx.arc(x, this.laneY(n[1], L), this.radius(L) + (n[3] & CYMBAL ? 9 : 6), 0, Math.PI * 2);
    }
    ctx.stroke();
  }

  /** The note the Draw tool would add, faint, with the sustain being drawn. */
  drawHover(L) {
    const { tick, lane, length } = this.hover;
    const x = this.x(this.tempo.secondsAt(tick));
    if (x < -30 || x > this.width + 30) return;
    const ctx = this.ctx;
    if (length > 0) this.drawSustain([tick, lane, length, 0], L, 0.45);
    ctx.globalAlpha = 0.5;
    if (this.drums && lane === 0) this.drawKick(x, L);
    else this.drawGem(x, this.laneY(lane, L), this.colourOf(lane), 0, L);
    ctx.globalAlpha = 1;
  }

  drawBox() {
    const ctx = this.ctx;
    const { x0, y0, x1, y1 } = this.box;
    const left = Math.min(x0, x1);
    const top = Math.min(y0, y1);
    ctx.globalAlpha = 0.08;
    ctx.fillStyle = this.colours.mark;
    ctx.fillRect(left, top, Math.abs(x1 - x0), Math.abs(y1 - y0));
    ctx.globalAlpha = 1;
    ctx.strokeStyle = this.colours.mark;
    ctx.lineWidth = 1;
    ctx.strokeRect(left + 0.5, top + 0.5, Math.abs(x1 - x0), Math.abs(y1 - y0));
  }

  drawBelow(L, t0, t1) {
    const ctx = this.ctx;
    const c = this.colours;
    ctx.globalAlpha = 0.55;
    ctx.fillStyle = c.panel;
    ctx.fillRect(0, L.ghostY - 6, this.width, 5 * GHOST_ROW + 12);
    ctx.globalAlpha = 1;
    for (let r = 0; r < 5; r++) this.hline(L.ghostY + r * GHOST_ROW + GHOST_ROW / 2, c.rule2);
    const rowBelow = (lane) => (this.drums ? (lane === 0 ? 4 : DRUM_ROW[lane]) : lane === OPEN_LANE ? 2 : lane);
    ctx.globalAlpha = c.ghost;
    for (const n of visibleSlice(this.below.notes, t0, t1, this.longestBelow)) {
      const x = this.x(this.tempo.secondsAt(n[0]));
      const y = L.ghostY + rowBelow(n[1]) * GHOST_ROW + GHOST_ROW / 2;
      const colour = n[1] === OPEN_LANE ? c.open : this.colourOf(n[1]);
      ctx.fillStyle = colour;
      if (n[2] > 0) {
        const x1 = this.x(this.tempo.secondsAt(n[0] + n[2]));
        ctx.fillRect(x, y - 2, x1 - x, 4);
      }
      ctx.beginPath();
      ctx.arc(x, y, 4.4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    // Notes an edit just changed here on its own (linked levels): a ring for a moment, no animation.
    ctx.strokeStyle = c.sp;
    ctx.lineWidth = 2;
    for (const f of this.flashes) {
      const x = this.x(this.tempo.secondsAt(f.tick));
      if (x < -12 || x > this.width + 12) continue;
      ctx.beginPath();
      ctx.arc(x, L.ghostY + rowBelow(f.lane) * GHOST_ROW + GHOST_ROW / 2, 8, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  roundRect(x, y, w, h, r) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.roundRect(x, y, Math.max(0, w), h, Math.min(r, Math.abs(w) / 2, h / 2));
  }

  /** The note under a point of the canvas (an open note counts in every row), or null. */
  noteAt(px, py) {
    if (!this.track) return null;
    const L = this.layout();
    const bottom = L.lanesY + L.rows * L.lane + L.kick;
    if (py < L.lanesY || py > bottom) return null;
    const seconds = this.secondsAtX(px);
    const reach = 16 / this.zoom;
    const t0 = this.tempo.ticksAt(Math.max(0, seconds - reach));
    const t1 = this.tempo.ticksAt(Math.min(this.lengthS, seconds + reach));
    let best = null;
    let bestDistance = Infinity;
    for (const n of visibleSlice(this.track.notes, t0, t1)) {
      const open = n[1] === OPEN_LANE;
      const y = open ? py : this.laneY(n[1], L);
      const dx = this.x(this.tempo.secondsAt(n[0])) - px;
      // An open note loses to a gem at the same spot, so the gems of a chord stay reachable.
      const d = Math.hypot(dx, y - py) + (open ? 8 : 0);
      if (d < bestDistance && Math.abs(dx) <= 16 && Math.abs(y - py) <= L.lane / 2) {
        best = n;
        bestDistance = d;
      }
    }
    return best;
  }
}
