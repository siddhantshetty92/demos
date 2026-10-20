globalThis.FairRoundRobin = {
  NONE: "__none__",
  NOT_NEEDED: "__na__",

  assign({ meetings, roster, perPersonCap, history = {}, overrides = {} }) {
    const { NONE, NOT_NEEDED } = globalThis.FairRoundRobin;
    const load = Object.fromEntries(roster.map((p) => [p, 0]));
    for (const meeting of meetings) {
      const pick = overrides[meeting.id];
      if (pick && pick !== NONE && pick !== NOT_NEEDED) load[pick] = (load[pick] ?? 0) + 1;
    }

    const result = {};
    const ordered = [...meetings].sort((a, b) => a.start.localeCompare(b.start));
    for (const meeting of ordered) {
      const override = overrides[meeting.id];
      if (override) {
        result[meeting.id] = { person: override === NONE || override === NOT_NEEDED ? null : override, reason: override === NOT_NEEDED ? "not needed" : "manual" };
        continue;
      }
      const candidates = roster.filter((p) => meeting.free.includes(p) && load[p] < perPersonCap);
      if (!candidates.length) {
        result[meeting.id] = { person: null, reason: meeting.free.length ? "everyone free is at the cap" : "nobody free" };
        continue;
      }
      const score = (p) => (history[p] ?? 0) + load[p];
      candidates.sort((a, b) => score(a) - score(b) || roster.indexOf(a) - roster.indexOf(b));
      const person = candidates[0];
      load[person] += 1;
      result[meeting.id] = { person, reason: `lowest load (${score(person) - 1} before this)` };
    }
    return { assignments: result, load };
  },
};
