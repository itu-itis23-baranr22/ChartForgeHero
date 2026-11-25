// Tick <-> seconds, the same piecewise-constant curve as chartgen.core.timing.TempoMap, computed in the
// same order so that both agree to the last bit (checked against Python by tests/js/tempo.test.mjs).

export class TempoMap {
  /**
   * @param {number} resolution ticks per beat
   * @param {Array<[number, number]>} tempos [tick, bpm], the first at tick 0
   * @param {Array<[number, number, number]>} signatures [tick, numerator, denominator], the first at tick 0
   */
  constructor(resolution, tempos, signatures) {
    if (!(resolution > 0)) throw new Error(`resolution must be > 0, got ${resolution}`);
    if (!tempos.length || tempos[0][0] !== 0) throw new Error("the first tempo must be at tick 0");
    this.resolution = resolution;
    this.tempos = tempos.map(([tick, bpm]) => ({ tick, bpm }));
    this.signatures = (signatures.length ? signatures : [[0, 4, 4]]).map(([tick, numerator, denominator]) => ({
      tick, numerator, denominator,
    }));
    this.eventTicks = this.tempos.map((t) => t.tick);
    this.secondsPerTick = this.tempos.map((t) => 60 / (t.bpm * resolution));
    this.eventSeconds = [0];
    for (let i = 1; i < this.tempos.length; i++) {
      this.eventSeconds.push(this.eventSeconds[i - 1] + (this.eventTicks[i] - this.eventTicks[i - 1]) * this.secondsPerTick[i - 1]);
    }
  }

  /** The last index i with values[i] <= x (numpy searchsorted side="right" minus one). */
  static lastAtOrBefore(values, x) {
    let lo = 0;
    let hi = values.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (values[mid] <= x) lo = mid + 1;
      else hi = mid;
    }
    return lo - 1;
  }

  secondsAt(tick) {
    if (tick < 0) throw new Error("ticks must be >= 0");
    const i = TempoMap.lastAtOrBefore(this.eventTicks, tick);
    return this.eventSeconds[i] + (tick - this.eventTicks[i]) * this.secondsPerTick[i];
  }

  ticksAt(seconds) {
    if (seconds < 0) throw new Error("seconds must be >= 0");
    const i = TempoMap.lastAtOrBefore(this.eventSeconds, seconds);
    return this.eventTicks[i] + (seconds - this.eventSeconds[i]) / this.secondsPerTick[i];
  }

  bpmAt(tick) {
    return this.tempos[TempoMap.lastAtOrBefore(this.eventTicks, tick)].bpm;
  }

  signatureAt(tick) {
    let found = this.signatures[0];
    for (const s of this.signatures) if (s.tick <= tick) found = s;
    return found;
  }

  barTicks(signature) {
    return (this.resolution * 4 * signature.numerator) / signature.denominator;
  }

  beatTicks(signature) {
    return (this.resolution * 4) / signature.denominator;
  }

  /** The tick of every bar line from the start to endSeconds, each signature from its own tick. */
  barLines(endSeconds) {
    const endTick = this.ticksAt(endSeconds);
    const ticks = [];
    this.signatures.forEach((signature, index) => {
      const next = this.signatures[index + 1];
      const stop = next ? Math.min(next.tick, endTick + 1e-9) : endTick + 1e-9;
      const step = this.barTicks(signature);
      // numpy.arange(start, stop, step): start + k * step while below stop
      for (let k = 0; ; k++) {
        const tick = signature.tick + k * step;
        if (tick >= stop) break;
        ticks.push(tick);
      }
    });
    return ticks.map(roundHalfEven);
  }
}

/** numpy.round: halves go to the even neighbour. */
export function roundHalfEven(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}
