import assert from "node:assert/strict";
import { test } from "node:test";
import "../assign.js";

const { assign, NONE, NOT_NEEDED } = globalThis.FairRoundRobin;
const roster = ["a", "b", "c"];
const meeting = (id, start, free) => ({ id, start, free });

test("spreads calls across free people, lowest load first", () => {
  const meetings = [meeting("1", "2026-10-19T09:00", roster), meeting("2", "2026-10-19T10:00", roster), meeting("3", "2026-10-19T11:00", roster)];
  const { load } = assign({ meetings, roster, perPersonCap: 5 });
  assert.deepEqual(load, { a: 1, b: 1, c: 1 });
});

test("prior attendance counts against a person", () => {
  const { assignments } = assign({ meetings: [meeting("1", "2026-10-19T09:00", roster)], roster, perPersonCap: 5, history: { a: 3, b: 0, c: 1 } });
  assert.equal(assignments["1"].person, "b");
});

test("only free people under the cap are picked", () => {
  const meetings = [meeting("1", "2026-10-19T09:00", ["a"]), meeting("2", "2026-10-19T10:00", ["a"]), meeting("3", "2026-10-19T11:00", [])];
  const { assignments } = assign({ meetings, roster, perPersonCap: 1 });
  assert.equal(assignments["1"].person, "a");
  assert.equal(assignments["2"].person, null);
  assert.match(assignments["2"].reason, /cap/);
  assert.equal(assignments["3"].reason, "nobody free");
});

test("manual picks consume a slot before auto-assignment runs", () => {
  const meetings = [meeting("1", "2026-10-19T09:00", ["a", "b"]), meeting("2", "2026-10-19T10:00", ["a", "b"])];
  const { assignments } = assign({ meetings, roster, perPersonCap: 1, overrides: { "2": "a" } });
  assert.equal(assignments["1"].person, "b");
  assert.equal(assignments["2"].reason, "manual");
});

test("no-shadow and not-needed overrides leave the call empty", () => {
  const meetings = [meeting("1", "2026-10-19T09:00", roster), meeting("2", "2026-10-19T10:00", roster)];
  const { assignments, load } = assign({ meetings, roster, perPersonCap: 2, overrides: { "1": NONE, "2": NOT_NEEDED } });
  assert.equal(assignments["1"].person, null);
  assert.equal(assignments["2"].reason, "not needed");
  assert.deepEqual(load, { a: 0, b: 0, c: 0 });
});
