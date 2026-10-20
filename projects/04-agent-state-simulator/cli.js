#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { parseCsv } from "./lib/csv.js";
import { WeeklySchedule } from "./lib/schedule.js";
import { Simulator } from "./lib/simulator.js";

const { values } = parseArgs({
  options: {
    people: { type: "string", default: "examples/people.csv" },
    schedule: { type: "string", default: "examples/schedule.csv" },
    tz: { type: "string", default: "America/New_York" },
    "every-seconds": { type: "string", default: "60" },
    ooa: { type: "string", default: "3" },
    webhook: { type: "string" },
    at: { type: "string" },
    once: { type: "boolean", default: false },
  },
});

const simulator = new Simulator({
  people: parseCsv(readFileSync(values.people, "utf8")),
  schedule: WeeklySchedule.fromRows(parseCsv(readFileSync(values.schedule, "utf8"))),
  timeZone: values.tz,
  outOfAdherence: Number(values.ooa),
});

async function emit(platform, events) {
  if (!values.webhook) {
    for (const e of events) console.log(`${platform.padEnd(10)} ${e.agent_id.padEnd(10)} ${e.state.padEnd(16)} ${e.out_of_adherence ? "OUT OF ADHERENCE" : e.scheduled_activity}`);
    return;
  }
  const res = await fetch(values.webhook, {
    method: "POST",
    headers: { "content-type": "application/json", ...(process.env.WEBHOOK_TOKEN ? { authorization: `Bearer ${process.env.WEBHOOK_TOKEN}` } : {}) },
    body: JSON.stringify({ platform, events }),
  });
  if (!res.ok) console.error(`${platform}: webhook returned ${res.status}`);
}

async function tick() {
  const now = values.at ? Date.parse(values.at) : Date.now();
  const result = simulator.tick(now);
  console.log(`\n${new Date(now).toISOString()}  on shift: ${result.onShift}  out of adherence: ${result.outOfAdherence.join(", ") || "none"}`);
  for (const [platform, events] of Object.entries(result.batches)) if (events.length) await emit(platform, events);
}

await tick();
if (!values.once && !values.at) setInterval(tick, Number(values["every-seconds"]) * 1000);
