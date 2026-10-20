import assert from "node:assert/strict";
import { test } from "node:test";
import { AdherencePool } from "../lib/adherence.js";
import { parseCsv } from "../lib/csv.js";
import { MINUTES_PER_WEEK, WeeklySchedule, minuteOfWeek } from "../lib/schedule.js";
import { Simulator } from "../lib/simulator.js";
import { stateInBlock } from "../lib/states.js";

test("csv parser handles quotes, commas and CRLF", () => {
  assert.deepEqual(parseCsv('a,b\r\n"x, y","say ""hi"""\r\n'), [{ a: "x, y", b: 'say "hi"' }]);
});

test("minute of week is Monday-based and timezone-aware", () => {
  assert.equal(minuteOfWeek(Date.parse("2026-09-07T00:00:00Z"), "UTC"), 0);
  assert.equal(minuteOfWeek(Date.parse("2026-09-07T13:30:00Z"), "America/New_York"), 9 * 60 + 30);
  assert.equal(minuteOfWeek(Date.parse("2026-09-07T03:00:00Z"), "America/New_York"), 6 * 1440 + 23 * 60);
});

test("any week's schedule repeats every week", () => {
  const schedule = WeeklySchedule.fromRows([{ agent: "a", start: "2025-01-06T09:00", end: "2025-01-06T17:00", activity: "Phones", type: "Productive" }]);
  assert.equal(schedule.at("a", 9 * 60).activity, "Phones");
  assert.equal(schedule.at("a", 17 * 60), null);
  assert.equal(schedule.at("a", 1440 + 9 * 60), null);
});

test("a shift across Sunday midnight wraps to Monday", () => {
  const schedule = WeeklySchedule.fromRows([{ agent: "a", start: "2026-09-13T22:00", end: "2026-09-14T02:00", activity: "Night", type: "Productive" }]);
  assert.ok(schedule.at("a", MINUTES_PER_WEEK - 30));
  assert.ok(schedule.at("a", 60));
  assert.equal(schedule.at("a", 3 * 60), null);
});

test("adherence pool keeps its target size and drops agents who leave shift", () => {
  const pool = new AdherencePool({ size: 2, seed: 3 });
  pool.update(0, new Set(["a", "b", "c", "d"]));
  assert.equal(pool.active.size, 2);
  const [first] = pool.active.keys();
  pool.update(60_000, new Set(["a", "b", "c", "d"].filter((x) => x !== first)));
  assert.equal(pool.isOut(first), false);
  assert.equal(pool.active.size, 2);
  pool.update(200 * 60_000, new Set(["a"]));
  assert.equal(pool.active.size, 1);
});

test("states inside a block are stable minute to minute and deterministic", () => {
  const args = { platform: "telephony", productive: true, agent: "a", blockStart: 540 };
  const states = Array.from({ length: 120 }, (_, i) => stateInBlock({ ...args, minute: 540 + i }));
  const changes = states.filter((s, i) => i && s !== states[i - 1]).length;
  assert.ok(changes >= 3 && changes <= 8, `changes=${changes}`);
  assert.deepEqual(states, Array.from({ length: 120 }, (_, i) => stateInBlock({ ...args, minute: 540 + i })));
});

test("out-of-adherence agents report non-productive states", () => {
  const rows = ["a", "b", "c"].map((agent) => ({ agent, start: "2026-09-07T09:00", end: "2026-09-07T17:00", activity: "Phones", type: "Productive" }));
  const sim = new Simulator({
    people: ["a", "b", "c"].map((agent, i) => ({ agent, telephony_id: `T${i}` })),
    schedule: WeeklySchedule.fromRows(rows),
    timeZone: "UTC",
    outOfAdherence: 1,
  });
  const { batches, outOfAdherence } = sim.tick(Date.parse("2026-10-19T10:00:00Z"));
  assert.equal(outOfAdherence.length, 1);
  for (const event of batches.telephony) {
    const productive = ["Available", "On Call", "After Call Work"].includes(event.state);
    assert.equal(productive, !event.out_of_adherence);
  }
});
