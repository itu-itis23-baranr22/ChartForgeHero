// Playback (SPEC 53): one Web Audio source per stem, all started at the same audio-clock time, a gain per
// stem, speed through the playback rate, and a metronome scheduled on the audio clock from the tempo map.
// Keep pitch (E.4.1 a): a stem with a copy stretched to the current speed plays that copy at full rate from
// song time / speed, so the pitch stays and the clock, and with it the sync, is the same.
// Works on any BaseAudioContext, so tests/browser/sync.mjs renders the same code offline and measures it.

import { SongClock, firstBeatFrom, stemGains } from "./transport.js";

/** Seconds between a command and the audio it starts: every source of a start gets the same time. */
export const LEAD = 0.05;
/** How far ahead metronome clicks are scheduled. Long enough to survive a throttled background tab;
 * a seek, a speed change or switching the metronome off cancels what is scheduled. */
export const LOOKAHEAD = 1.5;
/** How often the live page schedules more clicks. */
export const PUMP_MS = 50;
const GAIN_SMOOTHING = 0.005;
const METRONOME_LEVEL = 0.8;

/** The metronome's sound, as in chartgen.clonehero.click_overlay: a decaying sine burst. */
const CLICK_SECONDS = 0.035;
const CLICK_DECAY = 0.008;
const BEAT = { hz: 1000, level: 0.45 };
const DOWNBEAT = { hz: 2000, level: 0.7 };

function clickBuffer(ctx, { hz, level }) {
  const frames = Math.round(CLICK_SECONDS * ctx.sampleRate);
  const buffer = new AudioBuffer({ length: frames, numberOfChannels: 1, sampleRate: ctx.sampleRate });
  const data = buffer.getChannelData(0);
  for (let i = 0; i < frames; i++) {
    const t = i / ctx.sampleRate;
    data[i] = level * Math.sin(2 * Math.PI * hz * t) * Math.exp(-t / CLICK_DECAY);
  }
  return buffer;
}

export class Player {
  /** @param {BaseAudioContext} ctx */
  constructor(ctx) {
    this.ctx = ctx;
    this.master = new GainNode(ctx);
    this.master.connect(ctx.destination);
    this.stems = [];
    this.rate = 1;
    this.cursor = 0; // where playback starts while stopped, in song seconds
    this.playing = false;
    this.clock = new SongClock();
    this.sources = [];
    this.beats = [];
    this.metronomeOn = false;
    this.metronomeGain = new GainNode(ctx, { gain: METRONOME_LEVEL });
    this.metronomeGain.connect(this.master);
    this.nextBeat = 0;
    this.clicks = new Set();
    this.clickBuffers = { beat: clickBuffer(ctx, BEAT), downbeat: clickBuffer(ctx, DOWNBEAT) };
    this.duration = 0;
    this.keepPitch = false;
  }

  /** A stem's copy stretched to `speed` without lowering its pitch (it replaces one for another speed). */
  setSlow(index, speed, buffer) {
    this.stems[index].slow = { speed, buffer };
  }

  /** Lets go of every stretched copy (they take memory). */
  clearSlow() {
    for (const stem of this.stems) stem.slow = null;
  }

  /** Whether every stem has its stretched copy for `speed`. */
  slowReady(speed) {
    return this.stems.length > 0 && this.stems.every((s) => s.slow && s.slow.speed === speed);
  }

  /** Keep pitch on or off; playing on from where the audio is, with the other copies. */
  setKeepPitch(on) {
    if (on === this.keepPitch) return null;
    this.keepPitch = on;
    return this.refresh();
  }

  /** Starts the sources again where the audio is: after the stems to play have changed. */
  refresh() {
    if (!this.playing) return null;
    const when = this.ctx.currentTime + LEAD;
    return this.restart(this.clock.songAt(when), when);
  }

  /** Adds a decoded stem; it plays from the next start on. */
  addStem(file, buffer) {
    const gain = new GainNode(this.ctx);
    gain.connect(this.master);
    this.stems.push({ file, buffer, gain, volume: 1, mute: false, solo: false, slow: null });
    this.duration = Math.max(this.duration, buffer.duration);
    this.applyGains(true);
  }

  /** The metronome's beats: [{seconds, downbeat}] sorted by time (transport.metronomeBeats). */
  setBeats(beats) {
    this.beats = beats;
  }

  /** Changes a stem's mute, solo or volume without restarting playback. */
  setStem(index, change) {
    Object.assign(this.stems[index], change);
    this.applyGains();
  }

  applyGains(now = false) {
    const gains = stemGains(this.stems);
    this.stems.forEach((stem, i) => {
      const param = stem.gain.gain;
      if (now) param.value = gains[i];
      else {
        param.cancelScheduledValues(this.ctx.currentTime);
        param.setTargetAtTime(gains[i], this.ctx.currentTime, GAIN_SMOOTHING);
      }
    });
  }

  /** The song time being played at context time `ctxTime` (now by default); the cursor while stopped. */
  position(ctxTime = this.ctx.currentTime) {
    if (!this.playing) return this.cursor;
    return Math.min(this.duration, this.clock.songAt(ctxTime));
  }

  /**
   * The context time being heard now, from the output timestamp when the browser gives one (it accounts for
   * the output's own latency), else the context's clock.
   */
  heardContextTime() {
    const ctx = this.ctx;
    if (typeof ctx.getOutputTimestamp === "function") {
      const stamp = ctx.getOutputTimestamp();
      if (stamp.contextTime > 0 && stamp.performanceTime > 0) {
        return stamp.contextTime + (performance.now() - stamp.performanceTime) / 1000;
      }
    }
    return ctx.currentTime - (ctx.outputLatency || 0);
  }

  /**
   * Where the playhead goes: the song time being heard, later by `latencyMs` (the user's calibration).
   * `heard` is the context time being heard, when the caller has already read it.
   */
  playhead(latencyMs = 0, heard = this.heardContextTime()) {
    if (!this.playing) return this.cursor;
    return Math.min(this.duration, Math.max(0, this.clock.songAt(heard - latencyMs / 1000)));
  }

  /** Starts playing from `from` (the cursor by default). Returns the context time the sources start at. */
  play(from = this.cursor) {
    if (this.playing) return this.clock.current.ctx;
    this.playing = true;
    this.clock.clear();
    return this.restart(Math.min(Math.max(0, from), this.duration));
  }

  /** Stops, leaving the cursor where playback was. */
  pause() {
    if (!this.playing) return;
    this.cursor = this.position();
    this.playing = false;
    for (const source of this.sources) source.stop();
    this.sources = [];
    this.cancelClicks(0);
    this.clock.clear();
  }

  /** Moves the cursor, or the playback when playing. Returns the start time of the new sources, or null. */
  seek(seconds) {
    const target = Math.min(Math.max(0, seconds), this.duration);
    if (!this.playing) {
      this.cursor = target;
      return null;
    }
    return this.restart(target);
  }

  /** Changes the speed; playing on from where the audio is when the new sources start. */
  setRate(rate) {
    if (rate === this.rate) return null;
    if (!this.playing) {
      this.rate = rate;
      return null;
    }
    const when = this.ctx.currentTime + LEAD;
    const from = this.clock.songAt(when);
    this.rate = rate;
    return this.restart(from, when);
  }

  setMetronome(on) {
    if (on === this.metronomeOn) return;
    this.metronomeOn = on;
    if (!on) {
      this.cancelClicks(0);
      return;
    }
    if (this.playing) {
      this.nextBeat = firstBeatFrom(this.beats, this.clock.songAt(this.ctx.currentTime + LEAD));
      this.pump();
    }
  }

  /**
   * Starts every stem at `songTime` at context time `when`, stopping the sources playing now at that same
   * time, so that a seek or a speed change has no gap and no overlap.
   */
  restart(songTime, when = this.ctx.currentTime + LEAD) {
    for (const source of this.sources) source.stop(when);
    this.cancelClicks(when);
    this.sources = [];
    for (const stem of this.stems) {
      if (songTime >= stem.buffer.duration) continue;
      const slow = this.keepPitch && this.rate < 1 && stem.slow && stem.slow.speed === this.rate ? stem.slow.buffer : null;
      const source = slow
        ? new AudioBufferSourceNode(this.ctx, { buffer: slow, playbackRate: 1 })
        : new AudioBufferSourceNode(this.ctx, { buffer: stem.buffer, playbackRate: this.rate });
      source.connect(stem.gain);
      source.start(when, slow ? Math.min(songTime / this.rate, slow.duration) : songTime);
      this.sources.push(source);
    }
    this.clock.start(when, songTime, this.rate);
    this.nextBeat = firstBeatFrom(this.beats, songTime);
    this.pump();
    return when;
  }

  /** Schedules the metronome's clicks up to LOOKAHEAD seconds ahead. Called every PUMP_MS while playing. */
  pump() {
    if (!this.playing || !this.metronomeOn) return;
    const now = this.ctx.currentTime;
    const horizon = now + LOOKAHEAD;
    while (this.nextBeat < this.beats.length) {
      const beat = this.beats[this.nextBeat];
      const when = this.clock.contextAt(beat.seconds);
      if (when > horizon) break;
      this.nextBeat++;
      if (when < now) continue;
      const source = new AudioBufferSourceNode(this.ctx, {
        buffer: beat.downbeat ? this.clickBuffers.downbeat : this.clickBuffers.beat,
      });
      source.connect(this.metronomeGain);
      source.start(when);
      const click = { source, when };
      this.clicks.add(click);
      source.onended = () => this.clicks.delete(click);
    }
  }

  /** Stops the clicks due at or after `from` (all of them for 0); a click already sounding is cut there. */
  cancelClicks(from) {
    for (const click of this.clicks) {
      if (from === 0 || click.when >= from) {
        click.source.stop(from === 0 ? 0 : from);
        this.clicks.delete(click);
      }
    }
  }

  /** Lets go of the sources; the page closes the context. */
  dispose() {
    this.pause();
    this.stems = [];
  }
}
