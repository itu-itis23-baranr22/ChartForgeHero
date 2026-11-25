// Playback's pure helpers: the song clock, the metronome's beats, mute and solo, the waveform, following.
import assert from "node:assert/strict";
import { test } from "node:test";

import { TempoMap } from "../../chartgen/editor/static/tempo.js";
import {
  SongClock, clampLatency, firstBeatFrom, followScroll, metronomeBeats, peakBetween, peaks, silencedBySolo, stemGains,
} from "../../chartgen/editor/static/transport.js";

const close = (a, b, tolerance = 1e-12) => assert.ok(Math.abs(a - b) <= tolerance, `${a} vs ${b}`);

test("the song clock maps context time to song time, at any speed", () => {
  const clock = new SongClock();
  clock.start(10, 30, 0.5);
  close(clock.songAt(10), 30);
  close(clock.songAt(12), 31);
  close(clock.contextAt(31), 12);
  close(clock.songAt(9.9), 30); // before the sources start, the start itself
});

test("a seek keeps the old segment until its sources start", () => {
  const clock = new SongClock();
  clock.start(1, 0, 1);
  clock.start(5.05, 60, 1); // seek asked at 5.0, sources start 50 ms later
  close(clock.songAt(5.02), 4.02);
  close(clock.songAt(5.05), 60);
  close(clock.songAt(6), 60.95);
  close(clock.contextAt(61), 6.05);
});

test("a speed change continues from where the audio is", () => {
  const clock = new SongClock();
  clock.start(0, 0, 1);
  const when = 4;
  clock.start(when, clock.songAt(when), 0.5);
  close(clock.songAt(6), 5);
  close(clock.contextAt(4.5), 5);
});

test("an empty clock is at the start", () => {
  assert.equal(new SongClock().songAt(3), 0);
});

test("metronome beats follow each time signature from its own tick and skip tick 0", () => {
  const map = new TempoMap(192, [[0, 120], [768, 60]], [[0, 4, 4], [768, 3, 4], [1344, 6, 8]]);
  const beats = metronomeBeats(map, 8);
  assert.deepEqual(beats.slice(0, 4).map((b) => b.tick), [192, 384, 576, 768]);
  assert.deepEqual(beats.slice(0, 4).map((b) => b.downbeat), [false, false, false, true]);
  close(beats[3].seconds, 2); // 4 beats at 120 BPM
  // 3/4 from 768: 768, 960, 1152 then 6/8 from 1344 in eighths (96 ticks)
  assert.deepEqual(beats.slice(3, 9).map((b) => b.tick), [768, 960, 1152, 1344, 1440, 1536]);
  assert.deepEqual(beats.slice(3, 9).map((b) => b.downbeat), [true, false, false, true, false, false]);
  close(beats[4].seconds, 3); // one beat at 60 BPM after 2 s
  assert.ok(beats.every((b) => b.seconds < 8));
});

test("the first beat from a time is found by bisection", () => {
  const beats = [0.5, 1, 1.5, 2].map((seconds) => ({ seconds }));
  assert.equal(firstBeatFrom(beats, 0), 0);
  assert.equal(firstBeatFrom(beats, 1), 1);
  assert.equal(firstBeatFrom(beats, 1.0001), 2);
  assert.equal(firstBeatFrom(beats, 9), 4);
});

test("mute silences, solo silences the others, a muted solo stays silent", () => {
  const stems = [
    { volume: 1, mute: false, solo: false },
    { volume: 0.5, mute: false, solo: false },
    { volume: 0.8, mute: true, solo: false },
  ];
  assert.deepEqual(stemGains(stems), [1, 0.5, 0]);
  stems[1].solo = true;
  assert.deepEqual(stemGains(stems), [0, 0.5, 0]);
  assert.equal(silencedBySolo(stems, 0), true);
  assert.equal(silencedBySolo(stems, 1), false);
  assert.equal(silencedBySolo(stems, 2), false); // muted: struck through, not dimmed
  stems[1].mute = true;
  assert.deepEqual(stemGains(stems), [0, 0, 0]);
});

test("waveform peaks take the largest absolute sample of each block over the channels", () => {
  const left = Float32Array.from([0, 0.2, -0.9, 0.1, 0.3]);
  const right = Float32Array.from([0.5, 0, 0, -0.4, 0]);
  assert.deepEqual(Array.from(peaks([left, right], 2)).map((v) => +v.toFixed(3)), [0.5, 0.9, 0.3]);
  assert.equal(peaks([], 4).length, 0);
  const p = Float32Array.from([0.1, 0.7, 0.2, 0.4]); // 2 peaks per second
  close(peakBetween(p, 2, 0, 0.5), 0.1, 1e-7); // float32
  close(peakBetween(p, 2, 0.4, 1.2), 0.7, 1e-7);
  close(peakBetween(p, 2, 1.5, 1.6), 0.4, 1e-7); // narrower than a peak: the peak it falls in
  close(peakBetween(p, 2, 9, 10), 0);
});

test("the view turns a page when the playhead passes 85 % and leaves a scrolled-away view alone", () => {
  assert.equal(followScroll(500, 1000, 2000), null);
  assert.equal(followScroll(851, 1000, 2000), 2000 + 851 - 150);
  assert.equal(followScroll(-10, 1000, 2000), null);
  assert.equal(followScroll(1200, 1000, 2000), null);
});

test("latency is whole milliseconds in range", () => {
  assert.equal(clampLatency("40"), 40);
  assert.equal(clampLatency(12.6), 13);
  assert.equal(clampLatency(-2000), -300);
  assert.equal(clampLatency(9999), 500);
  assert.equal(clampLatency("abc"), 0);
});
