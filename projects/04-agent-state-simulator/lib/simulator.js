import { AdherencePool } from "./adherence.js";
import { minuteOfWeek } from "./schedule.js";
import { PLATFORMS, stateInBlock } from "./states.js";

export class Simulator {
  constructor({ people, schedule, timeZone, outOfAdherence = 5, seed = 1 }) {
    this.people = people;
    this.schedule = schedule;
    this.timeZone = timeZone;
    this.pool = new AdherencePool({ size: outOfAdherence, seed });
  }

  tick(nowMs) {
    const minute = minuteOfWeek(nowMs, this.timeZone);
    const onShift = this.schedule.onShift(minute);
    const productiveOnShift = new Set([...onShift].filter((a) => this.schedule.at(a, minute).productive));
    this.pool.update(nowMs, productiveOnShift);

    const batches = Object.fromEntries(Object.keys(PLATFORMS).map((p) => [p, []]));
    for (const person of this.people) {
      const slot = this.schedule.at(person.agent, minute);
      if (!slot) continue;
      const out = this.pool.isOut(person.agent);
      for (const [platform, { idColumn }] of Object.entries(PLATFORMS)) {
        const externalId = person[idColumn];
        if (!externalId) continue;
        batches[platform].push({
          agent_id: externalId,
          state: stateInBlock({ platform, productive: slot.productive && !out, agent: person.agent, blockStart: slot.start, minute }),
          scheduled_activity: slot.activity,
          out_of_adherence: out,
          timestamp: new Date(nowMs).toISOString(),
        });
      }
    }
    return { minute, onShift: onShift.size, outOfAdherence: [...this.pool.active.keys()], batches };
  }
}
