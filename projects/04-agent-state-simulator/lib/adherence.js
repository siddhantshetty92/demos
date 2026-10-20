import { mulberry32, shuffle } from "./random.js";

export class AdherencePool {
  constructor({ size, minMinutes = 15, maxMinutes = 90, seed = 1 }) {
    this.size = size;
    this.minMinutes = minMinutes;
    this.maxMinutes = maxMinutes;
    this.rng = mulberry32(seed);
    this.active = new Map();
  }

  update(nowMs, onShift) {
    for (const [agent, stint] of this.active) {
      if (stint.endsAt <= nowMs || !onShift.has(agent)) this.active.delete(agent);
    }
    const deficit = this.size - this.active.size;
    if (deficit <= 0) return;
    const candidates = shuffle([...onShift].filter((a) => !this.active.has(a)), this.rng);
    for (const agent of candidates.slice(0, deficit)) {
      const minutes = this.minMinutes + Math.floor(this.rng() * (this.maxMinutes - this.minMinutes + 1));
      this.active.set(agent, { startedAt: nowMs, endsAt: nowMs + minutes * 60_000 });
    }
  }

  isOut(agent) {
    return this.active.has(agent);
  }
}
