// Pure helpers of playback (SPEC 53): no DOM and no Web Audio, tested by tests/js/transport.test.mjs.

/**
 * Song time <-> audio-context time for one playback. Every start, seek and speed change opens a segment
 * at the context time its sources start; a time before the newest segment belongs to the segment it falls
 * in, so the playhead stays right while a seek is still LEAD seconds away.
 */
export class SongClock {
  constructor() {
    this.segments = [];
  }

  /** A new segment: from context time `ctxTime` the song plays from `songTime` at `rate`. */
  start(ctxTime, songTime, rate) {
    this.segments.push({ ctx: ctxTime, song: songTime, rate });
    if (this.segments.length > 4) this.segments.shift();
  }

  clear() {
    this.segments = [];
  }

  get current() {
    return this.segments.at(-1) || null;
  }

  /** The song time heard at context time `ctxTime`; before the first segment starts, its own start. */
  songAt(ctxTime) {
    const segments = this.segments;
    if (!segments.length) return 0;
    let segment = segments[0];
    for (const s of segments) if (s.ctx <= ctxTime) segment = s;
    return segment.song + Math.max(0, ctxTime - segment.ctx) * segment.rate;
  }

  /** The context time at which the newest segment reaches `songTime`. */
  contextAt(songTime) {
    const segment = this.current;
    return segment.ctx + (songTime - segment.song) / segment.rate;
  }
}

/**
 * Every beat of the tempo map up to `endSeconds`, as chartgen.clonehero.click_overlay.click_schedule lists
 * them: beats counted from each time signature's own tick, the first of every `numerator` a downbeat, tick 0
 * left out (it is the start of the audio).
 * @returns {Array<{tick: number, seconds: number, downbeat: boolean}>}
 */
export function metronomeBeats(tempoMap, endSeconds) {
  const endTick = tempoMap.ticksAt(endSeconds);
  const signatures = tempoMap.signatures;
  const beats = [];
  signatures.forEach((signature, index) => {
    const stop = index + 1 < signatures.length ? signatures[index + 1].tick : endTick;
    const step = Math.floor((tempoMap.resolution * 4) / signature.denominator);
    for (let beat = 0; signature.tick + beat * step < stop; beat++) {
      const tick = signature.tick + beat * step;
      if (tick > 0) beats.push({ tick, seconds: tempoMap.secondsAt(tick), downbeat: beat % signature.numerator === 0 });
    }
  });
  return beats;
}

/** The index of the first beat at or after `seconds` (beats sorted by time). */
export function firstBeatFrom(beats, seconds) {
  let lo = 0;
  let hi = beats.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (beats[mid].seconds < seconds) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/**
 * The gain of each stem: a muted stem is silent; while any stem is soloed, only the soloed ones that are
 * not muted sound. `volume` is 0..1.
 */
export function stemGains(stems) {
  const solo = stems.some((s) => s.solo);
  return stems.map((s) => (s.mute || (solo && !s.solo) ? 0 : s.volume));
}

/** Whether a stem is silenced by another stem's solo (shown dimmed, not struck through). */
export function silencedBySolo(stems, index) {
  return stems.some((s) => s.solo) && !stems[index].solo && !stems[index].mute;
}

/**
 * The waveform's peaks: the largest absolute sample of every block of `block` frames over all channels.
 * @param {Float32Array[]} channels
 * @returns {Float32Array}
 */
export function peaks(channels, block) {
  const frames = channels.length ? channels[0].length : 0;
  const out = new Float32Array(Math.ceil(frames / block));
  for (const data of channels) {
    for (let b = 0, start = 0; start < frames; b++, start += block) {
      let peak = out[b];
      const end = Math.min(frames, start + block);
      for (let i = start; i < end; i++) {
        const v = data[i] < 0 ? -data[i] : data[i];
        if (v > peak) peak = v;
      }
      out[b] = peak;
    }
  }
  return out;
}

/** The largest peak between two times, for one pixel column of the waveform. */
export function peakBetween(peakArray, peaksPerSecond, s0, s1) {
  const from = Math.max(0, Math.floor(s0 * peaksPerSecond));
  const to = Math.min(peakArray.length, Math.max(from + 1, Math.ceil(s1 * peaksPerSecond)));
  let peak = 0;
  for (let i = from; i < to; i++) if (peakArray[i] > peak) peak = peakArray[i];
  return peak;
}

/**
 * Where to scroll so the playhead stays in view while playing: when it passes 85 % of the view the page
 * turns and it starts again at 15 %. A playhead the user scrolled away from is left alone (null).
 */
export function followScroll(playheadX, viewWidth, scrollLeft) {
  if (playheadX < 0 || playheadX > viewWidth) return null;
  if (playheadX <= viewWidth * 0.85) return null;
  return Math.max(0, scrollLeft + playheadX - viewWidth * 0.15);
}

export const SPEEDS = [0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1];
export const LATENCY_MIN = -300;
export const LATENCY_MAX = 500;

/** A latency offset typed by the user, as whole milliseconds within the allowed range (0 when not a number). */
export function clampLatency(value) {
  const ms = Math.round(Number(value));
  if (!Number.isFinite(ms)) return 0;
  return Math.min(LATENCY_MAX, Math.max(LATENCY_MIN, ms));
}
