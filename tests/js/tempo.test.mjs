// The page's tick <-> seconds conversion equals Python's TempoMap (fixture: tests/test_tempo_parity.py).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { TempoMap, roundHalfEven } from "../../chartgen/editor/static/tempo.js";

const path = process.env.CHARTGEN_TEMPO_FIXTURE || new URL("./tempo_fixture.json", import.meta.url);
const cases = JSON.parse(readFileSync(path, "utf8"));

for (const c of cases) {
  test(`tempo map agrees with Python: ${c.name}`, () => {
    const map = new TempoMap(c.resolution, c.tempos, c.signatures);
    for (const [tick, seconds] of c.seconds_at) {
      assert.ok(Math.abs(map.secondsAt(tick) - seconds) <= 1e-9, `seconds at tick ${tick}: ${map.secondsAt(tick)} vs ${seconds}`);
    }
    for (const [seconds, tick] of c.ticks_at) {
      assert.ok(Math.abs(map.ticksAt(seconds) - tick) <= 1e-6, `ticks at ${seconds} s: ${map.ticksAt(seconds)} vs ${tick}`);
    }
    assert.deepEqual(map.barLines(c.end_s), c.bar_lines);
  });
}

test("halves round to the even neighbour, as numpy does", () => {
  assert.deepEqual([0.5, 1.5, 2.5, 3.5, 2.4, 2.6, 7].map(roundHalfEven), [0, 2, 2, 4, 2, 3, 7]);
});

test("a tempo map must start at tick 0", () => {
  assert.throws(() => new TempoMap(192, [[96, 120]], []), /tick 0/);
  assert.throws(() => new TempoMap(0, [[0, 120]], []), /resolution/);
});
